"""Seconds per frame for each inference runtime, through the real detect path.

    python ai/scripts/bench_runtime.py --images "E:/New folder/ai/data/processed/val/images"
    python ai/scripts/bench_runtime.py --images <dir> --json out.json

Times infer.detect_batch -- decode, model, post-processing, shadow and dropout
context, the lot -- because that is what a user waits for. A model-only
figure is also taken (one frame per call, preprocessing + inference + NMS
inside Ultralytics) so the number can be compared with published "ms per
tile" claims, which are usually model-only.

Configurations: torch on the GPU (when there is one), torch on CPU, ONNX
Runtime on CPU; each detector-only and detector + net U-Net. Each is warmed
first (two batches, untimed): the first CUDA call creates the context and the
first ONNX call allocates its arena, and neither is what a survey of 40
frames pays per frame.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

os.environ.setdefault("GHOSTNET_NET_WEIGHTS", "none")   # each config sets its own

from ghostnet import infer, netseg  # noqa: E402
from ghostnet.config import Settings  # noqa: E402

TRAINED = AI_ROOT / "models" / "trained"


def square_tiles(folder: Path, n: int) -> list[Path]:
    """n 640x640 tiles: the shape a survey is cut into, so per-frame figures
    are per-tile figures."""
    import cv2

    out = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if im is not None and im.shape == (640, 640):
            out.append(p)
        if len(out) >= n:
            break
    return out


def _reset():
    infer._MODEL = None
    infer._MODEL_KEY = None
    netseg._NET_MODEL = None
    netseg._NET_KEY = None


def run(label: str, settings: Settings, tiles: list[Path], repeats: int) -> dict:
    _reset()
    assert infer.load_model(settings) is not None, f"{label}: detector did not load"
    bs = settings.batch_size
    infer.detect_batch(tiles[: 2 * bs], {}, settings)                 # warm-up
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        payloads = infer.detect_batch(tiles, {}, settings)
        times.append((time.perf_counter() - t0) / len(tiles))
    prov = payloads[0]["provenance"]
    # Model-only, batch 1, detector alone.
    model = infer.load_model(settings)
    single = []
    for p in tiles[:24]:
        t0 = time.perf_counter()
        infer._predict_many(model, [str(p)], settings)
        single.append(time.perf_counter() - t0)
    row = {
        "config": label,
        "runtime": prov.get("runtime"),
        "net_runtime": prov.get("net_runtime"),
        "s_per_frame_median": round(statistics.median(times), 4),
        "s_per_frame_runs": [round(t, 4) for t in times],
        "detector_model_only_batch1_ms": round(1000 * statistics.median(single), 1),
        "frames": len(tiles),
        "batch_size": bs,
        "detections": sum(len(p["detections"]) for p in payloads),
    }
    print(json.dumps(row))
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", required=True)
    ap.add_argument("--n", type=int, default=40, help="tiles per timed pass (default 40, one demo survey)")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--json", help="write the rows here")
    args = ap.parse_args()

    import torch

    tiles = square_tiles(Path(args.images), args.n)
    net = TRAINED / "ghostnet_net.pt"
    configs = []
    if torch.cuda.is_available():
        configs += [("torch-cuda detector", dict(runtime="torch", device="cuda", net_weights_path=None)),
                    ("torch-cuda detector+unet", dict(runtime="torch", device="cuda", net_weights_path=net))]
    configs += [("torch-cpu detector", dict(runtime="torch", device="cpu", net_weights_path=None)),
                ("torch-cpu detector+unet", dict(runtime="torch", device="cpu", net_weights_path=net)),
                ("onnx-cpu detector", dict(runtime="onnx", device="cpu", net_weights_path=None)),
                ("onnx-cpu detector+unet", dict(runtime="onnx", device="cpu", net_weights_path=net))]

    rows = []
    for label, kw in configs:
        s = Settings(**kw)
        if kw["net_weights_path"] is None:
            # Settings() would otherwise resolve the promoted net model; the
            # env var above only covers the default, not an explicit None.
            s.net_weights_path = None
        if "onnx" in label and s.runtime_active != "onnx":
            print(f"skip {label}: {s.runtime_note}")
            continue
        rows.append(run(label, s, tiles, args.repeats))

    meta = {"cpu": platform.processor(), "torch": torch.__version__,
            "torch_threads": torch.get_num_threads(), "rows": rows}
    try:
        import onnxruntime

        meta["onnxruntime"] = onnxruntime.__version__
    except ImportError:
        pass
    if torch.cuda.is_available():
        meta["gpu"] = torch.cuda.get_device_name(0)
    if args.json:
        Path(args.json).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
