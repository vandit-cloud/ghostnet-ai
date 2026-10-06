"""Export the served models to ONNX, verify parity, and only then install them.

    python ai/scripts/export_onnx.py --images "E:/New folder/ai/data/processed/val/images"
    python ai/scripts/export_onnx.py --images <dir> --net-images <net chips dir>
    python ai/scripts/export_onnx.py --images <dir> --only detector
    python ai/scripts/export_onnx.py --images <dir> --force      # replace existing exports

For each model it writes, beside the .pt (both gitignored, like the weights):

* <stem>.onnx      -- FP32, opset 17, dynamic batch. The detector goes through
  Ultralytics' own exporter, so the .onnx carries the class names and the
  letterbox metadata its predictor needs; the U-Net through torch.onnx.export.
* <stem>.onnx.json -- the sidecar ghostnet.runtime.verify_onnx() checks before
  serving the export: sha256 of the source .pt and of the .onnx, the opset,
  the export time and the parity figures below.

PARITY, before anything is installed
------------------------------------
Exported into a scratch directory first, then scored against PyTorch on CPU
in FP32 (the same arithmetic, so any difference is the export's) on >= 50
images:

* detector -- every box above the floor pairs with a same-class box at
  IoU >= 0.95 and |score delta| <= 0.01 (ghostnet.runtime.match_detections),
  run at conf 0.03, the lowest floor the app ever uses, so the check covers
  every box any configuration can report;
* U-Net    -- the 0.5-threshold masks reach Dice >= 0.99 on every image.

A failure refuses the export and leaves any existing one untouched, the way
promote_net_model.py refuses a slim checkpoint that changes the model. The
shipped GPU path runs FP16, so the same comparison against torch-CUDA-FP16 is
also recorded, as information rather than a gate.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from ghostnet import runtime as rt  # noqa: E402
from ghostnet import unet  # noqa: E402

TRAINED = AI_ROOT / "models" / "trained"
OPSET = 17
#: The lowest detector floor in Settings (raw_conf_threshold_net). Parity at
#: the lowest floor covers every box a higher one could report.
PARITY_CONF = 0.03
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def pick_images(folder: Path, n: int) -> list[Path]:
    """n images spread evenly over the sorted folder -- deterministic, and
    not just the first site's tiles, which sort together."""
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if len(files) <= n:
        return files
    step = len(files) / n
    return [files[int(i * step)] for i in range(n)]


def _boxes(results) -> list[list[dict]]:
    out = []
    for r in results:
        names = r.names
        items = []
        for b in r.boxes:
            items.append({"cls": names[int(b.cls[0])], "score": float(b.conf[0]),
                          "xyxy": [float(v) for v in b.xyxy[0].tolist()]})
        out.append(items)
    return out


def _predict(model, images: list[Path], device: str, quantize: int, batch: int = 8):
    out = []
    for i in range(0, len(images), batch):
        chunk = [str(p) for p in images[i:i + batch]]
        out += _boxes(model.predict(source=chunk, imgsz=640, conf=PARITY_CONF, iou=0.5,
                                    max_det=300, device=device, quantize=quantize, verbose=False))
    return out


def detector_parity(pt: Path, onnx: Path, images: list[Path], gpu_reference: bool) -> dict:
    from ultralytics import YOLO

    ref = _predict(YOLO(str(pt)), images, "cpu", 32)
    got = _predict(YOLO(str(onnx), task="detect"), images, "cpu", 32)
    report = _compare_boxes(ref, got, images)
    if gpu_reference:
        import torch

        if torch.cuda.is_available():
            gpu = _predict(YOLO(str(pt)), images, "0", 16)
            info = _compare_boxes(gpu, got, images)
            report["vs_torch_cuda_fp16"] = {k: v for k, v in info.items() if k != "passed"} | {
                "within_gate": info["passed"],
                "n_failures": len(info["failures"]),
                "note": "information only: FP16 on the GPU is a different computation, not the gate",
            }
    return report


def _compare_boxes(ref, got, images) -> dict:
    failures, paired, min_iou, max_ds, n_ref, n_got = [], 0, 1.0, 0.0, 0, 0
    for path, a, b in zip(images, ref, got):
        m = rt.match_detections(a, b, PARITY_CONF)
        paired += m["paired"]
        n_ref, n_got = n_ref + len(a), n_got + len(b)
        min_iou, max_ds = min(min_iou, m["min_iou"]), max(max_ds, m["max_score_delta"])
        for f in m["failures"]:
            failures.append({"image": path.name, "kind": f[0],
                             "boxes": [{"cls": x["cls"], "score": round(x["score"], 4)} for x in f[1:]]})
    return {"passed": not failures, "n_images": len(images), "boxes_reference": n_ref,
            "boxes_onnx": n_got, "boxes_paired": paired, "min_iou": round(min_iou, 5),
            "max_score_delta": round(max_ds, 5), "failures": failures[:20],
            "gate": f"same class, IoU >= {rt.PARITY_IOU_MIN}, |score delta| <= {rt.PARITY_SCORE_TOL}, "
                    f"conf {PARITY_CONF}"}


def net_parity(pt: Path, onnx: Path, images: list[Path], threshold: float = 0.5) -> dict:
    import cv2
    import numpy as np

    model, ck = unet.load_checkpoint(pt, "cpu")
    session = rt.OnnxUNet(onnx)
    size = int(ck.get("imgsz") or unet.IMGSZ)
    dices, max_dp, worst, blobs_equal, with_net = [], 0.0, None, 0, 0
    for path in images:
        gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        a = unet.predict_prob(model, gray, "cpu", size=size)
        b = unet.predict_prob(session, gray, "cpu", size=size)
        d = rt.dice(a >= threshold, b >= threshold)
        dices.append(d)
        max_dp = max(max_dp, float(np.abs(a - b).max()))
        blobs_equal += len(unet.blobs(a, threshold)) == len(unet.blobs(b, threshold))
        # Two empty masks score Dice 1.0, so say how many images actually
        # held net pixels -- parity on 60 empty frames would prove little.
        with_net += bool((a >= threshold).any())
        if worst is None or d < worst[1]:
            worst = (path.name, d)
    return {"passed": min(dices) >= rt.PARITY_DICE_MIN, "n_images": len(images),
            "min_dice": round(min(dices), 5), "mean_dice": round(float(np.mean(dices)), 5),
            "worst_image": worst[0], "max_abs_prob_delta": round(max_dp, 6),
            "images_with_equal_blob_count": blobs_equal,
            "images_with_net_pixels": with_net,
            "gate": f"Dice >= {rt.PARITY_DICE_MIN} on every image at pixel threshold {threshold}"}


def export_detector(pt: Path, workdir: Path) -> Path:
    from ultralytics import YOLO

    # Export from a COPY: Ultralytics writes <stem>.onnx beside its input, and
    # beside the live .pt that would overwrite a verified export before this
    # one has passed anything.
    tmp_pt = workdir / pt.name
    shutil.copy2(pt, tmp_pt)
    out = YOLO(str(tmp_pt)).export(format="onnx", imgsz=640, opset=OPSET, dynamic=True,
                                   simplify=False, device="cpu", verbose=False)
    return Path(out)


def export_net(pt: Path, workdir: Path) -> Path:
    import torch

    model, ck = unet.load_checkpoint(pt, "cpu")
    size = int(ck.get("imgsz") or unet.IMGSZ)
    out = workdir / (pt.stem + ".onnx")
    # dynamo=False: the TorchScript exporter needs nothing beyond torch and
    # onnx, and on this smp U-Net it reproduces the logits to ~1e-4. The
    # torch.export one wants onnxscript as well, for no gain on a static graph.
    torch.onnx.export(model, (torch.zeros(1, 1, size, size),), str(out),
                      input_names=["image"], output_names=["logits"],
                      dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
                      opset_version=OPSET, dynamo=False)
    return out


def _versions() -> dict:
    import onnx
    import onnxruntime
    import torch

    v = {"torch": torch.__version__, "onnx": onnx.__version__, "onnxruntime": onnxruntime.__version__}
    try:
        import ultralytics

        v["ultralytics"] = ultralytics.__version__
    except ImportError:
        pass
    return v


def install(pt: Path, tmp_onnx: Path, kind: str, parity: dict, extra: dict) -> Path:
    """Move a verified export into place beside `pt`, sidecar last-but-together."""
    dest = rt.onnx_path_for(pt)
    side = rt.sidecar_path_for(dest)
    pt_meta = {}
    try:
        pt_meta = json.loads(pt.with_suffix(".json").read_text(encoding="utf-8"))
    except Exception:
        pass
    meta = {
        "kind": kind,
        "model_version": pt_meta.get("model_version", pt.stem),
        "source": pt.name,
        "source_sha256": rt.sha256(pt),
        "onnx_sha256": rt.sha256(tmp_onnx),
        "opset": OPSET,
        "precision": "fp32",
        "dynamic_batch": True,
        "exported_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "versions": _versions(),
        **extra,
        "parity": parity,
        "note": ("Written by export_onnx.py after the parity check passed. ghostnet.runtime serves "
                 "the .onnx only while source_sha256 matches the .pt beside it, so a re-promoted "
                 "model needs a re-export. Gitignored, like the weights."),
    }
    tmp_side = side.with_suffix(".json.tmp")
    tmp_side.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    shutil.move(str(tmp_onnx), str(dest))
    tmp_side.replace(side)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", required=True, help="folder of real frames for the parity check (>= 50)")
    ap.add_argument("--net-images", help="extra folder of net chips added to the U-Net check; the val "
                    "split holds few nets, and Dice on frames both runtimes leave empty proves little")
    ap.add_argument("--n", type=int, default=60, help="images to check (default 60, minimum 50)")
    ap.add_argument("--detector", default=str(TRAINED / "ghostnet.pt"))
    ap.add_argument("--net", default=str(TRAINED / "ghostnet_net.pt"))
    ap.add_argument("--only", choices=("detector", "net"))
    ap.add_argument("--force", action="store_true", help="replace an existing verified export")
    ap.add_argument("--no-gpu-reference", action="store_true",
                    help="skip the informational comparison against torch-CUDA-FP16")
    args = ap.parse_args()

    images = pick_images(Path(args.images), args.n)
    if len(images) < rt.PARITY_MIN_IMAGES:
        print(f"refused: {len(images)} images in {args.images}; parity needs >= {rt.PARITY_MIN_IMAGES}")
        return 1

    jobs = []
    if args.only in (None, "detector"):
        jobs.append(("detector", Path(args.detector)))
    if args.only in (None, "net") and Path(args.net).exists():
        jobs.append(("net", Path(args.net)))

    status = 0
    for kind, pt in jobs:
        if not pt.exists():
            print(f"[{kind}] no weights at {pt}")
            status = 1
            continue
        dest = rt.onnx_path_for(pt)
        if dest.exists() and not args.force and rt.verify_onnx(pt) is None:
            print(f"[{kind}] {dest.name} already verified for this {pt.name}; --force to redo")
            continue
        with tempfile.TemporaryDirectory(prefix="ghostnet-onnx-") as tmp:
            t0 = time.perf_counter()
            if kind == "detector":
                onnx = export_detector(pt, Path(tmp))
                parity = detector_parity(pt, onnx, images, gpu_reference=not args.no_gpu_reference)
                extra = {"imgsz": 640, "exporter": "ultralytics"}
            else:
                onnx = export_net(pt, Path(tmp))
                net_images = images + (pick_images(Path(args.net_images), args.n) if args.net_images else [])
                parity = net_parity(pt, onnx, net_images)
                if args.net_images:
                    parity["net_images_dir"] = str(Path(args.net_images)).replace("\\", "/")
                ck = unet.read_checkpoint(pt) or {}
                extra = {"imgsz": int(ck.get("imgsz") or unet.IMGSZ), "encoder": ck.get("encoder"),
                         "exporter": "torch.onnx.export (TorchScript)"}
            parity["images_dir"] = str(Path(args.images)).replace("\\", "/")
            summary = {k: v for k, v in parity.items()
                       if k not in ("failures", "gate", "images_dir", "vs_torch_cuda_fp16")}
            print(f"[{kind}] parity {json.dumps(summary)}")
            if not parity["passed"]:
                print(f"[{kind}] REFUSED: export does not reproduce PyTorch; nothing installed")
                for f in parity.get("failures", [])[:10]:
                    print("   ", f)
                status = 1
                continue
            dest = install(pt, onnx, kind, parity, extra)
            print(f"[{kind}] installed {dest.relative_to(AI_ROOT.parent)} "
                  f"({dest.stat().st_size / 1e6:.1f} MB) in {time.perf_counter() - t0:.0f} s")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
