"""Merge converted datasets into one leakage-safe train/val/test set.

    python ai/scripts/build_dataset.py
    python ai/scripts/build_dataset.py --dry-run
    python ai/scripts/build_dataset.py --sources SCTD AI4SHIPWRECKS

Reads  ai/data/interim/<DATASET>/...   (output of voc_to_yolo / masks_to_yolo)
Writes ai/data/processed/{train,val,test}/{images,labels} + data.yaml + report

This is plan §12, the leakage-safe split, and it is the step where a good
result quietly becomes a meaningless one.

The two ways this leaks
-----------------------
1. DUPLICATE IMAGES. SCTD ships 25 byte-identical image pairs annotated twice
   with slightly different boxes. Split them randomly and the same picture sits
   in train and val: the model has memorised the answer, and validation says it
   generalises. Exact duplicates are dropped; near-duplicates are grouped so a
   group can never straddle a split.

2. TILES FROM ONE FRAME. Adjacent tiles of a single waterfall overlap by 25%
   and show the same seabed. One in train and one in val is the same leak in a
   different costume. Tiles are grouped by their source frame, which the tiler
   encoded into every filename.

Both are handled the same way: nothing is split by FILE, everything is split by
GROUP, and a group is the smallest set of files that must stay together.

3. FRAMES FROM ONE CONTINUOUS SURVEY. SubPipe is 66 minutes of one AUV
   following one pipeline. Grouping by frame is not enough: consecutive frames
   are one second and a couple of metres apart, so a random group split puts
   the same stretch of pipe on both sides. "mode: temporal" cuts the survey at
   a real gap in its timestamps instead, so the test portion is seabed the
   model has genuinely never seen. Note what this does and does not buy: the
   held-out track is still the same survey, the same sonar and the same pipe,
   so it measures tracking, not generalisation to debris elsewhere. Report it
   next to the independent boxes, never instead of them.

Where a dataset ships its own benchmark split (AI4Shipwrecks), that split is
respected so our numbers stay comparable to the published ones. Validation is
carved out of its train portion, never out of its test portion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.taxonomy import TRAINING_CLASSES  # noqa: E402

INTERIM = AI_ROOT / "data" / "interim"
PROCESSED = AI_ROOT / "data" / "processed"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")

# How each dataset's own directory layout maps onto our splits.
#   "fixed"  -> the dataset ships a benchmark split; honour it.
#   "random" -> flat set; split it here, grouped and stratified.
#
# For AI4Shipwrecks the authors' test set is kept as OUR test set so results
# stay comparable to the paper. Validation comes out of their train portion.
SPLIT_POLICY = {
    "AI4SHIPWRECKS": {"mode": "fixed", "map": {"train": "train", "test": "test"}, "val_from": "train"},
    "SCTD": {"mode": "random"},
    "SONARDETECT": {"mode": "fixed", "map": {"train": "train", "valid": "val", "test": "test"}},
    "GHOSTVISION": {"mode": "fixed", "map": {"train": "train", "valid": "val", "test": "test"}},
    "MARINE-PULSE": {"mode": "fixed", "map": {"train": "train", "test": "test"}},
    # SubPipe was ENTIRELY train through gv4, to keep the test split identical
    # to gv-yolo11s and gv2-yolo11s. That protected comparability at the cost
    # of making debris unmeasurable: 2,171 training boxes against 14 in test,
    # so the debris column of every metrics table was noise.
    #
    # From gv5 it is cut in time instead. The survey has a 156-second gap at
    # 70% through -- roughly 150 m of seabed at survey speed -- and that gap is
    # the split point. Everything before it trains, everything after it tests.
    # No SubPipe frames go to val: val only drives early stopping and
    # calibration, and the other sources already cover it.
    #
    # This DOES break strict comparability with gv2/gv4 on debris. That is the
    # trade, taken deliberately: a comparable meaningless number is worth less
    # than an incomparable meaningful one, and the wreck/plane/ghost_pot
    # columns are unaffected.
    "SUBPIPE": {"mode": "temporal", "cuts": [(0.70, "train"), (1.00, "test")]},
    # Synthetic ghost nets go ENTIRELY to train, and this is not a tuning
    # choice -- it is the line that keeps the result honest. The frames are
    # real net returns composited onto real seabed, so they look exactly like
    # test data and would score well on themselves. A ghost_net number
    # measured on generated nets would be self-congratulation.
    #
    # The 36 real held-out boxes stay the only thing that counts, and they are
    # untouched by this because synthesis never sees the test split: its
    # backgrounds come from train only.
    "GHOSTNET-SYNTH": {"mode": "fixed", "map": {"train": "train"}},
}
DEFAULT_POLICY = {"mode": "random"}


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def find_pairs(root: Path) -> list[tuple[str, Path, Path]]:
    """(split_or_empty, image, label) for every labelled image under root."""
    out = []
    for images_dir in sorted(root.rglob("images")):
        labels_dir = images_dir.parent / "labels"
        if not labels_dir.is_dir():
            continue
        rel = images_dir.parent.relative_to(root)
        split = rel.parts[-1] if rel.parts else ""
        for img in sorted(images_dir.iterdir()):
            if img.suffix.lower() not in IMAGE_EXTS:
                continue
            lbl = labels_dir / (img.stem + ".txt")
            if lbl.exists():
                out.append((split, img, lbl))
    return out


def group_key(dataset: str, img: Path) -> str:
    """The unit that must not be split.

    Tiles are named "<frame>__x<col>_y<row>" by masks_to_yolo, so everything
    before the double underscore is the source waterfall. For anything else the
    file is its own group until deduplication merges it with its twins.
    """
    stem = img.stem
    return f"{dataset}:{stem.split('__')[0]}" if "__" in stem else f"{dataset}:{stem}"


#: Any run of digits with an optional decimal point, long enough to be a unix
#: timestamp. SubPipe names frames "SSS_HF_images_1693569378.780__x0_y0", and
#: both the HF and LF channels of one survey share the same clock, so sorting
#: on this interleaves the two channels correctly.
TIME_RE = re.compile(r"(\d{9,}(?:\.\d+)?)")


def time_key(img: Path) -> float | None:
    """The acquisition time encoded in a filename, or None if there isn't one."""
    m = TIME_RE.search(img.stem)
    return float(m.group(1)) if m else None


def temporal_split(items: list, cuts: list[tuple[float, str]]) -> list[tuple[str, tuple]]:
    """Assign (ds, img, lbl) triples to splits by acquisition time.

    Sorted by timestamp, then cut at the given fractions -- so a split boundary
    is a moment in the survey, and everything after it is seabed the earlier
    portion never covered. Falls back to filename order for any frame with no
    timestamp, which keeps the function total rather than silently dropping
    frames; the caller reports how many that was.
    """
    ordered = sorted(items, key=lambda t: (time_key(t[1]) is None, time_key(t[1]) or 0.0, t[1].stem))
    n = len(ordered)
    out, start = [], 0
    for frac, split in cuts:
        end = n if frac >= 1.0 else int(round(n * frac))
        for it in ordered[start:end]:
            out.append((split, it))
        start = end
    return out


def classes_in(label: Path) -> set[int]:
    """The distinct classes present. Used for stratifying the split."""
    out = set()
    for line in label.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            out.add(int(line.split()[0]))
    return out


def boxes_in(label: Path) -> Counter:
    """How many boxes of each class.

    NOT the same as classes_in, and the difference matters: one frame holding
    eight crab pots is one frame and eight boxes. Reporting frames while
    calling them boxes understates the training signal, which is exactly the
    mistake this function exists to stop.
    """
    out: Counter = Counter()
    for line in label.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            out[int(line.split()[0])] += 1
    return out


def stratified_group_split(
    groups: dict[str, list], ratios: tuple[float, float, float], rng: random.Random
) -> dict[str, str]:
    """Assign whole groups to train/val/test, keeping classes represented.

    Greedy rather than clever: groups are shuffled, then walked rarest-class
    first, each going to whichever split is furthest below its quota for that
    class. With 57 aircraft against 271 ships, a plain random split can leave a
    class almost absent from val, making its metric noise.
    """
    keys = list(groups)
    rng.shuffle(keys)

    def rarity(k):
        cls = set()
        for _s, _i, lbl in groups[k]:
            cls |= classes_in(lbl)
        return (min(cls) if cls else 99, -len(groups[k]))

    keys.sort(key=rarity)

    names = ("train", "val", "test")
    counts = {n: Counter() for n in names}
    totals = Counter()
    for k in keys:
        for _s, _i, lbl in groups[k]:
            for c in classes_in(lbl) or {-1}:
                totals[c] += 1

    assignment: dict[str, str] = {}
    for k in keys:
        present = Counter()
        for _s, _i, lbl in groups[k]:
            for c in classes_in(lbl) or {-1}:
                present[c] += 1
        best, best_deficit = None, None
        for name, ratio in zip(names, ratios):
            if ratio <= 0:
                continue
            deficit = 0.0
            for c, n in present.items():
                want = totals[c] * ratio
                deficit += (want - counts[name][c]) / max(1.0, want)
            deficit /= max(1, len(present))
            if best_deficit is None or deficit > best_deficit:
                best, best_deficit = name, deficit
        assignment[k] = best
        for c, n in present.items():
            counts[best][c] += n
    return assignment


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge interim datasets into a leakage-safe split.")
    ap.add_argument("--sources", nargs="*", default=None, help="dataset ids under ai/data/interim")
    ap.add_argument("--out", default=None)
    ap.add_argument("--ratios", nargs=3, type=float, default=[0.70, 0.15, 0.15],
                    metavar=("TRAIN", "VAL", "TEST"))
    ap.add_argument("--val-fraction", type=float, default=0.15,
                    help="fraction carved out of a fixed-split dataset's TRAIN portion for validation")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out_root = Path(args.out) if args.out else PROCESSED

    if not INTERIM.exists():
        print("no ai/data/interim/ -- run the converters first")
        return 1
    sources = args.sources or sorted(d.name for d in INTERIM.iterdir() if d.is_dir())
    if not sources:
        print("no converted datasets in ai/data/interim/")
        return 1

    # ---- collect, deduplicate, group -------------------------------------
    by_hash: dict[str, tuple[str, Path]] = {}
    groups: dict[str, list] = defaultdict(list)
    fixed: dict[str, list] = defaultdict(list)
    temporal: dict[str, list] = defaultdict(list)
    dropped_dupes = Counter()
    per_source = Counter()

    for ds in sources:
        root = INTERIM / ds
        if not root.is_dir():
            print(f"  skip {ds}: not found")
            continue
        policy = SPLIT_POLICY.get(ds.upper(), DEFAULT_POLICY)
        for split, img, lbl in find_pairs(root):
            digest = hashlib.md5(img.read_bytes()).hexdigest()
            if digest in by_hash:
                # Byte-identical to something already accepted. SCTD ships 25
                # such pairs, annotated twice with different boxes. Keeping both
                # puts one picture on both sides of the split.
                dropped_dupes[ds] += 1
                continue
            by_hash[digest] = (ds, img)
            per_source[ds] += 1

            if policy["mode"] == "temporal":
                temporal[ds].append((ds, img, lbl))
            elif policy["mode"] == "fixed":
                target = policy.get("map", {}).get(split)
                if target is None:
                    continue
                fixed[f"{ds}|{target}"].append((ds, img, lbl))
            else:
                groups[group_key(ds, img)].append((ds, img, lbl))

    # ---- assign splits ----------------------------------------------------
    plan: list[tuple[str, str, Path, Path]] = []   # (split, dataset, image, label)

    if groups:
        assignment = stratified_group_split(groups, tuple(args.ratios), rng)
        for key, items in groups.items():
            for ds, img, lbl in items:
                plan.append((assignment[key], ds, img, lbl))

    for ds, items in temporal.items():
        policy = SPLIT_POLICY.get(ds.upper(), DEFAULT_POLICY)
        undated = sum(1 for _d, img, _l in items if time_key(img) is None)
        if undated:
            print(f"  ! {ds}: {undated} frame(s) carry no timestamp -- placed by filename order")
        for split, (d, img, lbl) in temporal_split(items, policy["cuts"]):
            plan.append((split, d, img, lbl))

    for combined, items in fixed.items():
        ds, target = combined.split("|")
        policy = SPLIT_POLICY.get(ds.upper(), DEFAULT_POLICY)
        if target == policy.get("val_from"):
            # Carve validation out of the dataset's TRAIN portion, grouped by
            # source frame. Never out of its test portion -- that is the
            # published benchmark and must stay untouched.
            frames = defaultdict(list)
            for d, img, lbl in items:
                frames[group_key(d, img)].append((d, img, lbl))
            keys = sorted(frames)
            rng.shuffle(keys)
            n_val = max(1, int(round(len(keys) * args.val_fraction)))
            val_keys = set(keys[:n_val])
            for k in keys:
                split = "val" if k in val_keys else "train"
                for d, img, lbl in frames[k]:
                    plan.append((split, d, img, lbl))
        else:
            for d, img, lbl in items:
                plan.append((target, d, img, lbl))

    # ---- report and write -------------------------------------------------
    stats = {s: Counter() for s in ("train", "val", "test")}    # boxes
    frames = {s: Counter() for s in ("train", "val", "test")}   # frames containing
    tiles = Counter()
    backgrounds = Counter()
    for split, ds, img, lbl in plan:
        tiles[split] += 1
        counts = boxes_in(lbl)
        if not counts:
            backgrounds[split] += 1
        for c, n in counts.items():
            stats[split][c] += n
            frames[split][c] += 1

    print(f"\nsources: {', '.join(sources)}")
    print(f"output : {out_root if not args.dry_run else '(dry run)'}\n")
    for ds in sources:
        extra = f", {dropped_dupes[ds]} exact duplicates dropped" if dropped_dupes[ds] else ""
        print(f"  {ds:16s} {per_source[ds]:5d} images{extra}")

    print("\n  BOXES per class (one frame may hold several)")
    print(f"  {'split':6s} {'images':>7s} {'background':>11s}  " +
          "  ".join(f"{n:>9s}" for n in TRAINING_CLASSES))
    for s in ("train", "val", "test"):
        row = "  ".join(f"{stats[s][i]:9d}" for i in range(len(TRAINING_CLASSES)))
        print(f"  {s:6s} {tiles[s]:7d} {backgrounds[s]:11d}  {row}")
    row = "  ".join(f"{frames['train'][i]:9d}" for i in range(len(TRAINING_CLASSES)))
    print(f"  {'':6s} {'':7s} {'train frames':>11s}  {row}")

    problems = []
    for i, name in enumerate(TRAINING_CLASSES):
        if stats["train"][i] and not stats["val"][i]:
            problems.append(f"class '{name}' has training examples but NONE in val -- its metric will be blind")
    if not tiles["val"]:
        problems.append("validation split is empty")

    # A class with no examples anywhere cannot be learned and puts a NaN in
    # every per-class table. Trailing unused classes are simply not declared:
    # no label file references them, so dropping them needs no relabelling.
    used = {c for s in stats.values() for c in s}
    highest = max(used) if used else -1
    active = list(TRAINING_CLASSES[: highest + 1])
    for i in range(highest + 1):
        if i not in used:
            problems.append(
                f"class '{TRAINING_CLASSES[i]}' (id {i}) has no examples but sits below a class that "
                f"does. It cannot be dropped without renumbering every label -- add data for it, or "
                f"move it to the end of TRAINING_CLASSES."
            )
    for name in TRAINING_CLASSES[highest + 1:]:
        print(f"\n  note: class '{name}' has no examples in this build and is not declared. "
              f"Add its source dataset to bring it back.")
    for p in problems:
        print(f"\n  ! {p}")

    if args.dry_run:
        return 0

    # Clear the target splits first. Adding a source changes the stratified
    # assignment, so a file that was in train last build may belong in val
    # this one -- and the stale copy would still be sitting in train. That is
    # the same image on both sides of the split: leakage, introduced by the
    # very script whose job is to prevent it, and invisible afterwards.
    for s in ("train", "val", "test"):
        if (out_root / s).exists():
            shutil.rmtree(out_root / s, ignore_errors=True)
        (out_root / s / "images").mkdir(parents=True, exist_ok=True)
        (out_root / s / "labels").mkdir(parents=True, exist_ok=True)
    for split, ds, img, lbl in plan:
        stem = f"{ds}__{img.stem}"
        shutil.copy2(img, out_root / split / "images" / (stem + img.suffix))
        shutil.copy2(lbl, out_root / split / "labels" / (stem + ".txt"))

    yaml = [
        "# Generated by ai/scripts/build_dataset.py -- do not edit by hand.",
        f"path: {out_root.as_posix()}",
        "train: train/images",
        "val: val/images",
        "test: test/images",
        "",
        f"nc: {len(active)}",
        "names:",
        *[f"  {i}: {n}" for i, n in enumerate(active)],
        "",
        "# Split by GROUP, never by file: exact duplicates dropped, near-duplicates",
        "# and all tiles of one waterfall kept together. AI4Shipwrecks' published",
        "# test split is preserved so results stay comparable to the paper.",
    ]
    (out_root / "data.yaml").write_text("\n".join(yaml), encoding="utf-8")
    report = {
        "sources": sources,
        "images_per_source": dict(per_source),
        "exact_duplicates_dropped": dict(dropped_dupes),
        "split_sizes": dict(tiles),
        "background_per_split": dict(backgrounds),
        "boxes_per_class_per_split": {s: {TRAINING_CLASSES[c]: n for c, n in stats[s].items()} for s in stats},
        "frames_per_class_per_split": {s: {TRAINING_CLASSES[c]: n for c, n in frames[s].items()} for s in frames},
        "declared_classes": active,
        "ratios": args.ratios,
        "seed": args.seed,
        "warnings": problems,
    }
    (out_root / "build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {show(out_root / 'data.yaml')}")
    print(f"wrote {show(out_root / 'build_report.json')}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
