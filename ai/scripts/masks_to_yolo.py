"""Tile full side-scan waterfalls and convert segmentation masks to YOLO boxes.

    python ai/scripts/masks_to_yolo.py --dataset AI4Shipwrecks
    python ai/scripts/masks_to_yolo.py --dataset AI4Shipwrecks --dry-run
    python ai/scripts/masks_to_yolo.py --dataset AI4Shipwrecks --neg-ratio 2.0

Reads  ai/data/raw/**/<DATASET>/<split>/{images,labels}/
Writes ai/data/interim/<DATASET>/<split>/{images,labels}/ + a report.

Why tiling is not optional here
-------------------------------
AI4Shipwrecks frames are 1728 px wide and up to 18,179 px tall, with a mean
foreground of 1.6%. Feeding one whole frame to a 640x640 detector shrinks a
wreck to a handful of pixels: the object is destroyed before training starts.
Tiling keeps the native resolution and turns one frame into many samples.

The three decisions that make or break this
-------------------------------------------
1. OBJECTS CUT BY A TILE EDGE. A wreck straddling a boundary appears in two
   tiles as two fragments. Labelling a 10% sliver as a whole wreck teaches the
   detector that a scrap of hull is a full object, which wrecks precision.
   Fragments keeping less than --min-visible of their area are dropped, and the
   overlapping stride means the object is still captured whole in a neighbour.

2. NEGATIVE BALANCE. At 1.6% foreground, almost every tile is empty. Keeping
   them all gives a dataset that is ~99% background, where predicting "nothing"
   scores brilliantly and learns nothing. Negatives are sampled to --neg-ratio
   times the number of positive tiles, preferring the ones nearest an object,
   which are the informative hard negatives rather than blank seabed.

3. DEAD TILES. Waterfalls carry the black water-column band down the middle and
   padding at the edges. A tile of near-uniform black is not seabed and teaches
   nothing; it is rejected on pixel variance before it can dilute the negatives.

Tile filenames encode their source frame and pixel origin, so every tile can be
traced back and, critically, so a later split can group tiles by source frame.
Two tiles from one waterfall in different splits is leakage.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.taxonomy import TRAINING_CLASSES, source_to_training  # noqa: E402

RAW_ROOT = AI_ROOT / "data" / "raw"
INTERIM_ROOT = AI_ROOT / "data" / "interim"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")

# What the mask's foreground means, per dataset. Only one entry today; adding a
# mask dataset is a line here rather than a code change.
DATASET_CLASS = {"AI4SHIPWRECKS": "shipwreck"}


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


@dataclass
class Report:
    frames: int = 0
    frames_all_negative: int = 0
    objects_found: int = 0
    objects_too_small: int = 0
    tiles_considered: int = 0
    tiles_positive: int = 0
    tiles_negative_kept: int = 0
    tiles_negative_available: int = 0
    tiles_rejected_dead: int = 0
    fragments_dropped: int = 0
    boxes_too_small: int = 0
    tiles_quarantined: int = 0
    boxes_written: int = 0
    per_split: dict = field(default_factory=dict)
    missing_masks: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["missing_masks"] = self.missing_masks[:50]
        return d


def find_dataset(name: str) -> Path | None:
    if not RAW_ROOT.exists():
        return None
    for bucket in RAW_ROOT.iterdir():
        if not bucket.is_dir():
            continue
        for child in bucket.iterdir():
            if child.is_dir() and child.name.lower() == name.lower():
                return child
    return None


def find_split_dirs(root: Path) -> list[tuple[str, Path, Path]]:
    """Locate every (split_name, images_dir, labels_dir) triple.

    Datasets nest inconsistently -- AI4Shipwrecks unpacks to
    AI4Shipwrecks/AI4Shipwrecks/train/... -- so search rather than assume.
    """
    out = []
    for images in sorted(root.rglob("images")):
        labels = images.parent / "labels"
        if images.is_dir() and labels.is_dir():
            rel = images.parent.relative_to(root)
            # Archives often nest the dataset inside a folder of the same name
            # (AI4Shipwrecks/AI4Shipwrecks/train/...). Dropping that repeat
            # keeps the split called "train" rather than "AI4Shipwrecks_train",
            # which matters because --merge-empty-into names a split by hand.
            parts = [p for p in rel.parts if p.lower() != root.name.lower()]
            # "extras/terrain" -> "extras_terrain"; keep the split identity
            name = "_".join(parts) if parts else "all"
            out.append((name, images, labels))
    return out


def mask_to_boxes(mask: np.ndarray, min_area: int) -> list[tuple[int, int, int, int]]:
    """Connected components of the mask foreground -> pixel boxes.

    A mask can hold several disjoint wrecks; one box around all of them would
    be mostly empty water. Components below min_area are annotation speckle.
    """
    binary = (mask > 0).astype(np.uint8)
    n, _lbl, stats, _cent = cv2.connectedComponentsWithStats(binary, connectivity=8)
    boxes = []
    for i in range(1, n):  # 0 is background
        x, y, w, h, area = stats[i]
        if area >= min_area:
            boxes.append((x, y, x + w, y + h))
    return boxes


def tile_origins(length: int, tile: int, stride: int) -> list[int]:
    """Tile starts along one axis, always including a flush-to-edge final tile
    so the last strip of a frame is never silently discarded."""
    if length <= tile:
        return [0]
    origins = list(range(0, length - tile + 1, stride))
    if origins[-1] != length - tile:
        origins.append(length - tile)
    return origins


def is_dead(patch: np.ndarray, min_std: float, max_dark: float) -> bool:
    """Near-uniform or overwhelmingly black tiles: water column, padding, or
    off-swath. Not seabed, and worse than useless as a negative."""
    if float(patch.std()) < min_std:
        return True
    return float((patch < 8).mean()) > max_dark


def main() -> int:
    ap = argparse.ArgumentParser(description="Tile waterfalls and convert masks to YOLO boxes.")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tile", type=int, default=640, help="tile size in pixels")
    ap.add_argument("--overlap", type=float, default=0.25, help="fraction of tile overlapped by the next")
    ap.add_argument("--min-visible", type=float, default=0.35,
                    help="fraction of an object's area that must survive clipping for the fragment to be kept")
    ap.add_argument("--min-object-px", type=int, default=64,
                    help="ignore mask components below this AREA in source pixels (annotation speckle)")
    ap.add_argument("--min-box-side", type=int, default=10,
                    help="drop boxes whose short side in TILE pixels is below this. Objects a few pixels "
                         "across cannot be learned at this resolution and dominate the loss with "
                         "unlearnable examples. A tile whose boxes are ALL dropped is discarded rather "
                         "than written as a negative -- see the quarantine note in voc_to_yolo.")
    ap.add_argument("--neg-ratio", type=float, default=1.0,
                    help="negative tiles per positive tile IN THE TRAIN SPLIT; 0 keeps none, -1 keeps all")
    ap.add_argument("--val-neg-ratio", type=float, default=-1.0,
                    help="same for val/test splits. Defaults to -1 (keep ALL): a validation set "
                         "balanced 1:1 flatters the false-positive rate, because real surveys are "
                         "overwhelmingly empty seabed. Measure on the real ratio.")
    ap.add_argument("--empty-split-tiles", type=int, default=250,
                    help="tiles to take from a split that contains no objects at all (e.g. a dedicated "
                         "terrain/background set). Budgeting those off positives would yield zero.")
    ap.add_argument("--merge-empty-into", default="train",
                    help="split that negative-only sets are written into, so they are actually trained "
                         "on rather than sitting in a directory data.yaml never references")
    ap.add_argument("--min-std", type=float, default=6.0, help="reject tiles flatter than this")
    ap.add_argument("--max-dark", type=float, default=0.85, help="reject tiles with more than this fraction near-black")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    src = find_dataset(args.dataset)
    if src is None:
        print(f"dataset '{args.dataset}' not found under ai/data/raw/ -- see docs/DOWNLOAD_GUIDE.md")
        return 1

    dataset_id = args.dataset.upper()
    source_class = DATASET_CLASS.get(dataset_id)
    if source_class is None:
        print(f"no mask class registered for '{dataset_id}'. Add it to DATASET_CLASS in this script.")
        return 1
    training_class, reason = source_to_training(source_class)
    if training_class is None:
        print(f"'{source_class}' does not map to a training class ({reason})")
        return 1
    class_id = TRAINING_CLASSES.index(training_class)

    splits = find_split_dirs(src)
    if not splits:
        print(f"no images/ + labels/ directory pairs found under {src}")
        return 1

    out_root = Path(args.out) if args.out else INTERIM_ROOT / dataset_id
    stride = max(1, int(round(args.tile * (1.0 - args.overlap))))
    report = Report()

    print(f"\nsource : {src}")
    print(f"output : {out_root if not args.dry_run else '(dry run)'}")
    print(f"tiles  : {args.tile}px, stride {stride}px, class {class_id}={training_class}\n")

    for split_name, img_dir, lbl_dir in splits:
        pos_tiles: list[tuple] = []
        neg_tiles: list[tuple] = []

        for img_path in sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS):
            mask_path = None
            for ext in IMAGE_EXTS:
                cand = lbl_dir / (img_path.stem + ext)
                if cand.exists():
                    mask_path = cand
                    break
            if mask_path is None:
                report.missing_masks.append(img_path.name)
                continue

            image = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            mask = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
            if image is None or mask is None:
                report.missing_masks.append(img_path.name)
                continue
            if mask.ndim == 3:
                mask = mask[..., 0]
            if mask.shape != image.shape:
                mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)

            report.frames += 1
            boxes = mask_to_boxes(mask, args.min_object_px)
            report.objects_found += len(boxes)
            if not boxes:
                report.frames_all_negative += 1

            H, W = image.shape
            for oy in tile_origins(H, args.tile, stride):
                for ox in tile_origins(W, args.tile, stride):
                    report.tiles_considered += 1
                    patch = image[oy:oy + args.tile, ox:ox + args.tile]
                    if patch.shape[0] < args.tile or patch.shape[1] < args.tile:
                        pad = np.zeros((args.tile, args.tile), dtype=patch.dtype)
                        pad[:patch.shape[0], :patch.shape[1]] = patch
                        patch = pad

                    lines = []
                    nearest = 10**9
                    tiny_here = False
                    for (x1, y1, x2, y2) in boxes:
                        cx1, cy1 = max(x1, ox), max(y1, oy)
                        cx2, cy2 = min(x2, ox + args.tile), min(y2, oy + args.tile)
                        full = max(1, (x2 - x1) * (y2 - y1))
                        if cx2 <= cx1 or cy2 <= cy1:
                            # distance from tile to object, for hard-negative ranking
                            dx = max(x1 - (ox + args.tile), ox - x2, 0)
                            dy = max(y1 - (oy + args.tile), oy - y2, 0)
                            nearest = min(nearest, int((dx * dx + dy * dy) ** 0.5))
                            continue
                        visible = (cx2 - cx1) * (cy2 - cy1) / full
                        if visible < args.min_visible:
                            # A sliver of hull labelled as a whole wreck is a
                            # false lesson. The overlap means a neighbouring
                            # tile holds this object intact.
                            report.fragments_dropped += 1
                            nearest = 0
                            continue
                        if min(cx2 - cx1, cy2 - cy1) < args.min_box_side:
                            report.boxes_too_small += 1
                            tiny_here = True
                            continue
                        bw, bh = (cx2 - cx1) / args.tile, (cy2 - cy1) / args.tile
                        bcx = (cx1 + cx2) / 2.0 - ox
                        bcy = (cy1 + cy2) / 2.0 - oy
                        lines.append(
                            f"{class_id} {bcx / args.tile:.6f} {bcy / args.tile:.6f} {bw:.6f} {bh:.6f}"
                        )

                    stem = f"{img_path.stem}__x{ox}_y{oy}"
                    if lines:
                        report.tiles_positive += 1
                        pos_tiles.append((stem, patch, lines))
                    elif tiny_here:
                        # Every object here was dropped as too small. Writing an
                        # empty label would assert this tile contains nothing,
                        # training the model that a real object is background.
                        # Discard the tile instead. Same reasoning as the
                        # unmapped-class quarantine in voc_to_yolo.
                        report.tiles_quarantined += 1
                        continue
                    else:
                        if is_dead(patch, args.min_std, args.max_dark):
                            report.tiles_rejected_dead += 1
                            continue
                        report.tiles_negative_available += 1
                        neg_tiles.append((stem, patch, [], nearest))

        # --- negative sampling, per split ---------------------------------
        is_train = "train" in split_name.lower()
        ratio = args.neg_ratio if is_train else args.val_neg_ratio

        if not pos_tiles:
            # A split with no objects anywhere is a dedicated background set
            # (AI4Shipwrecks ships 25 terrain frames like this). Budgeting its
            # negatives off a positive count of zero would discard all of them,
            # which is exactly backwards: they are the cleanest hard negatives
            # in the dataset.
            rng.shuffle(neg_tiles)
            chosen_neg = neg_tiles[: args.empty_split_tiles]
        elif ratio < 0:
            chosen_neg = neg_tiles
        elif ratio == 0:
            chosen_neg = []
        else:
            budget = int(round(len(pos_tiles) * ratio))
            # Nearest-to-an-object first: those are the hard negatives that
            # actually teach the boundary. Blank seabed far from anything is
            # cheap and endless, so it is sampled rather than taken wholesale.
            neg_tiles.sort(key=lambda t: t[3])
            near = neg_tiles[: budget // 2]
            rest = neg_tiles[budget // 2:]
            rng.shuffle(rest)
            chosen_neg = near + rest[: budget - len(near)]
        report.tiles_negative_kept += len(chosen_neg)

        # A negative-only split written to its own directory would never be
        # referenced by data.yaml, so the model would never see it. Fold it
        # into the training split instead; the stem already carries the source
        # frame, so provenance survives the move.
        target_split = args.merge_empty_into if not pos_tiles else split_name
        if target_split != split_name:
            print(f"  {split_name:16s} -> merged into '{target_split}' as background")

        if not args.dry_run:
            oi = out_root / target_split / "images"
            ol = out_root / target_split / "labels"
            oi.mkdir(parents=True, exist_ok=True)
            ol.mkdir(parents=True, exist_ok=True)
            for item in pos_tiles + [(s, p, l) for (s, p, l, _d) in chosen_neg]:
                stem, patch, lines = item
                cv2.imwrite(str(oi / (stem + ".png")), patch)
                (ol / (stem + ".txt")).write_text(
                    "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
                )
                report.boxes_written += len(lines)

        report.per_split[split_name] = {
            "positive_tiles": len(pos_tiles),
            "negative_tiles_kept": len(chosen_neg),
        }
        print(f"  {split_name:16s} positives={len(pos_tiles):5d}  negatives_kept={len(chosen_neg):5d}")

    print(f"\n  {report.frames:5d} frames ({report.frames_all_negative} with no object at all)")
    print(f"  {report.objects_found:5d} mask components -> objects")
    print(f"  {report.tiles_considered:5d} tiles considered")
    print(f"  {report.tiles_positive:5d} positive tiles")
    print(f"  {report.tiles_negative_kept:5d} negative tiles kept "
          f"(of {report.tiles_negative_available} usable)")
    if report.tiles_rejected_dead:
        print(f"  {report.tiles_rejected_dead:5d} dead tiles rejected (water column, padding, off-swath)")
    if report.boxes_too_small:
        print(f"  {report.boxes_too_small:5d} boxes dropped below --min-box-side "
              f"({args.min_box_side}px): too small to learn at this resolution")
    if report.tiles_quarantined:
        print(f"  {report.tiles_quarantined:5d} tiles QUARANTINED: every object on them was too "
              f"small, so an empty label would have taught the model they are background")
    if report.fragments_dropped:
        print(f"  {report.fragments_dropped:5d} edge fragments dropped below --min-visible "
              f"({args.min_visible:.0%}); the overlap keeps them whole elsewhere")
    if report.missing_masks:
        print(f"  ! {len(report.missing_masks)} image(s) with no matching mask")

    if not args.dry_run:
        names = list(TRAINING_CLASSES)
        split_names = [s for s, _, _ in splits]
        train_split = "train" if "train" in split_names else split_names[0]
        val_split = next((s for s in ("valid", "val", "test") if s in split_names), train_split)
        yaml = [
            "# Generated by ai/scripts/masks_to_yolo.py -- do not edit by hand.",
            f"path: {out_root.as_posix()}",
            f"train: {train_split}/images",
            f"val: {val_split}/images",
            "",
            f"nc: {len(names)}",
            "names:",
            *[f"  {i}: {n}" for i, n in enumerate(names)],
            "",
            "# Splits kept as the dataset shipped them. Tiles are named",
            "# <frame>__x<col>_y<row>, so tiles from one waterfall can be grouped;",
            "# splitting tiles from the same frame across train and val is leakage.",
        ]
        (out_root / "data.yaml").write_text("\n".join(yaml), encoding="utf-8")
        (out_root / "tiling_report.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"\nwrote {show(out_root / 'data.yaml')}")
        print(f"wrote {show(out_root / 'tiling_report.json')}")

    if report.tiles_positive == 0:
        print("\nNO POSITIVE TILES. Check the mask directory and --min-object-px.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
