"""Build the ghost_net segmentation dataset with ENGINEERED input channels.

    python ai/scripts/build_net_seg_ridge.py
    python ai/scripts/train_net_seg.py --data "E:/New folder/ai/data/net_seg_ridge3/data.yaml" \
        --no-colour-aug --epochs 1000 --name gv9r-netseg-ridge3-s0 --seed 0

Reads  ai/data/net_seg/{train,val,test}/{images,labels}   (built by build_net_seg_dataset.py)
Writes ai/data/net_seg_ridge3/{train,val,test}/{images,labels} + data.yaml + channels.json

One variable against the gv7d3 baseline
---------------------------------------
Same 73 chips, same polygons, same 51/11/11 split (copied, never recomputed),
same trainer. Only the pixels change. The baseline fed the model one grey image
three times over; this feeds it three different views of it:

    channel 0 (B)  raw sonar
    channel 1 (G)  dark-ridge response: largest Hessian eigenvalue at sigma 2,
                   clipped at 0, then Gaussian-blurred at sigma 4 so the beads
                   of one chain merge into one line
    channel 2 (R)  black-hat (dark spots on a lighter surround), 25 px ellipse,
                   same sigma-4 blur

Why these two: measured 23 Sep 2026 on the 425 polygons, CPU only. The ridge
channel catches 0.89 of held-out chains while flagging 20% of a chip (pixel
AUROC 0.86 within frame); black-hat reaches 0.81. Gaussian background
subtraction and CLAHE, the obvious alternatives, scored 0.53-0.54 and are
deliberately absent.

Why ONE global scale per channel, fitted on train
-------------------------------------------------
Per-image normalisation would stretch every chip's ridge response to full
range, including a chip of empty seabed, which would turn noise into
"strong ridge". A fixed scale keeps the channel's meaning the same on every
image. It is the 99.5th percentile of the response over TRAIN pixels only, so
val and test never influence it, and it is written to channels.json because
inference must apply exactly the same numbers.

Why the trainer needs --no-colour-aug
-------------------------------------
Ultralytics' hsv_h / hsv_s augmentations are no-ops on a grey image (zero
saturation), so the baseline never really had them. On engineered channels they
are not no-ops: a hue shift mixes the ridge channel into the raw one. Turning
them off therefore matches the baseline's effective augmentation instead of
changing it. hsv_v (brightness) is kept, as in the baseline.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import sys

import cv2
import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

# ONE implementation of the transform, shared with inference, so the pixels a
# model trains on and the pixels it is served can never drift apart.
from ghostnet.netseg import BLACKHAT_K, JOIN_SIGMA, RIDGE_SIGMA, blackhat, engineer, ridge  # noqa: E402

DEFAULT_SRC = Path("E:/New folder/ai/data/net_seg")
DEFAULT_DST = Path("E:/New folder/ai/data/net_seg_ridge3")
PCTL = 99.5


def fit_scales(train_images: list[Path]) -> dict:
    rs, bs = [], []
    rng = np.random.default_rng(0)
    for p in train_images:
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        for acc, fn in ((rs, ridge), (bs, blackhat)):
            v = fn(g).ravel()
            acc.append(rng.choice(v, min(20000, v.size), replace=False))
    return {"ridge": float(np.percentile(np.concatenate(rs), PCTL)),
            "blackhat": float(np.percentile(np.concatenate(bs), PCTL))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--dst", type=Path, default=DEFAULT_DST)
    a = ap.parse_args()
    if a.dst.exists():
        raise SystemExit(f"{a.dst} exists -- delete it deliberately before rebuilding")

    train_imgs = sorted((a.src / "train" / "images").glob("*"))
    scales = fit_scales(train_imgs)
    counts = {}
    for split in ("train", "val", "test"):
        (a.dst / split / "images").mkdir(parents=True)
        (a.dst / split / "labels").mkdir(parents=True)
        imgs = sorted((a.src / split / "images").glob("*"))
        for p in imgs:
            g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            cv2.imwrite(str(a.dst / split / "images" / f"{p.stem}.png"), engineer(g, scales))
            shutil.copy2(a.src / split / "labels" / f"{p.stem}.txt", a.dst / split / "labels")
        counts[split] = len(imgs)

    (a.dst / "channels.json").write_text(json.dumps({
        "order_bgr": ["raw", "ridge", "blackhat"],
        "ridge_sigma": RIDGE_SIGMA, "join_sigma": JOIN_SIGMA, "blackhat_k": BLACKHAT_K,
        "scale_percentile": PCTL, "scales_fitted_on": "train", "scales": scales,
        "source": str(a.src), "counts": counts}, indent=2))
    (a.dst / "data.yaml").write_text(
        "# ghost_net segmentation, ENGINEERED 3-channel input (raw / ridge / black-hat).\n"
        "# Built by ai/scripts/build_net_seg_ridge.py -- do not hand-edit.\n"
        "# Same chips, polygons and split as net_seg; only the pixels differ.\n"
        f"path: {a.dst.as_posix()}\ntrain: train/images\nval: val/images\ntest: test/images\n"
        "names:\n  0: ghost_net\n")
    print(f"built {counts} -> {a.dst}\nscales {scales}")


if __name__ == "__main__":
    main()
