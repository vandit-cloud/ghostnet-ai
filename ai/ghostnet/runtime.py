"""Which inference runtime serves the models: PyTorch, or ONNX Runtime on CPU.

    GHOSTNET_RUNTIME = auto | torch | onnx        (default auto)

Why ONNX at all
---------------
The shipped stack is fast on a GPU and slow without one. Measured 29 Sep 2026
on this project's laptop, torch on CPU took 1.34-1.61 s per frame for the
detector plus the net U-Net, against 0.09 s on the RTX 3050. Most people who
clone this repository to try it have no CUDA GPU, so the CPU number IS the
product for them. ONNX Runtime is the cheapest real CPU speed-up that does not
retrain anything: same weights, same post-processing, a different executor.
ai/experiments/onnx-cpu/RESULTS.md has the measured table.

The selection rule
------------------
* torch -- always PyTorch, on Settings.device. The pre-ONNX behaviour.
* onnx  -- ONNX Runtime on CPU, when a VERIFIED export exists (below);
           otherwise PyTorch, and the payload warns that the request was not
           honoured. Never a crash: the package's promise is that a frame
           always comes back as a valid payload.
* auto  -- PyTorch when Settings.device is a GPU (it is ~15x faster there than
           anything on CPU); else ONNX when a verified export exists; else
           PyTorch on CPU.

ONE post-processing path
------------------------
Only the executor changes. The detector's .onnx is loaded through the same
Ultralytics YOLO() call as the .pt, so letterboxing, NMS and the Results
objects infer.detect() reads are Ultralytics' own, identical code for both.
The U-Net's ONNX session is wrapped so ghostnet.unet.predict_prob runs the
same letterbox, sigmoid, crop and resize around it. Two post-processing copies
is how the batched and single-frame paths in infer.py would have diverged,
and the same reasoning applies across runtimes.

A verified export, not just a file
----------------------------------
An .onnx file beside the .pt proves nothing about WHICH .pt it came from.
Replace ghostnet.pt with a new run, forget to re-export, and the app would
serve the OLD model under the NEW model's version string -- the provenance
failure config.py goes to some length to prevent. So an export is used only
when its sidecar (written by ai/scripts/export_onnx.py, and only after the
parity check passed) names the current .pt by sha256 and the .onnx itself by
sha256. Anything else falls back to PyTorch and says why.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Sequence

RUNTIMES = ("auto", "torch", "onnx")

#: Parity gates. A detector box must keep its class, overlap its PyTorch twin
#: at IoU >= 0.95 and move its score by at most 0.01; a U-Net mask must reach
#: Dice >= 0.99 against PyTorch's. Set before the export was first run; FP32
#: ONNX is expected to sit far inside them (U-Net logits differ by ~1e-4).
PARITY_IOU_MIN = 0.95
PARITY_SCORE_TOL = 0.01
PARITY_DICE_MIN = 0.99
PARITY_MIN_IMAGES = 50


def requested_runtime(raw: str | None = None) -> tuple[str, str | None]:
    """The requested runtime, normalised, plus a note when it was not valid.

    An invalid value degrades to 'auto' with a note rather than raising:
    Settings is built at import time, and a typo in an environment variable
    must not make the whole package unimportable.
    """
    value = (raw if raw is not None else os.environ.get("GHOSTNET_RUNTIME", "auto")) or "auto"
    value = value.strip().lower()
    if value in RUNTIMES:
        return value, None
    return "auto", f"GHOSTNET_RUNTIME={value!r} is not one of {', '.join(RUNTIMES)}; using auto"


def onnx_path_for(weights: Path | str) -> Path:
    """ghostnet.pt -> ghostnet.onnx, beside it."""
    return Path(weights).with_suffix(".onnx")


def sidecar_path_for(onnx_path: Path | str) -> Path:
    """ghostnet.onnx -> ghostnet.onnx.json.

    Not ghostnet.json: that name is already the .pt's sidecar, which config.py
    reads model_version and dataset_version from.
    """
    p = Path(onnx_path)
    return p.with_name(p.name + ".json")


_HASH_CACHE: dict[tuple, str] = {}


def sha256(path: Path | str) -> str:
    """sha256 of a file, cached by (path, mtime, size).

    Settings is constructed often (every test, every replace()), and the two
    model files are 19 MB and 98 MB. Replacing a file changes its mtime and so
    misses the cache, which is the case verification exists to catch.
    """
    p = Path(path)
    st = p.stat()
    key = (str(p.resolve()), st.st_mtime_ns, st.st_size)
    hit = _HASH_CACHE.get(key)
    if hit is not None:
        return hit
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    _HASH_CACHE[key] = h.hexdigest()
    return _HASH_CACHE[key]


def onnxruntime_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        return False
    return True


def verify_onnx(source: Path | str | None) -> str | None:
    """None when `source`'s .onnx export may serve in its place, else why not.

    Checks, in order: the .onnx exists, its sidecar parses, the sidecar says
    parity passed, the .onnx is the file the sidecar hashed, and the sidecar's
    source hash is the CURRENT source file. The last one is the stale-export
    case: a re-promoted .pt with a forgotten re-export.
    """
    if source is None:
        return "no source weights configured"
    source = Path(source)
    onnx = onnx_path_for(source)
    if not onnx.exists():
        return f"no {onnx.name} beside {source.name} (run ai/scripts/export_onnx.py)"
    side = sidecar_path_for(onnx)
    try:
        meta = json.loads(side.read_text(encoding="utf-8"))
    except Exception:
        return f"{side.name} is missing or unreadable, so {onnx.name} is unverified"
    if not (meta.get("parity") or {}).get("passed"):
        return f"{side.name} does not record a passed parity check"
    try:
        if meta.get("onnx_sha256") != sha256(onnx):
            return f"{onnx.name} does not match the hash in {side.name}; re-export it"
        if not source.exists():
            return f"{source.name} is missing, so {onnx.name} cannot be traced to it"
        if meta.get("source_sha256") != sha256(source):
            return (f"{onnx.name} was exported from a different {source.name} "
                    "(source sha256 differs); re-run ai/scripts/export_onnx.py")
    except OSError as exc:
        return f"could not hash the model files ({type(exc).__name__})"
    return None


def choose(requested: str, device: str, onnx_problem: str | None) -> tuple[str, str | None]:
    """The pure selection rule: (runtime, note). See the module docstring.

    `onnx_problem` is None when a verified export AND onnxruntime are both
    present, else the reason ONNX cannot run. The note is set only when the
    caller ASKED for onnx and is not getting it -- auto falling back to torch
    is the expected outcome on a machine without an export, not news.
    """
    on_gpu = str(device).strip().lower() not in ("cpu", "")
    if requested == "torch":
        return "torch", None
    if requested == "onnx":
        if onnx_problem is None:
            return "onnx", None
        return "torch", f"GHOSTNET_RUNTIME=onnx requested but {onnx_problem}; running PyTorch on {device}"
    # auto
    if on_gpu:
        return "torch", None
    return ("onnx", None) if onnx_problem is None else ("torch", None)


def onnx_problem_for(source: Path | str | None) -> str | None:
    """Everything that stops `source` running under ONNX, as one reason."""
    if not onnxruntime_available():
        return "onnxruntime is not installed (pip install onnxruntime)"
    return verify_onnx(source)


def label(runtime: str, device: str) -> str:
    """What provenance records: torch-cuda, torch-cpu or onnxruntime-cpu."""
    if runtime == "onnx":
        return "onnxruntime-cpu"
    return "torch-cpu" if str(device).strip().lower() == "cpu" else "torch-cuda"


# ------------------------------------------------------------------ U-Net

class OnnxUNet:
    """An ONNX Runtime session that stands in for the torch U-Net module.

    ghostnet.unet.predict_prob dispatches on this type and runs the identical
    letterbox / sigmoid / crop / resize around it, so the only difference
    between the runtimes is who computes the logits.
    """

    def __init__(self, path: Path | str, threads: int | None = None):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = int(threads)
        self.path = Path(path)
        self.session = ort.InferenceSession(str(path), sess_options=opts,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def logits(self, x):
        """float32 Nx1xHxW in [-1, 1] -> logits, same shape."""
        import numpy as np

        return self.session.run(None, {self.input_name: np.ascontiguousarray(x, dtype=np.float32)})[0]


# ---------------------------------------------------------------- parity

def box_iou(a: Sequence[float], b: Sequence[float]) -> float:
    """IoU of two xyxy boxes."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match_detections(ref: Iterable[dict], cand: Iterable[dict], conf_floor: float,
                     iou_min: float = PARITY_IOU_MIN,
                     score_tol: float = PARITY_SCORE_TOL) -> dict[str, Any]:
    """Pair one frame's reference boxes with a candidate runtime's.

    Each item is {"cls", "score", "xyxy"}. Greedy by reference score: each
    reference box takes the same-class candidate it overlaps most. A pair
    passes at IoU >= iou_min and |score delta| <= score_tol.

    An UNPAIRED box is tolerated only when its score is within score_tol of
    the confidence floor: a box at 0.0301 against a floor of 0.03 can land on
    either side of it from a 1e-5 numeric difference, and that is the
    threshold doing its job, not the export changing the model. Anything
    unpaired above that band fails.
    """
    ref = sorted(ref, key=lambda d: -d["score"])
    pool = list(cand)
    used = [False] * len(pool)
    pairs, bad = [], []
    for r in ref:
        best, best_iou = None, -1.0
        for j, c in enumerate(pool):
            if used[j] or c["cls"] != r["cls"]:
                continue
            iou = box_iou(r["xyxy"], c["xyxy"])
            if iou > best_iou:
                best, best_iou = j, iou
        if best is None or best_iou < iou_min:
            if r["score"] > conf_floor + score_tol:
                bad.append(("missing", r))
            continue
        used[best] = True
        ds = abs(r["score"] - pool[best]["score"])
        pairs.append((best_iou, ds))
        if ds > score_tol:
            bad.append(("score", r, pool[best]))
    for j, c in enumerate(pool):
        if not used[j] and c["score"] > conf_floor + score_tol:
            bad.append(("extra", c))
    return {
        "paired": len(pairs),
        "min_iou": min((p[0] for p in pairs), default=1.0),
        "max_score_delta": max((p[1] for p in pairs), default=0.0),
        "failures": bad,
        "ok": not bad,
    }


def dice(a, b) -> float:
    """Dice of two boolean masks. Two empty masks agree perfectly (1.0):
    most frames hold no net, and "both found nothing" is parity."""
    import numpy as np

    a, b = np.asarray(a, bool), np.asarray(b, bool)
    total = int(a.sum()) + int(b.sum())
    if total == 0:
        return 1.0
    return 2.0 * int(np.logical_and(a, b).sum()) / total
