"""Score a trained detector on a sample of its OWN training split.

    python ai/scripts/evaluate_trainfit.py
    python ai/scripts/evaluate_trainfit.py --mode uniform --n 1200
    python ai/scripts/evaluate_trainfit.py --weights .../gv7.4-p2/weights/best.pt

Answers one question and no others: is this model underfitting or overfitting?
Every other diagnostic in this repo measures the model on data it has never
seen, which tells you how well it generalises and cannot distinguish "did not
learn" from "learned and failed to transfer". The train-split score separates
them:

    train mAP50 high,  val/test low   -> variance. Regularise, stop earlier.
    train mAP50 low,   val/test low   -> bias. More capacity/resolution, or
                                         fix the class imbalance.

This number is NEVER a result to quote. It is measured on training data by
design and is meaningless as a capability claim -- `docs/MODEL_CAPABILITY_
EVIDENCE.md` must keep reporting test only.

The three things that make this harder than it sounds
-----------------------------------------------------
1. THE TRAIN SPLIT HAS GROWN SINCE THE WEIGHTS WERE MADE. `dataset_version` is
   keyed on the test split alone -- by design, so train may grow -- so nothing
   stops `data/processed/train` from holding frames the weights never saw.
   gv5 trained on 12,472 frames from 8 sources; the directory now holds 13,896
   from 10. Scoring the directory as-is silently mixes 1,424 held-out frames
   into a train-fit measurement and drags it toward the val number, i.e.
   towards the wrong conclusion. `--sources` (from the run's own
   provenance.json `images_per_source`) is the fix, and the default excludes
   the two sources added after gv5.

2. BACKGROUND FRAMES DECIDE PRECISION. 48.4% of the train split carries no
   annotation. Sample only object-bearing frames and precision has nothing to
   be wrong about, so it climbs for a reason that has nothing to do with
   fitting. Both modes below therefore keep the split's own background rate.

3. THE LABEL CACHE LIVES IN THE TRAINING TREE. Ultralytics writes
   `<split>/labels.cache` next to the labels, so a subset evaluation would
   leave a subset cache behind in a directory other sessions train from. The
   cache is hash-checked and would only be rebuilt, not misread, but this
   script still saves and restores it so the tree is left byte-identical.

Sampling modes
--------------
`stratified` (default) equalises FRAMES PER CLASS across the five classes, then
tops up with background at the split's own rate. `ghost_net` has 51 train
frames and `ghost_pot` 4,274; a uniform sample of 1,200 draws roughly four net
frames, so the per-class train number for the worst class would be noise, and
the worst class is the one the verdict hinges on.

`uniform` draws from the eligible pool untouched. It mirrors what the model
actually trained on, so the OVERALL number is the honest one, but its per-class
rows for the rare classes are not interpretable.

They answer different questions, they disagree for a knowable reason, and
running both costs one extra inference pass. `--mode both` is supported.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: The training tree, not this checkout. `ai/data/processed` here is empty --
#: this is a data-free demo checkout and always has been.
DEFAULT_DATA_ROOT = Path("E:/New folder/ai/data/processed")
DEFAULT_WEIGHTS = Path("E:/New folder/ai/experiments/gv5-yolo11s/weights/best.pt")

#: Sources added to the train split AFTER gv5 was trained. Excluded by default
#: so the sample contains only frames the gv5 weights actually saw. Override
#: with --sources when scoring a later run; read the truth out of that run's
#: provenance.json `dataset_build.images_per_source`.
GV5_EXCLUDED_SOURCES = ("GHOSTNET-SYNTH", "PLANE-HAND")

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def source_of(name: str) -> str:
    """Source dataset name from a processed filename (`SOURCE__rest.ext`)."""
    return name.split("__", 1)[0]


def read_classes(label_path: Path) -> set[int]:
    """Class ids present in a YOLO label file. Missing or empty -> background."""
    if not label_path.exists():
        return set()
    ids: set[int] = set()
    for line in label_path.read_text().splitlines():
        line = line.strip()
        if line:
            ids.add(int(float(line.split()[0])))
    return ids


def index_split(root: Path, split: str, exclude: tuple[str, ...]) -> tuple[list, dict, list]:
    """Return (object_frames, class_to_frames, background_frames).

    `object_frames` and `background_frames` hold (image_path, class_ids) pairs.
    """
    images_dir = root / split / "images"
    labels_dir = root / split / "labels"
    if not images_dir.is_dir():
        sys.exit(f"no such split: {images_dir}")

    objects: list[tuple[Path, set[int]]] = []
    background: list[tuple[Path, set[int]]] = []
    class_to_frames: dict[int, list[Path]] = defaultdict(list)
    skipped: Counter[str] = Counter()

    for img in sorted(images_dir.iterdir()):
        if img.suffix.lower() not in IMAGE_EXTS:
            continue
        src = source_of(img.name)
        if src in exclude:
            skipped[src] += 1
            continue
        ids = read_classes(labels_dir / f"{img.stem}.txt")
        if ids:
            objects.append((img, ids))
            for cid in ids:
                class_to_frames[cid].append(img)
        else:
            background.append((img, ids))

    if skipped:
        print("  excluded (not seen by these weights): "
              + ", ".join(f"{k} {v}" for k, v in sorted(skipped.items())))
    return objects, class_to_frames, background


def sample_stratified(class_to_frames, objects, n_objects, names, rng):
    """Equal frames per class, smallest class first, leftovers redistributed.

    Taking the smallest class first matters: `ghost_net` cannot fill its quota
    (51 frames exist), and giving its shortfall back to the classes that can
    fill it keeps the sample at the requested size instead of quietly shrinking.
    """
    remaining_classes = sorted(class_to_frames, key=lambda c: len(class_to_frames[c]))
    budget = n_objects
    chosen: set[Path] = set()
    per_class_taken: dict[str, int] = {}

    for i, cid in enumerate(remaining_classes):
        quota = budget // (len(remaining_classes) - i)
        pool = [p for p in class_to_frames[cid] if p not in chosen]
        take = min(quota, len(pool))
        picked = rng.sample(pool, take) if take else []
        chosen.update(picked)
        budget -= take
        per_class_taken[names[cid]] = take

    # A frame can carry several classes, so `chosen` may be short of target
    # even after redistribution. Top up from any object frame.
    if budget > 0:
        spare = [p for p, _ in objects if p not in chosen]
        chosen.update(rng.sample(spare, min(budget, len(spare))))
    return list(chosen), per_class_taken


def compose(objects, class_to_frames, background, n, mode, names, rng):
    """Pick `n` frames, preserving the split's background rate."""
    total = len(objects) + len(background)
    bg_rate = len(background) / total if total else 0.0
    n_bg = min(round(n * bg_rate), len(background))
    n_obj = min(n - n_bg, len(objects))

    if mode == "stratified":
        obj_paths, per_class_taken = sample_stratified(
            class_to_frames, objects, n_obj, names, rng)
    else:
        obj_paths = [p for p, _ in rng.sample(objects, n_obj)]
        per_class_taken = None

    bg_paths = [p for p, _ in rng.sample(background, n_bg)]
    return obj_paths + bg_paths, {
        "requested": n,
        "object_frames": len(obj_paths),
        "background_frames": len(bg_paths),
        "background_rate_in_sample": round(len(bg_paths) / max(1, len(obj_paths) + len(bg_paths)), 4),
        "background_rate_in_split": round(bg_rate, 4),
        "frames_per_class_taken": per_class_taken,
    }


def count_boxes(paths, labels_dir, names):
    """Boxes per class actually inside the sample -- the support for each row."""
    counts: Counter[str] = Counter()
    for img in paths:
        lp = labels_dir / f"{img.stem}.txt"
        if not lp.exists():
            continue
        for line in lp.read_text().splitlines():
            if line.strip():
                counts[names[int(float(line.split()[0]))]] += 1
    return dict(counts)


def run_val(weights, yaml_path, imgsz, batch, conf, project, name):
    from ultralytics import YOLO

    model = YOLO(str(weights))
    r = model.val(data=str(yaml_path), split="val", imgsz=imgsz, batch=batch,
                  conf=conf, plots=False, verbose=False, save_json=False,
                  project=str(project), name=name, exist_ok=True)
    box = r.box
    out = {
        "map50": float(box.map50),
        "map50_95": float(box.map),
        "precision": float(box.mp),
        "recall": float(box.mr),
        "per_class": {},
    }
    for i, cid in enumerate(r.box.ap_class_index):
        p, rec, ap50, ap = box.p[i], box.r[i], box.ap50[i], box.ap[i]
        out["per_class"][r.names[int(cid)]] = {
            "precision": float(p), "recall": float(rec),
            "map50": float(ap50), "map50_95": float(ap),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    ap.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    ap.add_argument("--split", default="train")
    ap.add_argument("--n", type=int, default=1200)
    ap.add_argument("--mode", choices=("stratified", "uniform", "both"), default="both")
    ap.add_argument("--sources", nargs="*", default=None,
                    help="Whitelist of sources the weights saw. Default: all "
                         f"except {', '.join(GV5_EXCLUDED_SOURCES)}.")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=2,
                    help="2 by default: the 3050 has 4 GB and is also the demo machine.")
    ap.add_argument("--conf", type=float, default=0.001,
                    help="mAP needs the full curve; 0.001 matches training-time val.")
    ap.add_argument("--also-reference-split", default="val",
                    help="Re-score this split in the same session so the "
                         "comparison is free of version drift. '' to skip.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "ai" / "experiments" / "trainfit" / "trainfit.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compose and report the sample; run no inference.")
    args = ap.parse_args()

    import yaml

    src_yaml = yaml.safe_load((args.data_root / "data.yaml").read_text())
    names = {int(k): v for k, v in src_yaml["names"].items()}
    rng = random.Random(args.seed)

    exclude: tuple[str, ...] = ()
    if args.sources is None:
        exclude = GV5_EXCLUDED_SOURCES
    print(f"indexing {args.data_root / args.split} ...")
    objects, class_to_frames, background = index_split(args.data_root, args.split, exclude)
    if args.sources is not None:
        keep = set(args.sources)
        objects = [(p, i) for p, i in objects if source_of(p.name) in keep]
        background = [(p, i) for p, i in background if source_of(p.name) in keep]
        class_to_frames = {c: [p for p in v if source_of(p.name) in keep]
                           for c, v in class_to_frames.items()}
        class_to_frames = {c: v for c, v in class_to_frames.items() if v}
    print(f"  eligible: {len(objects)} object frames, {len(background)} background")
    for cid in sorted(class_to_frames, key=lambda c: -len(class_to_frames[c])):
        print(f"    {names[cid]:<10} {len(class_to_frames[cid])} frames")

    labels_dir = args.data_root / args.split / "labels"
    work = args.out.parent
    work.mkdir(parents=True, exist_ok=True)

    modes = ("stratified", "uniform") if args.mode == "both" else (args.mode,)
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "weights": str(args.weights),
        "data_root": str(args.data_root),
        "split_scored": args.split,
        "excluded_sources": list(exclude),
        "imgsz": args.imgsz,
        "conf": args.conf,
        "seed": args.seed,
        "caveat": "Scored ON TRAINING DATA. Diagnostic only -- never a capability claim.",
        "samples": {},
    }

    cache = args.data_root / args.split / "labels.cache"
    backup = work / f"{args.split}.labels.cache.bak"
    if cache.exists():
        shutil.copy2(cache, backup)
        print(f"  saved existing {cache.name} -> {backup}")

    try:
        for mode in modes:
            paths, composition = compose(objects, class_to_frames, background,
                                         args.n, mode, names, rng)
            composition["boxes_per_class"] = count_boxes(paths, labels_dir, names)
            listing = work / f"{args.split}_{mode}_{args.n}.txt"
            listing.write_text("\n".join(str(p).replace("\\", "/") for p in paths) + "\n")
            yaml_path = work / f"{args.split}_{mode}.yaml"
            yaml_path.write_text(yaml.safe_dump({
                "path": str(args.data_root).replace("\\", "/"),
                "train": str(listing).replace("\\", "/"),
                "val": str(listing).replace("\\", "/"),
                "nc": len(names),
                "names": names,
            }, sort_keys=False))

            print(f"\n[{mode}] {len(paths)} frames "
                  f"({composition['object_frames']} object / "
                  f"{composition['background_frames']} background), "
                  f"boxes: {composition['boxes_per_class']}")
            entry = {"composition": composition, "image_list": str(listing)}
            if not args.dry_run:
                entry["metrics"] = run_val(args.weights, yaml_path, args.imgsz,
                                           args.batch, args.conf, work, f"val_{mode}")
            report["samples"][mode] = entry

        if args.also_reference_split and not args.dry_run:
            ref = args.also_reference_split
            ref_yaml = work / f"reference_{ref}.yaml"
            ref_yaml.write_text(yaml.safe_dump({
                "path": str(args.data_root).replace("\\", "/"),
                "train": f"{ref}/images",
                "val": f"{ref}/images",
                "nc": len(names),
                "names": names,
            }, sort_keys=False))
            print(f"\n[reference] full {ref} split, same session and settings")
            report["reference"] = {
                "split": ref,
                "metrics": run_val(args.weights, ref_yaml, args.imgsz, args.batch,
                                   args.conf, work, f"val_reference_{ref}"),
            }
    finally:
        if backup.exists():
            shutil.copy2(backup, cache)
            print(f"restored {cache}")

    args.out.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {args.out}")

    if not args.dry_run:
        print("\n--- verdict inputs ---")
        for mode, entry in report["samples"].items():
            m = entry["metrics"]
            print(f"  {args.split}/{mode:<11} mAP50 {m['map50']:.3f}  "
                  f"R {m['recall']:.3f}  P {m['precision']:.3f}")
        if "reference" in report:
            m = report["reference"]["metrics"]
            print(f"  {report['reference']['split']}/full       "
                  f"mAP50 {m['map50']:.3f}  R {m['recall']:.3f}  P {m['precision']:.3f}")


if __name__ == "__main__":
    main()
