"""The ghost_net SEGMENTATION model, as an optional second stage beside the detector.

Two kinds of model, one setting
-------------------------------
GHOSTNET_NET_WEIGHTS (or a promoted models/trained/ghostnet_net.pt) may hold
either a U-Net checkpoint (ghostnet.unet, the shipped model since 26 Sep 2026:
gvU1n, Dice 0.600, centroid 0.807, 1.3% empty-chip false alarms over three
seeds) or a YOLO-seg checkpoint (gv7d3 and earlier). load_net_model() tells
them apart by the file's contents, never its name: a U-Net checkpoint loads
under torch's weights_only mode and a YOLO one cannot. Each runs at its own
measured operating point -- the U-Net at a pixel threshold of
Settings.net_unet_threshold, YOLO at a box confidence of net_conf_threshold.

Why a second model at all
-------------------------
The box detector cannot detect nets: gv5 and gv6 scored recall 0.000, and on
23 Sep 2026 gv8b's net scores on real net chips were measured as 0.0189 on the
chains versus 0.0176 on the empty seabed inside the same boxes -- it learned
"the seabed near a chain", which is what a box around a thin diagonal chain
mostly contains (median 14% chain by area). The single-class segmentation
model trained on 425 polygons (docs/D2_SEGMENTATION_SUMMARY.md) reaches box
recall 0.492 +/- 0.074 and centroid detection 0.607 +/- 0.031 on the same
11 test chips. So when this model is configured, it REPLACES the detector's
ghost_net output rather than adding to it.

OFF unless configured
---------------------
Nothing loads unless Settings.net_weights_path resolves (GHOSTNET_NET_WEIGHTS,
or a promoted models/trained/ghostnet_net.pt). Unset, detect() behaves exactly
as before this module existed.

What it does NOT change
-----------------------
Nets stay `review_only`. The test split is 11 chips from 2 sites, far short of
the promotion rule (>=300 real instances, >=3 sites), so a better candidate is
still a candidate.

Confidence is uncalibrated
--------------------------
The temperature in models/calibrator/ was fitted on the BOX detector's scores
and means nothing for this model's. So a net's `calibrated_confidence` is its
raw score, the uncertainty band is never allowed to read "low", and the
evidence notes say so. Fitting a calibrator for this model needs held-out net
data that does not exist yet.

Engineered input channels
-------------------------
A model trained on build_net_seg_ridge.py's 3-channel input (raw / ridge /
black-hat) must see the same transform at inference, with the SAME fixed
scales. Those live in a channels.json sidecar -- GHOSTNET_NET_CHANNELS, or
`<weights>.channels.json` beside the weights. Without one, the frame is fed as
plain greyscale, which is what every gv7d2/gv7d3 model was trained on. The
U-Net takes one grey channel by construction, so a channels spec configured
beside a U-Net is refused at load time rather than silently ignored.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .config import SETTINGS, Settings

_NET_MODEL = None
_NET_LOCK = threading.Lock()
_NET_ERROR: str | None = None
#: Which weights _NET_MODEL was loaded from. One model is held at a time (4 GB
#: of VRAM), and a request for different weights replaces it rather than being
#: silently answered by the old model under the new model's version string.
_NET_KEY: str | None = None
#: (path, mtime, size) of the file whose load last FAILED. A broken file is not
#: re-read on every frame -- a U-Net read plus a YOLO attempt is ~100 MB of I/O
#: under the lock -- but replacing the file changes the key, so a fixed model
#: is picked up by a running process without a restart.
_NET_FAILED_KEY: tuple | None = None

#: Polygon simplification tolerance in pixels. The raw mask contour has a
#: vertex per boundary pixel -- hundreds per chain -- and the payload is stored
#: and sent per detection. One pixel is below anything a reviewer can see.
POLYGON_EPSILON_PX = 1.0
#: Hard cap on vertices, so one pathological mask cannot bloat a payload.
POLYGON_MAX_POINTS = 200

# --------------------------------------------------------------- channels
# The single implementation of the engineered transform. build_net_seg_ridge.py
# imports these, so training and inference cannot drift apart.

RIDGE_SIGMA, JOIN_SIGMA, BLACKHAT_K = 2.0, 4.0, 25


def ridge(gray):
    """Dark-ridge response: largest Hessian eigenvalue, clipped, then blurred
    so the beads of one chain merge into one line."""
    import cv2
    import numpy as np

    f = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), RIDGE_SIGMA)
    xx = cv2.Sobel(f, cv2.CV_32F, 2, 0)
    yy = cv2.Sobel(f, cv2.CV_32F, 0, 2)
    xy = cv2.Sobel(f, cv2.CV_32F, 1, 1)
    l1 = (xx + yy) / 2 + np.sqrt(((xx - yy) / 2) ** 2 + xy ** 2)
    return cv2.GaussianBlur(np.maximum(l1, 0), (0, 0), JOIN_SIGMA)


def blackhat(gray):
    import cv2
    import numpy as np

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (BLACKHAT_K, BLACKHAT_K))
    r = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k).astype(np.float32)
    return cv2.GaussianBlur(r, (0, 0), JOIN_SIGMA)


def engineer(gray, scales: dict):
    """raw / ridge / black-hat as one BGR image, with FIXED scales."""
    import cv2
    import numpy as np

    def u8(x, s):
        return np.clip(x / s * 255.0, 0, 255).astype(np.uint8)

    return cv2.merge([gray, u8(ridge(gray), scales["ridge"]), u8(blackhat(gray), scales["blackhat"])])


def load_channels(settings: Settings = SETTINGS) -> dict | None:
    """The channels.json for the configured model, or None for plain greyscale."""
    path = settings.net_channels_path
    if path is None or not Path(path).exists():
        return None
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        return spec if {"ridge", "blackhat"} <= set(spec.get("scales", {})) else None
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ model

class UNetNetModel:
    """A loaded U-Net plus what predict_nets needs to run it. `kind` is the
    tag predict_nets dispatches on; a YOLO model has no such attribute."""

    kind = "unet"

    def __init__(self, model, checkpoint: dict, device: str):
        self.model = model
        self.encoder = checkpoint.get("encoder", "?")
        self.imgsz = int(checkpoint.get("imgsz") or 640)
        self.device = device


def _load_unet(weights: Path, checkpoint: dict, settings: Settings) -> UNetNetModel:
    from . import unet

    if load_channels(settings) is not None:
        raise ValueError("a channels spec is configured, but a U-Net takes one grey channel")
    model = unet.build_model(checkpoint["encoder"], weights=None)
    model.load_state_dict(checkpoint["model"])
    model.to(unet.torch_device(settings.device)).eval()
    return UNetNetModel(model, checkpoint, settings.device)


def _file_key(path: Path) -> tuple:
    try:
        st = path.stat()
        return (str(path.resolve()), st.st_mtime_ns, st.st_size)
    except OSError:
        return (str(path), None, None)


def load_net_model(settings: Settings = SETTINGS):
    """Idempotent, thread-safe. None when not configured OR not loadable --
    the second case also sets net_model_error(), so detect() can say so."""
    global _NET_MODEL, _NET_ERROR, _NET_KEY, _NET_FAILED_KEY
    weights = settings.net_weights_path
    if weights is None:
        return None
    weights = Path(weights)
    path_key = str(weights.resolve())
    if _NET_MODEL is not None and _NET_KEY == path_key:
        return _NET_MODEL
    with _NET_LOCK:
        if _NET_MODEL is not None and _NET_KEY == path_key:
            return _NET_MODEL
        file_key = _file_key(weights)
        if file_key == _NET_FAILED_KEY:
            return None          # same file failed before; _NET_ERROR still says why
        if not weights.exists():
            _NET_ERROR = (
                "net segmentation weights configured but not found (" + weights.name
                + "); ghost_net falls back to the box detector's candidates"
            )
            _NET_FAILED_KEY = file_key
            return None
        try:
            from .unet import read_checkpoint

            checkpoint = read_checkpoint(weights)
            if checkpoint is not None:
                model = _load_unet(weights, checkpoint, settings)
            else:
                from ultralytics import YOLO

                model = YOLO(str(weights))
                if getattr(model, "task", "segment") != "segment":
                    raise ValueError("not a segmentation checkpoint")
                model.to(settings.device)
        except Exception as exc:
            _NET_ERROR = (
                "net segmentation weights at " + weights.name + " could not be loaded ("
                + type(exc).__name__ + "); ghost_net falls back to the box detector's candidates"
            )
            _NET_FAILED_KEY = file_key
            return None
        _NET_ERROR = None
        _NET_FAILED_KEY = None
        _NET_MODEL, _NET_KEY = model, path_key
        return _NET_MODEL


def net_model_error() -> str | None:
    return _NET_ERROR


def _polygon(xy) -> list[list[int]] | None:
    """Ultralytics' pixel-space contour -> a simplified integer polygon."""
    import cv2
    import numpy as np

    pts = np.asarray(xy, dtype=np.float32)
    if pts.ndim != 2 or len(pts) < 3:
        return None
    simple = cv2.approxPolyDP(pts.reshape(-1, 1, 2), POLYGON_EPSILON_PX, True).reshape(-1, 2)
    if len(simple) < 3:
        return None
    if len(simple) > POLYGON_MAX_POINTS:
        idx = np.linspace(0, len(simple) - 1, POLYGON_MAX_POINTS).astype(int)
        simple = simple[idx]
    return [[int(round(x)), int(round(y))] for x, y in simple]


def predict_nets(model, gray, settings: Settings = SETTINGS, lock: threading.Lock | None = None) -> list[dict[str, Any]]:
    """Run the net model on one decoded greyscale frame.

    Returns raw items in the same shape infer.detect() builds for the box
    detector, plus a `mask` polygon and a `source` tag. A U-Net is gated at
    settings.net_unet_threshold per pixel, a YOLO model at
    settings.net_conf_threshold per box.
    """
    if getattr(model, "kind", None) == "unet":
        return _predict_unet(model, gray, settings, lock)

    import cv2

    channels = load_channels(settings)
    image = engineer(gray, channels["scales"]) if channels else cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    ctx = lock if lock is not None else threading.Lock()
    with ctx:
        preds = model.predict(
            source=image,
            imgsz=settings.imgsz,
            conf=settings.net_conf_threshold,
            iou=settings.iou_threshold,
            max_det=settings.max_detections,
            device=settings.device,
            retina_masks=True,   # masks at frame resolution, not the 160 px proto grid
            verbose=False,
        )

    out: list[dict[str, Any]] = []
    for pred in preds:
        boxes = getattr(pred, "boxes", None)
        masks = getattr(pred, "masks", None)
        if boxes is None:
            continue
        polys = list(masks.xy) if masks is not None else [None] * len(boxes)
        for box, xy in zip(boxes, polys):
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            out.append({
                "cls": "ghost_net",
                "score": float(box.conf[0]),
                "bbox": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
                "centre": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
                "mask": _polygon(xy) if xy is not None else None,
                "source": "net_seg",
            })
    return out


def _predict_unet(model: UNetNetModel, gray, settings: Settings,
                  lock: threading.Lock | None) -> list[dict[str, Any]]:
    """One U-Net blob per detection, in the same raw-item shape as above.

    The blob rules are ghostnet.unet's, the ones every published U-Net figure
    was scored with: one 8-connected component of pixels at or above the
    threshold is one net, speckle under MIN_BLOB_SHARE is dropped, and the
    score is the mean probability inside the blob.
    """
    from . import unet

    ctx = lock if lock is not None else threading.Lock()
    with ctx:
        prob = unet.predict_prob(model.model, gray, model.device, size=model.imgsz)

    h, w = prob.shape
    out: list[dict[str, Any]] = []
    for blob in unet.blobs(prob, settings.net_unet_threshold):
        bx1, by1, bx2, by2 = blob["box"]
        x1, y1, x2, y2 = bx1 * w, by1 * h, bx2 * w, by2 * h
        out.append({
            "cls": "ghost_net",
            "score": blob["score"],
            # round(), not int(): the blob box comes back normalised, and
            # 40 / 300 * 300 is 39.999... in floating point.
            "bbox": [round(x1), round(y1), round(x2 - x1), round(y2 - y1)],
            "centre": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
            "mask": _polygon([(px * w, py * h) for px, py in blob["points"]]),
            "source": "net_seg",
        })
    # Highest score first, capped by the same max_detections the YOLO path uses.
    out.sort(key=lambda d: d["score"], reverse=True)
    return out[: settings.max_detections]
