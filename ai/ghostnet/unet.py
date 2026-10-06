"""The ghost_net U-Net's inference primitives: one implementation for training,
scoring and serving.

ai/scripts/_net_unet.py (training and evaluation) imports everything here, and
ghostnet.netseg serves it. That is deliberate: a letterbox, normalisation or
blob rule computed one way in training and another way in the web app is a
silent accuracy loss that no test flags as a bug. The channel transform in
netseg.py is shared the same way for the same reason.

Why a U-Net serves ghost_net (measured 24 Sep 2026, ai/experiments/unet-scoring/)
--------------------------------------------------------------------------------
Over three seeds on the 11 test chips, the U-Net trained with empty-seabed
negatives (gvU1n) reached Dice 0.600 +/- 0.011, centroid detection
0.807 +/- 0.042 and fired on 1.3% of empty chips. The YOLO-seg model it
replaces (gv7d3) scored 0.525 / 0.607 / 42%. A YOLO checkpoint still works
through the same setting; netseg.load_net_model tells the two apart by what is
inside the file.

Safe loading
------------
A U-Net checkpoint is a plain dict of tensors and strings, so it is read with
torch.load(weights_only=True), which refuses to execute pickled code. A YOLO
checkpoint pickles whole classes and cannot be read that way. That difference
is also how the two are told apart: see read_checkpoint().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

IMGSZ = 640          # parity with every YOLO-seg run (imgsz 640)
PAD_VALUE = 114      # the grey Ultralytics letterboxes with, for the same reason
MIN_BLOB_SHARE = 0.001
"""Blobs smaller than 0.1% of the chip are discarded as speckle.

Fixed before any U-Net was trained, from the label geometry: the smallest of
the 425 truth polygons covers 0.24% of its chip (p1 0.0024, p5 0.0035, median
0.0119). So 0.1% is safely below any real net and still removes the one-pixel
noise every per-pixel classifier produces, which would otherwise each count as
a detection.
"""


def letterbox(img: np.ndarray, size: int = IMGSZ, interp: int = cv2.INTER_LINEAR,
              pad: int = PAD_VALUE) -> tuple[np.ndarray, tuple[float, int, int]]:
    """Scale the long side to `size`, centre on a square canvas.

    Returns the canvas and (scale, x0, y0) so a prediction can be mapped back.
    """
    h, w = img.shape[:2]
    s = size / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    resized = cv2.resize(img, (nw, nh), interpolation=interp)
    canvas = np.full((size, size), pad, dtype=img.dtype)
    y0, x0 = (size - nh) // 2, (size - nw) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = resized
    return canvas, (s, x0, y0)


def build_model(encoder: str = "resnet34", weights: str | None = "imagenet"):
    """U-Net, single grey input channel, one logit per pixel.

    in_channels=1 makes smp sum the pretrained first-conv filters over RGB,
    which is exactly right for grey replicated to 3 channels and costs a third
    of the input memory.
    """
    import segmentation_models_pytorch as smp
    return smp.Unet(encoder_name=encoder, encoder_weights=weights,
                    in_channels=1, classes=1)


def to_tensor(gray: np.ndarray):
    """uint8 HxW -> float 1x1xHxW in [-1, 1]. Same normalisation as training."""
    import torch
    t = torch.from_numpy(gray.astype(np.float32) / 127.5 - 1.0)
    return t[None, None]


def torch_device(device: str) -> str:
    """Settings.device in the form torch accepts.

    GHOSTNET_DEVICE follows Ultralytics' convention, where "0" means the first
    GPU. torch reads a bare "0" as an error, so digits become "cuda:<n>".
    """
    d = str(device).strip()
    return f"cuda:{d}" if d.isdigit() else d


def read_checkpoint(path: Path) -> dict[str, Any] | None:
    """The checkpoint dict if `path` is a U-Net checkpoint, else None.

    Loaded with weights_only=True, so nothing pickled is ever executed. A YOLO
    checkpoint fails that load (it pickles classes), and so does anything that
    is not a torch file at all; both return None and are left for the caller
    to try as YOLO.
    """
    import torch
    try:
        ck = torch.load(str(path), map_location="cpu", weights_only=True)
    except Exception:
        return None
    if isinstance(ck, dict) and isinstance(ck.get("encoder"), str) and isinstance(ck.get("model"), dict):
        return ck
    return None


def load_checkpoint(path: Path, device: str):
    """(model on `device` in eval mode, checkpoint dict). Raises on anything
    that is not a U-Net checkpoint."""
    ck = read_checkpoint(Path(path))
    if ck is None:
        raise ValueError(f"{Path(path).name} is not a U-Net checkpoint")
    model = build_model(ck["encoder"], weights=None)
    model.load_state_dict(ck["model"])
    model.to(torch_device(device)).eval()
    return model, ck


def predict_prob(model, gray: np.ndarray, device: str, size: int = IMGSZ) -> np.ndarray:
    """Net probability per pixel, float32 at the chip's NATIVE resolution."""
    import torch
    dev = torch_device(device)
    on_cuda = dev.startswith("cuda")
    h, w = gray.shape
    canvas, (s, x0, y0) = letterbox(gray, size)
    # autocast is named for the device it runs on: asking for "cuda" autocast
    # on a CPU-only build warns on every call, even when disabled.
    with torch.no_grad(), torch.autocast(device_type="cuda" if on_cuda else "cpu", enabled=on_cuda):
        logits = model(to_tensor(canvas).to(dev))
    prob = torch.sigmoid(logits.float())[0, 0].cpu().numpy()
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    prob = prob[y0:y0 + nh, x0:x0 + nw]
    return cv2.resize(prob, (w, h), interpolation=cv2.INTER_LINEAR)


def blobs(prob: np.ndarray, conf: float) -> list[dict]:
    """Threshold a probability map into detections.

    One connected component (8-connected) of pixels >= conf is one detection.
    Its outline is the largest external contour (NORMALISED points, so it drops
    into centroid_metric.Shape unchanged), its box is the component's bbox, and
    its score is the mean probability inside it.

    `conf` plays the role YOLO's confidence floor plays: the pixel threshold
    that decides what is shown. It is NOT the same quantity, so a U-Net at 0.5
    and YOLO at 0.25 are each at their own natural operating point, not at a
    shared number.
    """
    h, w = prob.shape
    binary = (prob >= conf).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    out: list[dict] = []
    min_area = MIN_BLOB_SHARE * h * w
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        # Work inside the component's own box, not the whole frame: two
        # full-frame masks per blob made a large frame with many blobs
        # O(blobs x H x W). The 1-px pad keeps findContours' view of the border
        # the same as in the full frame; checked identical (points, boxes and
        # scores, bit for bit) on 31 chips x 3 thresholds, 26 Sep 2026.
        sub = lab[y:y + bh, x:x + bw] == i
        contours, _ = cv2.findContours(np.pad(sub.astype(np.uint8), 1),
                                       cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(np.float64) + (x - 1, y - 1)
        out.append({
            "points": [(float(px) / w, float(py) / h) for px, py in c],
            "box": (x / w, y / h, (x + bw) / w, (y + bh) / h),
            "score": float(prob[y:y + bh, x:x + bw][sub].mean()),
        })
    return out
