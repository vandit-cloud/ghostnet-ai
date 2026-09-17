"""Write a despeckled copy of the processed dataset, for the despeckle-TRAINED run.

    python ai/scripts/build_despeckled.py --dry-run
    python ai/scripts/build_despeckled.py

Why a whole second copy, rather than filtering in the dataloader
----------------------------------------------------------------
Transform symmetry: a transform is applied to training AND inference, or to
neither. The -13% result that put the speckle filter in the OFF position was
despeckling at INFERENCE ONLY, against a model trained on speckled data --
a domain mismatch, not a verdict on despeckling (see ghostnet/preprocess.py,
which records the same conclusion: "SETTLED: do not despeckle at inference for
a model trained without it. OPEN: a model TRAINED on despeckled data").

Materialising the filtered images means training, validation and test all see
the same domain, the filter runs once instead of every epoch, and the exact
pixels the run was trained on stay on disk to be re-examined afterwards.

What is deliberately NOT changed
--------------------------------
Filenames and label files are copied byte-identically. Only pixels change. That
is what keeps the comparison honest: the same frames carry the same boxes, so
per-class metrics measure the same objects being sought in filtered imagery.
It also means verify_dataset.py reports the SAME dataset_version here as for
the speckled root -- correct, because that fingerprint guards split membership,
not pixels. The preprocessing name is recorded separately in build_report.json
and belongs in the run's provenance.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(AI_ROOT / "scripts"))

PROCESSED = AI_ROOT / "data" / "processed"
DESPECKLED = AI_ROOT / "data" / "processed_despeckled"
SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Materialise a despeckled copy of the dataset.")
    ap.add_argument("--src", default=str(PROCESSED))
    ap.add_argument("--out", default=str(DESPECKLED))
    ap.add_argument("--filter", default="median3-v1",
                    help="a name from ghostnet.preprocess.PREPROCESSORS")
    ap.add_argument("--force", action="store_true",
                    help="re-filter images that already exist in the destination")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src, out = Path(args.src), Path(args.out)
    if not src.is_dir():
        print(f"no dataset at {src} -- run ai/scripts/build_dataset.py first")
        return 1

    from ghostnet.preprocess import PREPROCESSORS, preprocess

    if args.filter not in PREPROCESSORS:
        print(f"unknown filter {args.filter!r}; known: {', '.join(sorted(PREPROCESSORS))}")
        return 1
    if args.filter == "none":
        print("--filter none would copy the dataset unchanged. That is not an experiment.")
        return 1

    counts = {}
    for split in SPLITS:
        images = sorted(p for p in (src / split / "images").iterdir()
                        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES) \
            if (src / split / "images").is_dir() else []
        counts[split] = len(images)

    total = sum(counts.values())
    print(f"\n  source  {show(src)}")
    print(f"  dest    {show(out)}")
    print(f"  filter  {args.filter}")
    for split in SPLITS:
        print(f"  {split:<6} {counts[split]:>6} images")
    print(f"  total   {total:>6}")

    if args.dry_run:
        print("\ndry run: nothing written.")
        return 0

    import cv2

    started = time.time()
    written = skipped = failed = 0

    for split in SPLITS:
        src_images, src_labels = src / split / "images", src / split / "labels"
        dst_images, dst_labels = out / split / "images", out / split / "labels"
        if not src_images.is_dir():
            continue
        dst_images.mkdir(parents=True, exist_ok=True)
        dst_labels.mkdir(parents=True, exist_ok=True)

        images = sorted(p for p in src_images.iterdir()
                        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)

        for i, path in enumerate(images, 1):
            target = dst_images / path.name
            if target.exists() and not args.force:
                skipped += 1
            else:
                frame = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
                if frame is None:
                    # An unreadable frame is dropped from BOTH images and
                    # labels, or the split membership silently changes.
                    print(f"  ! unreadable, skipping: {path.name}")
                    failed += 1
                    continue
                if not cv2.imwrite(str(target), preprocess(frame, args.filter)):
                    print(f"  ! could not write: {target.name}")
                    failed += 1
                    continue
                written += 1

            label = src_labels / (path.stem + ".txt")
            if label.exists():
                shutil.copyfile(label, dst_labels / label.name)

            if i % 2000 == 0 or i == len(images):
                rate = (written + skipped) / max(time.time() - started, 1e-6)
                print(f"  {split:<6} {i:>6}/{len(images)}  ({rate:.0f} img/s)")

    # data.yaml, rewritten to point at this root. Generated, never hand-edited.
    yaml = [
        "# Generated by ai/scripts/build_despeckled.py -- do not edit by hand.",
        f"# Pixels filtered with {args.filter}; filenames and labels copied verbatim.",
        f"path: {out.as_posix()}",
        "train: train/images",
        "val: val/images",
        "test: test/images",
        "",
        "nc: 5",
        "names:",
        "  0: wreck",
        "  1: plane",
        "  2: debris",
        "  3: ghost_pot",
        "  4: ghost_net",
    ]
    (out / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")

    from _fingerprint import fingerprint_dataset

    fp = fingerprint_dataset(out)

    # Carry the source build's informational keys across. Downstream readers
    # (train.py's preflight) expect the shape build_dataset.py writes, and a
    # derived dataset should describe itself the same way its parent does.
    src_report = {}
    if (src / "build_report.json").is_file():
        src_report = json.loads((src / "build_report.json").read_text(encoding="utf-8"))

    report = {
        "derived_from": str(src),
        "preprocessing": args.filter,
        **{k: src_report[k] for k in (
            "sources", "images_per_source", "split_sizes", "background_per_split",
            "boxes_per_class_per_split", "frames_per_class_per_split",
            "declared_classes", "ratios", "seed", "warnings",
        ) if k in src_report},
        "note": ("Pixels filtered; filenames and labels are byte-identical to the source. "
                 "dataset_version therefore MATCHES the speckled root by design -- it "
                 "guards split membership, not pixels. Record `preprocessing` in the "
                 "run's provenance to tell the two apart."),
        "dataset_version": fp["dataset_version"],
        "fingerprints": fp,
    }
    (out / "build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    elapsed = time.time() - started
    print(f"\n  written {written}   skipped {skipped}   failed {failed}   in {elapsed/60:.1f} min")
    print(f"  dataset_version {fp['dataset_version']}")
    for split in SPLITS:
        s = fp["splits"][split]
        print(f"  {split:<6} {s['n_images']:>6} images  {s['n_labels']:>6} labels")

    src_fp = json.loads((src / "build_report.json").read_text(encoding="utf-8")) \
        if (src / "build_report.json").is_file() else {}
    expected = (src_fp.get("fingerprints") or {}).get("splits", {}).get("test", {})
    got = fp["splits"]["test"]
    if expected:
        same = all(expected.get(k) == got.get(k)
                   for k in ("n_images", "image_list", "label_content"))
        print(f"\n  test split identical to the speckled root: {'YES' if same else 'NO'}")
        if not same:
            print("  ! Frames or labels differ. The despeckled run would not be")
            print("    comparable to gv5. Investigate before training.")
            return 1

    print(f"\nwrote {show(out / 'data.yaml')}")
    print(f"wrote {show(out / 'build_report.json')}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
