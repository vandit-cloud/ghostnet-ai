"""Convert SubPipeMini2's side-scan sonar into tiles this project can train on.

    python ai/scripts/subpipe_to_yolo.py --dry-run
    python ai/scripts/subpipe_to_yolo.py
    python ai/scripts/subpipe_to_yolo.py --neg-ratio 0.25

Reads  ai/data/raw/research/SubPipeMini2/**/SSS_{HF,LF}_images/
Writes ai/data/interim/SUBPIPE/train/{images,labels}

Four things make SubPipe unusable as it ships, and this handles all four
--------------------------------------------------------------------------
1. Most of the archive is NOT sonar. Cam0_images holds 16,200 optical camera
   photographs and Cam1_images another 430. Only SSS_HF_images (1,011) and
   SSS_LF_images (1,055) are side-scan. Pointing an importer at the archive root
   would ingest camera imagery as sonar.

2. The frames are amber false-colour. Our training data is greyscale, and the
   difference is not cosmetic -- a colourised sonar image of a B-25 bomber
   produced zero detections from our model, and the same image converted to
   greyscale produced output immediately. Everything is converted on the way in.

3. The frames are waterfalls, 2500x500 (LF) and 5000x500 (HF). Fed whole to a
   640px detector they are squeezed by 4-8x across-track and a pipeline a few
   dozen pixels wide disappears. They are tiled square at the frame height, so
   aspect ratio is preserved and YOLO's own resize does the rest.

4. Two label rows carry the literal string "Pipeline" where a class id belongs.
   A naive int() crashes on them.

Written into TRAIN ONLY, on purpose
-----------------------------------
`gv-yolo11s` and `gv2-yolo11s` are comparable only because the test split is
byte-identical between them. Adding SubPipe frames to val or test would silently
end that, and every previously reported number with it. New data goes where it
can help the model without moving the measuring stick: build_dataset.py routes
this source entirely to train via SPLIT_POLICY.

Negatives default to NONE
-------------------------
Tiling these waterfalls yields roughly ten empty tiles for every occupied one.
Training background already sits at 47%, and raising it from 30% to 47% last
time tripled precision while nearly halving recall. More empty seabed is not the
missing ingredient, so --neg-ratio defaults to 0.0 and must be asked for.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.taxonomy import TRAINING_CLASSES  # noqa: E402

RAW = AI_ROOT / "data" / "raw" / "research" / "SubPipeMini2"
INTERIM = AI_ROOT / "data" / "interim" / "SUBPIPE"
SONAR_DIRS = ("SSS_HF_images", "SSS_LF_images")


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def read_boxes(label: Path) -> list[tuple[float, float, float, float]]:
    """YOLO rows -> (cx, cy, w, h) normalised. Class is ignored.

    SubPipe has exactly one object type, and two rows in the archive carry the
    literal string "Pipeline" in the class column instead of 0. Reading the
    class at all buys nothing and crashes on those rows, so it is skipped.
    """
    out = []
    for row in label.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = row.split()
        if len(parts) < 5:
            continue
        try:
            cx, cy, w, h = (float(v) for v in parts[1:5])
        except ValueError:
            continue
        out.append((cx, cy, w, h))
    return out


def to_grey(path: Path) -> np.ndarray | None:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 3:
        img = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    return img


def tile_boxes(boxes, W, H, x0, y0, size, min_visible):
    """Clip normalised whole-frame boxes into one tile. Returns YOLO rows."""
    rows = []
    for cx, cy, w, h in boxes:
        bx1, by1 = (cx - w / 2) * W, (cy - h / 2) * H
        bx2, by2 = (cx + w / 2) * W, (cy + h / 2) * H
        ix1, iy1 = max(bx1, x0), max(by1, y0)
        ix2, iy2 = min(bx2, x0 + size), min(by2, y0 + size)
        if ix2 <= ix1 or iy2 <= iy1:
            continue
        full = (bx2 - bx1) * (by2 - by1)
        if full <= 0 or ((ix2 - ix1) * (iy2 - iy1)) / full < min_visible:
            # An edge sliver teaches the model that a fragment is a whole
            # object. The overlap between tiles keeps it intact elsewhere.
            continue
        rows.append((
            ((ix1 + ix2) / 2 - x0) / size,
            ((iy1 + iy2) / 2 - y0) / size,
            (ix2 - ix1) / size,
            (iy2 - iy1) / size,
        ))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert SubPipeMini2 SSS to YOLO tiles.")
    ap.add_argument("--src", default=str(RAW))
    ap.add_argument("--out", default=str(INTERIM))
    ap.add_argument("--map-to", default="debris", choices=TRAINING_CLASSES,
                    help="training class for pipelines. 'debris' keeps the 4-class "
                         "taxonomy and the frozen test split; a dedicated 'pipeline' "
                         "class would need taxonomy.py edited and would carry zero "
                         "test instances, which is the NaN problem ghost_net has.")
    ap.add_argument("--tile", type=int, default=0,
                    help="tile size in px; 0 = the frame height, giving square tiles")
    ap.add_argument("--overlap", type=float, default=0.25)
    ap.add_argument("--min-visible", type=float, default=0.35,
                    help="keep a clipped box only if this fraction survives")
    ap.add_argument("--min-box-side", type=int, default=10,
                    help="drop boxes thinner than this in tile pixels")
    ap.add_argument("--neg-ratio", type=float, default=0.0,
                    help="empty tiles kept per occupied tile. 0 = none; see the "
                         "module docstring before raising it")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        print(f"no SubPipe at {src}")
        return 1

    cls_id = TRAINING_CLASSES.index(args.map_to)
    rng = random.Random(args.seed)

    frames = []
    for name in SONAR_DIRS:
        for d in src.rglob(name):
            img_dir, lbl_dir = d / "Image", d / "YOLO_Annotation"
            if not (img_dir.is_dir() and lbl_dir.is_dir()):
                continue
            for img in sorted(img_dir.iterdir()):
                lbl = lbl_dir / (img.stem + ".txt")
                if lbl.exists():
                    frames.append((name, img, lbl))

    if not frames:
        print(f"no SSS_HF_images / SSS_LF_images with labels under {src}")
        print("Note: Cam0_images and Cam1_images are optical camera data, not sonar.")
        return 1

    print(f"\n  source   {show(src)}")
    print(f"  frames   {len(frames)} labelled sonar frames")
    print(f"  class    pipelines -> '{args.map_to}' (id {cls_id})")
    print(f"  output   {show(Path(args.out))}/train" + ("   (dry run)" if args.dry_run else ""))
    print("  greyscale conversion ON; SubPipe ships amber false-colour\n")

    out_img = Path(args.out) / "train" / "images"
    out_lbl = Path(args.out) / "train" / "labels"
    if not args.dry_run:
        out_img.mkdir(parents=True, exist_ok=True)
        out_lbl.mkdir(parents=True, exist_ok=True)

    stats = {"frames": 0, "unreadable": 0, "tiles_considered": 0,
             "positive": 0, "negative_kept": 0, "boxes": 0,
             "boxes_dropped_small": 0, "dead_tiles": 0}
    negatives = []

    for group, img_path, lbl_path in frames:
        grey = to_grey(img_path)
        if grey is None:
            stats["unreadable"] += 1
            continue
        stats["frames"] += 1
        H, W = grey.shape[:2]
        size = args.tile or H
        stride = max(1, int(size * (1 - args.overlap)))
        boxes = read_boxes(lbl_path)

        for x0 in list(range(0, max(W - size, 0) + 1, stride)) or [0]:
            y0 = 0
            stats["tiles_considered"] += 1
            tile = grey[y0:y0 + size, x0:x0 + size]
            if tile.shape[0] < size or tile.shape[1] < size:
                tile = cv2.copyMakeBorder(tile, 0, size - tile.shape[0],
                                          0, size - tile.shape[1],
                                          cv2.BORDER_CONSTANT, value=0)
            # A flat tile is padding or off-swath, not seabed.
            if float(tile.std()) < 3.0:
                stats["dead_tiles"] += 1
                continue

            rows = tile_boxes(boxes, W, H, x0, y0, size, args.min_visible)
            kept = []
            for cx, cy, w, h in rows:
                if min(w * size, h * size) < args.min_box_side:
                    stats["boxes_dropped_small"] += 1
                    continue
                kept.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

            stem = f"{group}_{img_path.stem}__x{x0}_y{y0}"
            if kept:
                stats["positive"] += 1
                stats["boxes"] += len(kept)
                if not args.dry_run:
                    cv2.imwrite(str(out_img / f"{stem}.png"), tile)
                    (out_lbl / f"{stem}.txt").write_text("\n".join(kept) + "\n", encoding="utf-8")
            elif rows:
                # Every box on this tile was dropped as too small. Writing it as
                # a negative would teach the model that pipelines are seabed.
                continue
            else:
                negatives.append((stem, tile))

    budget = int(stats["positive"] * args.neg_ratio)
    rng.shuffle(negatives)
    for stem, tile in negatives[:budget]:
        stats["negative_kept"] += 1
        if not args.dry_run:
            cv2.imwrite(str(out_img / f"{stem}.png"), tile)
            (out_lbl / f"{stem}.txt").write_text("", encoding="utf-8")

    print(f"    {stats['frames']} frames read ({stats['unreadable']} unreadable)")
    print(f"    {stats['tiles_considered']} tiles considered")
    print(f"    {stats['positive']} tiles with a pipeline, {stats['boxes']} boxes")
    print(f"    {stats['negative_kept']} empty tiles kept (of {len(negatives)}, --neg-ratio {args.neg_ratio})")
    print(f"    {stats['dead_tiles']} flat tiles rejected as padding or off-swath")
    print(f"    {stats['boxes_dropped_small']} boxes dropped below --min-box-side {args.min_box_side}px")

    if args.dry_run:
        print("\n  dry run: nothing written.")
        return 0

    yaml = [
        "# Generated by ai/scripts/subpipe_to_yolo.py -- do not edit by hand.",
        f"path: {Path(args.out).as_posix()}",
        "train: train/images",
        "val: train/images",
        "",
        f"nc: {len(TRAINING_CLASSES)}",
        "names:",
        *[f"  {i}: {n}" for i, n in enumerate(TRAINING_CLASSES)],
        "",
        "# TRAIN ONLY, deliberately. build_dataset.py routes this source entirely",
        "# to train so the frozen val/test splits stay comparable with earlier runs.",
    ]
    (Path(args.out) / "data.yaml").write_text("\n".join(yaml), encoding="utf-8")
    (Path(args.out) / "tiling_report.json").write_text(
        json.dumps({**stats, "args": vars(args)}, indent=2), encoding="utf-8")

    print(f"\nwrote {show(Path(args.out))}/data.yaml")
    print("Next: python ai/scripts/build_dataset.py --dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
