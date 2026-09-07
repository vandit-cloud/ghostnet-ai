"""Build the single-class ghost_net SEGMENTATION dataset (D2 / Track D).

    python ai/scripts/build_net_seg_dataset.py
    python ai/scripts/build_net_seg_dataset.py --dry-run

Reads  ai/data/annotate/ghost_net_seg/{images,labels}   (73 chips, 425 polygons)
       ai/data/processed/{train,val,test}/images/       (for the split ONLY)
Writes ai/data/net_seg/{train,val,test}/{images,labels} + data.yaml + report

Why a separate dataset instead of a class in the main one
---------------------------------------------------------
Ultralytics segmentation requires EVERY label in the dataset to be a polygon.
The other four classes exist only as boxes, and the raw imagery needed to
re-derive them was pruned in ad70122. Turning those boxes into 4-point
rectangles to satisfy the format would teach the model that debris is
rectangular -- fake segmentation that damages the classes which currently work.
So `ghost_net` gets its own single-class segmentation model and gv5 keeps
handling the other four unchanged.

The split is INHERITED, never recomputed
----------------------------------------
Which chip sits in train/val/test is read back from the existing processed
dataset by filename (`GHOSTNET-HAND__<stem>.png`). Re-splitting 73 chips
randomly would put a chip in test that gv5 trained on, and every comparison
after that would be measuring memorisation. Inheriting also means the 11 test
chips here are the same 11 the detector was scored on, so the two rulers at
least look at the same seabed.

What this dataset can and cannot say (read before quoting a number)
-------------------------------------------------------------------
Its test split is 11 chips. Per EXPERIMENT_GV7_PLAN.md section 4.3 that
supports an upper bound and little else. A segmentation score from here is NOT
comparable with gv5's mAP50: different task, different label geometry,
different metric. Anyone placing the two side by side is comparing rulers, not
models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
ANNOTATE = AI_ROOT / "data" / "annotate" / "ghost_net_seg"
PROCESSED = AI_ROOT / "data" / "processed"
OUT = AI_ROOT / "data" / "net_seg"
SPLITS = ("train", "val", "test")
PREFIX = "GHOSTNET-HAND__"

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def split_of(stem: str) -> str | None:
    """Which split the existing dataset put this chip in, or None if absent."""
    for split in SPLITS:
        d = PROCESSED / split / "images"
        if not d.is_dir():
            continue
        for suf in IMAGE_SUFFIXES:
            if (d / f"{PREFIX}{stem}{suf}").exists():
                return split
    return None


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=AI_ROOT.parent,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the ghost_net segmentation dataset")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out_root = Path(args.out)

    images = sorted(p for p in (ANNOTATE / "images").iterdir()
                    if p.suffix.lower() in IMAGE_SUFFIXES) if (ANNOTATE / "images").is_dir() else []
    if not images:
        print(f"no images under {ANNOTATE / 'images'}")
        return 1

    labels_dir = ANNOTATE / "labels"
    if not labels_dir.is_dir():
        print(f"no labels under {labels_dir} -- run labelme_to_yoloseg.py first")
        return 1

    plan: dict[str, list[tuple[Path, Path]]] = {s: [] for s in SPLITS}
    missing_label, missing_split, polygons = [], [], 0

    for img in images:
        lbl = labels_dir / f"{img.stem}.txt"
        if not lbl.exists():
            missing_label.append(img.stem)
            continue
        split = split_of(img.stem)
        if split is None:
            # Refuse to guess. A chip with no home in the existing dataset would
            # otherwise be silently dropped or silently dumped into train.
            missing_split.append(img.stem)
            continue
        polygons += len([l for l in lbl.read_text(encoding="utf-8").split("\n") if l.strip()])
        plan[split].append((img, lbl))

    if missing_label:
        print(f"ERROR: {len(missing_label)} image(s) have no label: {missing_label[:8]}")
        return 1
    if missing_split:
        print(f"ERROR: {len(missing_split)} chip(s) are not in the processed dataset, "
              f"so their split is unknown: {missing_split[:8]}")
        return 1

    print(f"\nsource : {ANNOTATE}")
    print(f"output : {out_root if not args.dry_run else '(dry run)'}")
    for s in SPLITS:
        print(f"  {s:5s} {len(plan[s]):3d} chip(s)")
    print(f"  total {sum(len(v) for v in plan.values()):3d} chips, {polygons} polygons")

    if args.dry_run:
        return 0

    if out_root.exists():
        shutil.rmtree(out_root)
    for s in SPLITS:
        (out_root / s / "images").mkdir(parents=True, exist_ok=True)
        (out_root / s / "labels").mkdir(parents=True, exist_ok=True)
        for img, lbl in plan[s]:
            shutil.copy2(img, out_root / s / "images" / img.name)
            shutil.copy2(lbl, out_root / s / "labels" / lbl.name)

    # Ultralytics resolves train/val/test relative to `path`.
    (out_root / "data.yaml").write_text(
        "# Single-class ghost_net SEGMENTATION dataset (D2, Track D).\n"
        "# Built by ai/scripts/build_net_seg_dataset.py -- do not hand-edit.\n"
        "# NOT comparable with the detection dataset: different task and metric.\n"
        f"path: {out_root.as_posix()}\n"
        "train: train/images\n"
        "val: val/images\n"
        "test: test/images\n"
        "names:\n"
        "  0: ghost_net\n",
        encoding="utf-8",
    )

    digest = hashlib.sha256()
    for s in SPLITS:
        for _, lbl in sorted(plan[s]):
            digest.update(lbl.read_bytes())
    version = f"netseg-{len(plan['train'])}/{len(plan['val'])}/{len(plan['test'])}-{digest.hexdigest()[:12]}"

    (out_root / "build_report.json").write_text(json.dumps({
        "dataset_version": version,
        "task": "segment",
        "classes": ["ghost_net"],
        "splits": {s: len(plan[s]) for s in SPLITS},
        "polygons": polygons,
        "split_inherited_from": str(PROCESSED),
        "source": str(ANNOTATE),
        "git_commit": git_commit(),
        "caveat": ("test split is 11 chips; supports an upper bound only. "
                   "Not comparable with gv5 mAP50 -- different task and ruler."),
    }, indent=2), encoding="utf-8")

    print(f"\ndataset_version: {version}")
    print(f"wrote {out_root / 'data.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
