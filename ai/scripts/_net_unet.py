"""Shared pieces of the ghost_net U-Net: loading, masks, model, inference.

Imported by train_net_unet.py and evaluate_net_unet.py, so that training and
scoring cannot drift apart on preprocessing -- a letterbox computed one way in
training and another at test time is a silent accuracy loss that no metric
flags as a bug.

Why a U-Net at all, when YOLO11s-seg already works
--------------------------------------------------
The two models answer different questions. YOLO-seg is instance-first: it
proposes boxes, scores them, then paints a mask inside each one at 1/4
resolution. A U-Net labels every pixel "net" or "not net" directly, at full
resolution.

That difference matters for one specific result. Adding 102 empty-seabed chips
to YOLO-seg (gv9n) cut false alarms from 31% to 3% of empty chips, but test
box mAP50 fell from 0.528 to 0.351: to an instance model an empty chip is only
"no box here", and it learned to propose less. To a U-Net an empty chip is
~150,000 pixels each labelled background, the same kind of supervision as the
background pixels around a net. The hypothesis under test is that per-pixel
supervision lets a model take on the negatives without losing the nets.

Masks come straight from the existing polygons
----------------------------------------------
The 425 labelme polygons (converted to YOLO-seg labels in net_seg /
net_seg_hardneg) are area outlines, median 27 px wide at 640, not centrelines.
They are filled as-is. No relabelling: the 65 "missing chains" found on 23 Sep
are missing from the BOX labels, and the polygons already contain them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

# The inference half lives in the package, so the web app serves exactly what
# was trained and scored. Re-exported here so `U.letterbox` etc. keep working.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ghostnet.unet import (  # noqa: E402,F401
    IMGSZ,
    MIN_BLOB_SHARE,
    PAD_VALUE,
    blobs,
    build_model,
    letterbox,
    load_checkpoint,
    predict_prob,
    to_tensor,
)


def read_gray(path: Path) -> np.ndarray:
    """uint8 HxW. Some chips are RGBA PNGs, all are grey replicated to 3 channels."""
    im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if im is None:
        raise FileNotFoundError(path)
    return im


def read_polygons(label_path: Path) -> list[np.ndarray]:
    """YOLO-seg label -> list of (N, 2) arrays, NORMALISED 0-1. Empty file = negative chip."""
    polys: list[np.ndarray] = []
    if not label_path.exists():
        return polys
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 7:
            continue
        polys.append(np.array(parts[1:], dtype=np.float64).reshape(-1, 2))
    return polys


def polygons_to_mask(polys: list[np.ndarray], h: int, w: int) -> np.ndarray:
    """Fill the polygons at native resolution. uint8 {0, 1}."""
    mask = np.zeros((h, w), np.uint8)
    for p in polys:
        pts = np.round(p * [w, h]).astype(np.int32)
        cv2.fillPoly(mask, [pts], 1)
    return mask


def list_split(data_dir: Path, split: str) -> list[tuple[Path, Path]]:
    """(image, label) pairs for one split, sorted by name."""
    img_dir = data_dir / split / "images"
    lbl_dir = data_dir / split / "labels"
    return [(p, lbl_dir / f"{p.stem}.txt") for p in sorted(img_dir.iterdir())
            if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
