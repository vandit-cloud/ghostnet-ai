"""Fit the temperature that turns detector scores into honest probabilities.

    python ai/scripts/fit_calibration.py --weights ai/experiments/<run>/weights/best.pt
    python ai/scripts/fit_calibration.py --weights ... --device 0     # if the GPU is free

Writes ai/models/calibrator/temperature.json, which ghostnet/decision.py reads.
Until this file exists the pipeline reports T = 1.0 and refuses to claim "low"
uncertainty for anything -- which is correct, and this is what lifts that cap.

What is actually being fitted
-----------------------------
A YOLO confidence is not a probability. It is a number trained to RANK boxes,
and it is systematically overconfident: across a validation set, the detections
scoring 0.9 are correct rather less than 90% of the time. Temperature scaling
fixes the calibration without touching the ranking -- it divides the logit by a
single scalar T, which is monotonic, so precision, recall and mAP are all
completely unchanged. Only the numbers shown to a human move.

Each prediction becomes one training example for the fit:
    label 1  if it matches a ground-truth box at IoU >= --iou
    label 0  otherwise
and T is chosen to minimise the negative log-likelihood of those labels.

Fitted on VALIDATION, never on test
-----------------------------------
T is a learned parameter. Fitting it on the test split and then reporting test
calibration would be marking your own homework, in exactly the way the plan's
honesty rules exist to prevent.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

DATA_YAML = AI_ROOT / "data" / "processed" / "data.yaml"
CALIBRATOR = AI_ROOT / "models" / "calibrator"


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def load_gt(label_path: Path, w: int, h: int) -> list[tuple[int, float, float, float, float]]:
    """YOLO label file -> [(cls, x1, y1, x2, y2)] in pixels."""
    out = []
    if not label_path.exists():
        return out
    for line in label_path.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        c, cx, cy, bw, bh = line.split()[:5]
        cx, cy, bw, bh = float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
        out.append((int(c), cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))
    return out


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def match(preds, gts, thr: float) -> list[int]:
    """Greedy highest-score-first matching, one ground truth per prediction.

    Greedy by score is what the COCO evaluator does, and it matters: allowing
    two predictions to claim the same object would count a duplicate as
    correct, and duplicates are precisely what a calibrated score should
    discourage.
    """
    labels = []
    taken = set()
    for _score, cls, box in sorted(preds, key=lambda p: -p[0]):
        best, best_i = 0.0, -1
        for i, (gcls, *gbox) in enumerate(gts):
            if i in taken or gcls != cls:
                continue
            v = iou(box, gbox)
            if v > best:
                best, best_i = v, i
        if best >= thr and best_i >= 0:
            taken.add(best_i)
            labels.append(1)
        else:
            labels.append(0)
    return labels


def fit_temperature(scores: np.ndarray, labels: np.ndarray) -> float:
    """Minimise NLL over T by ternary search on a convex-enough 1-D problem.

    A scalar fit does not justify pulling in an optimiser. Ternary search over
    log T is stable, needs no gradients, and cannot wander off.
    """
    p = np.clip(scores, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))

    def nll(t: float) -> float:
        z = logit / t
        # log(1 + exp(-|z|)) form: numerically safe at both extremes
        return float(np.mean(np.logaddexp(0.0, -z) + (1.0 - labels) * z))

    lo, hi = math.log(0.05), math.log(20.0)
    for _ in range(200):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if nll(math.exp(m1)) < nll(math.exp(m2)):
            hi = m2
        else:
            lo = m1
    return math.exp((lo + hi) / 2)


def ece(scores: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error: mean |confidence - accuracy| per bin.

    This is the number worth quoting. A model can have excellent mAP and a
    terrible ECE, and it is the ECE a reviewer feels when a detection labelled
    90% turns out to be a rock.
    """
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for i in range(bins):
        m = (scores > edges[i]) & (scores <= edges[i + 1])
        if m.sum():
            total += m.mean() * abs(scores[m].mean() - labels[m].mean())
    return float(total)


def reliability(scores: np.ndarray, labels: np.ndarray, bins: int = 10) -> str:
    lines = ["    conf range      n    predicted    actual"]
    edges = np.linspace(0.0, 1.0, bins + 1)
    for i in range(bins):
        m = (scores > edges[i]) & (scores <= edges[i + 1])
        if m.sum():
            lines.append(
                f"    {edges[i]:.1f}-{edges[i+1]:.1f}  {m.sum():6d}    "
                f"{scores[m].mean():9.3f} {labels[m].mean():9.3f}"
            )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fit temperature scaling on the validation split.")
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", default=str(DATA_YAML))
    ap.add_argument("--split", default="val", choices=["val", "train"],
                    help="never 'test': T is a learned parameter, and fitting it on test "
                         "then reporting test calibration is marking your own homework")
    ap.add_argument("--conf", type=float, default=0.05,
                    help="low on purpose. Calibration needs the wrong detections too; "
                         "fitting only on high-confidence hits models the easy half.")
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="cpu",
                    help="CPU by default so this can run while a training job holds the GPU")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        print(f"weights not found: {weights}")
        return 1

    import yaml
    from ultralytics import YOLO

    cfg = yaml.safe_load(Path(args.data).read_text(encoding="utf-8"))
    root = Path(cfg.get("path", Path(args.data).parent))
    images_dir = root / cfg[args.split].replace("/images", "") / "images"
    labels_dir = images_dir.parent / "labels"
    if not images_dir.is_dir():
        print(f"no {args.split} images at {images_dir}")
        return 1

    files = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    print(f"\n  weights  {show(weights)}")
    print(f"  split    {args.split} ({len(files)} images) on {args.device}")
    print(f"  matching IoU >= {args.iou}, keeping predictions above conf {args.conf}\n")
    if args.dry_run:
        print("dry run: nothing fitted.")
        return 0

    model = YOLO(str(weights))
    scores: list[float] = []
    labels: list[int] = []

    for i in range(0, len(files), 16):
        chunk = files[i:i + 16]
        results = model.predict(source=[str(p) for p in chunk], imgsz=args.imgsz,
                                conf=args.conf, device=args.device, verbose=False)
        for path, res in zip(chunk, results):
            h, w = res.orig_shape
            gts = load_gt(labels_dir / (path.stem + ".txt"), w, h)
            preds = []
            for box in getattr(res, "boxes", []) or []:
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                preds.append((float(box.conf[0]), int(box.cls[0]), (x1, y1, x2, y2)))
            matched = match(preds, gts, args.iou)
            scores.extend(p[0] for p in sorted(preds, key=lambda p: -p[0]))
            labels.extend(matched)
        print(f"  {min(i + 16, len(files))}/{len(files)} images, {len(scores)} predictions", end="\r")

    print()
    if len(scores) < 50:
        print(f"\nonly {len(scores)} predictions -- too few to fit a temperature honestly.")
        print("Lower --conf, or train longer before calibrating.")
        return 1

    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=float)
    t = fit_temperature(s, y)

    calibrated = 1.0 / (1.0 + np.exp(-(np.log(np.clip(s, 1e-6, 1 - 1e-6) /
                                              (1 - np.clip(s, 1e-6, 1 - 1e-6))) / t)))
    before, after = ece(s, y), ece(calibrated, y)

    print(f"\n  {len(s)} predictions, {int(y.sum())} correct ({y.mean():.1%})")
    print(f"  mean raw score {s.mean():.3f} vs actual accuracy {y.mean():.3f}")
    print(f"\n  temperature T = {t:.4f}")
    print("  T > 1 softens overconfident scores; T < 1 sharpens underconfident ones.")
    print(f"\n  ECE before {before:.4f} -> after {after:.4f}"
          + ("  (improved)" if after < before else "  (NOT improved -- see warning below)"))
    print("\n  reliability, raw scores:")
    print(reliability(s, y))

    if after >= before:
        print("\n  ! Calibration did not improve ECE. That usually means too few")
        print("    predictions, or a model still early in training. Prefer T = 1.0")
        print("    over a fitted value that makes things worse.")

    CALIBRATOR.mkdir(parents=True, exist_ok=True)
    out = CALIBRATOR / "temperature.json"
    out.write_text(json.dumps({
        "temperature": round(t, 6),
        "fitted_on": args.split,
        "weights": str(weights),
        "n_predictions": int(len(s)),
        "n_correct": int(y.sum()),
        "iou_threshold": args.iou,
        "conf_threshold": args.conf,
        "ece_before": round(before, 6),
        "ece_after": round(after, 6),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {show(out)}")
    print("ghostnet/decision.py picks this up automatically; 'low' uncertainty is now reachable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
