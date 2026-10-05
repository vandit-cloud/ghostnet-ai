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

One map per class (format 2)
----------------------------
The file now carries a global temperature AND a map per detector class. A
class gets its own map only with at least --min-positives matched detections
on val (default 30): below that, a fitted T is mostly noise -- plane has 9 val
boxes, ghost_net a handful -- and the class is recorded as a "fallback" with
the reason, using the global T. The global T is still written at the top
level, so a reader that predates format 2 keeps working on the same file.

--method picks temperature (one parameter per class) or platt (slope and
intercept per class). The choice was measured, not assumed:
ai/experiments/calib-perclass/RESULTS.md.

Predictions are made with the SERVED NMS settings (Settings.iou_threshold 0.5,
max_detections), not ultralytics' defaults (0.7). The format-1 file was fitted
at 0.7: 1,604 val boxes where the app's NMS keeps 1,238, the difference being
duplicates that are labelled wrong by construction and that no reviewer ever
sees. Calibrate the population that is served.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

DATA_YAML = AI_ROOT / "data" / "processed" / "data.yaml"


def calibrator_dir() -> Path:
    """Where temperature.json is written.

    Must track the READER, which resolves `models_dir` from GHOSTNET_MODELS_DIR
    (config.py) and then reads `<models_dir>/calibrator/temperature.json`
    (decision.py). This used to be a hardcoded constant, so fitting calibration
    for an experiment silently overwrote the SHIPPED model's temperature no
    matter what the environment said -- which is exactly how gv6's temperature
    ended up paired with gv5's weights and had to be reverted by hand.

    Resolved at call time, not at import, so a test can set the variable after
    this module is already loaded.
    """
    return Path(os.environ.get("GHOSTNET_MODELS_DIR", AI_ROOT / "models")) / "calibrator"


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


def fit_platt(scores: np.ndarray, labels: np.ndarray, l2: float = 1e-3) -> tuple[float, float]:
    """Logistic regression of the label on the raw logit: p = sigmoid(a*z + b).

    Newton's method on a 2-parameter convex problem -- a handful of steps, no
    optimiser dependency. The small ridge on (a - 1, b) keeps a class with
    nearly separable scores from running the slope off to infinity, and pulls
    toward the identity map rather than toward a flat one.
    """
    p = np.clip(scores, 1e-6, 1 - 1e-6)
    z = np.log(p / (1 - p))
    y = labels.astype(float)
    a, b = 1.0, 0.0
    for _ in range(100):
        q = _sigmoid(a * z + b)
        g = np.array([np.mean((q - y) * z) + l2 * (a - 1.0), np.mean(q - y) + l2 * b])
        w = q * (1 - q)
        h = np.array([[np.mean(w * z * z) + l2, np.mean(w * z)],
                      [np.mean(w * z), np.mean(w) + l2]])
        step = np.linalg.solve(h, g)
        a, b = a - step[0], b - step[1]
        if np.abs(step).max() < 1e-9:
            break
    return float(a), float(b)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    # Clipped so a steep Platt slope cannot overflow exp; +-50 is far past
    # where the result stops changing in float64.
    return 1.0 / (1.0 + np.exp(-np.clip(z, -50.0, 50.0)))


def apply_params(params: dict, scores: np.ndarray) -> np.ndarray:
    """Vectorised twin of ghostnet.decision.apply_map."""
    p = np.clip(scores, 1e-6, 1 - 1e-6)
    z = np.log(p / (1 - p))
    if params["method"] == "platt":
        z = params["a"] * z + params["b"]
    else:
        z = z / params["temperature"]
    return _sigmoid(z)


#: The temperature search runs over [0.05, 20]. A fit that lands at either end
#: has not found a minimum, it has run out of room -- the class's errors are
#: not a temperature problem. Measured: val ghost_pot is correct 60% of the
#: time at raw 0.07 and 69% overall, so the NLL keeps falling as T -> infinity
#: (every score -> 0.5) and the "fit" is T = 20.0, the wall. Applying that on
#: test, where ghost_pot is correct 30% of the time, raised its ECE from 0.064
#: to 0.178.
T_BOUNDS = (0.05, 20.0)
#: Same idea for Platt: a slope outside this range is a near-separable or
#: near-flat class, not a calibration (val ghost_pot produced a = 636).
PLATT_SLOPE_BOUNDS = (0.05, 20.0)


def _degenerate(entry: dict) -> str | None:
    if entry["method"] == "temperature":
        t = entry["temperature"]
        lo, hi = T_BOUNDS
        if t <= lo * 1.01 or t >= hi * 0.99:
            return f"temperature fit ran into the search bound ({t:.3g}); its errors are not a temperature problem"
    else:
        a = entry["a"]
        lo, hi = PLATT_SLOPE_BOUNDS
        if not (lo <= a <= hi):
            return f"Platt slope {a:.3g} is outside [{lo}, {hi}]; the class is near-separable or near-flat on val"
    return None


def build_calibrator(scores: np.ndarray, classes: np.ndarray, labels: np.ndarray,
                     names: list[str], method: str = "temperature",
                     min_positives: int = 30) -> dict:
    """Global T plus one map per class with enough evidence; the fallbacks say why.

    A class gets its own map when it has >= min_positives matched AND
    unmatched detections on val, and the fit is not degenerate (see T_BOUNDS).
    Everything else uses the global temperature.

    The global temperature is fitted on the pooled val detections of every
    class EXCEPT degenerate ones. Without that exclusion ghost_pot -- 638 of
    the 1,238 val boxes, and degenerate -- dragged the pooled T to 6.31, and
    every fallback class inherited a correction fitted to pots: test debris
    ECE went 0.092 raw -> 0.326. A class whose val scores are known not to be
    a temperature problem is not evidence about the other classes' T.

    Returns the "format_version" / "method" / "temperature" / "classes" part
    of a format-2 calibrator file. Provenance fields are the caller's job.
    """
    y = labels.astype(float)
    out_classes: dict[str, dict] = {}
    pooled = np.ones(len(scores), dtype=bool)
    for k, name in enumerate(names):
        m = classes == k
        n, pos = int(m.sum()), int(y[m].sum())
        entry: dict = {"n": n, "positives": pos}
        if pos < min_positives or (n - pos) < min_positives:
            which = "positives" if pos < min_positives else "negatives"
            have = pos if which == "positives" else n - pos
            entry.update(fallback=True, reason=(
                f"{have} matched {which} on val < {min_positives}; a per-class fit on so "
                f"few is noise"))
        else:
            if method == "platt":
                a, b = fit_platt(scores[m], y[m])
                fitted = {"method": "platt", "a": round(a, 6), "b": round(b, 6)}
            else:
                fitted = {"method": "temperature",
                          "temperature": round(fit_temperature(scores[m], y[m]), 6)}
            why = _degenerate(fitted)
            if why:
                entry.update(fallback=True, reason=why, rejected_fit=fitted)
                pooled &= ~m
            else:
                entry.update(fitted)
                entry["ece_before"] = round(ece(scores[m], y[m]), 6)
                entry["ece_after"] = round(ece(apply_params(entry, scores[m]), y[m]), 6)
        out_classes[name] = entry

    t_global = fit_temperature(scores[pooled], y[pooled])
    for entry in out_classes.values():
        if entry.get("fallback"):
            entry["reason"] += f"; the global temperature {t_global:.4f} is used"
    return {"format_version": 2, "method": method, "temperature": round(t_global, 6),
            "min_positives": min_positives,
            "global_fitted_on": [n for k, n in enumerate(names)
                                 if (pooled & (classes == k)).any()],
            "classes": out_classes}


def calibrate_array(cal: dict, scores: np.ndarray, classes: np.ndarray, names: list[str]) -> np.ndarray:
    """Apply a format-2 calibrator (as returned by build_calibrator) by class."""
    out = apply_params({"method": "temperature", "temperature": cal["temperature"]}, scores)
    for k, name in enumerate(names):
        entry = cal.get("classes", {}).get(name)
        m = classes == k
        if entry and not entry.get("fallback") and m.any():
            out[m] = apply_params(entry, scores[m])
    return out


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
    ap.add_argument("--out", default=None,
                    help="explicit path for temperature.json. Overrides GHOSTNET_MODELS_DIR. "
                         "Use it for an experiment-local fit so the shipped calibrator is "
                         "never touched.")
    ap.add_argument("--method", default="temperature", choices=["temperature", "platt"],
                    help="per-class map. Platt tied temperature on held-out NLL (test "
                         "0.4622 vs 0.4623; served boxes 0.5114 vs 0.5105), so the "
                         "one-parameter map ships; see ai/experiments/calib-perclass/RESULTS.md")
    ap.add_argument("--min-positives", type=int, default=30,
                    help="matched (and unmatched) val detections a class needs for its own "
                         "map; fewer and it uses the global temperature")
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
    destination = Path(args.out) if args.out else calibrator_dir() / "temperature.json"
    print(f"  will write {show(destination)}")
    if destination.resolve() == (AI_ROOT / "models" / "calibrator" / "temperature.json").resolve():
        print("  ^ this is the SHIPPED calibrator. For an experiment, set GHOSTNET_MODELS_DIR")
        print("    or pass --out, or you will re-fit the promoted model's temperature.")

    if args.dry_run:
        print("dry run: nothing fitted.")
        return 0

    from ghostnet.config import Settings
    from ghostnet.decision import _digest

    served = Settings(weights_path=weights)
    model = YOLO(str(weights))
    names = [str(model.names[i]) for i in range(len(model.names))]
    scores: list[float] = []
    classes: list[int] = []
    labels: list[int] = []

    for i in range(0, len(files), 16):
        chunk = files[i:i + 16]
        results = model.predict(source=[str(p) for p in chunk], imgsz=args.imgsz,
                                conf=args.conf, iou=served.iou_threshold,
                                max_det=served.max_detections, device=args.device,
                                verbose=False)
        for path, res in zip(chunk, results):
            h, w = res.orig_shape
            gts = load_gt(labels_dir / (path.stem + ".txt"), w, h)
            preds = []
            for box in getattr(res, "boxes", []) or []:
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                preds.append((float(box.conf[0]), int(box.cls[0]), (x1, y1, x2, y2)))
            preds.sort(key=lambda p: -p[0])
            labels.extend(match(preds, gts, args.iou))
            scores.extend(p[0] for p in preds)
            classes.extend(p[1] for p in preds)
        print(f"  {min(i + 16, len(files))}/{len(files)} images, {len(scores)} predictions", end="\r")

    print()
    if len(scores) < 50:
        print(f"\nonly {len(scores)} predictions -- too few to fit a temperature honestly.")
        print("Lower --conf, or train longer before calibrating.")
        return 1

    s = np.asarray(scores, dtype=float)
    c = np.asarray(classes, dtype=int)
    y = np.asarray(labels, dtype=float)
    cal = build_calibrator(s, c, y, names, args.method, args.min_positives)
    calibrated = calibrate_array(cal, s, c, names)
    before, after = ece(s, y), ece(calibrated, y)

    print(f"\n  {len(s)} predictions, {int(y.sum())} correct ({y.mean():.1%})")
    print(f"  mean raw score {s.mean():.3f} vs actual accuracy {y.mean():.3f}")
    print(f"\n  global temperature T = {cal['temperature']:.4f} "
          f"(pooled over {', '.join(cal['global_fitted_on'])})")
    for name, entry in cal["classes"].items():
        if entry.get("fallback"):
            print(f"    {name:10s} -> global   {entry['reason']}")
        else:
            params = (f"T = {entry['temperature']:.4f}" if entry["method"] == "temperature"
                      else f"a = {entry['a']:.4f}, b = {entry['b']:.4f}")
            print(f"    {name:10s} -> own map  {params}   ECE {entry['ece_before']:.4f} -> "
                  f"{entry['ece_after']:.4f}  ({entry['positives']}/{entry['n']} correct)")
    print("  T > 1 softens overconfident scores; T < 1 sharpens underconfident ones.")
    print(f"\n  ECE before {before:.4f} -> after {after:.4f}"
          + ("  (improved)" if after < before else "  (NOT improved -- see warning below)"))
    print("\n  reliability, raw scores:")
    print(reliability(s, y))
    print("\n  reliability, calibrated:")
    print(reliability(calibrated, y))

    if after >= before:
        print("\n  ! Calibration did not improve ECE on the split it was fitted on.")
        print("    That usually means too few predictions, or a split whose labels do")
        print("    not represent the classes. Check test before shipping it.")

    out_dir = Path(args.out).parent if args.out else calibrator_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else out_dir / "temperature.json"
    out.write_text(json.dumps({
        "format_version": cal["format_version"],
        "method": cal["method"],
        # Top level, always: a format-1 reader reads exactly this key and
        # nothing else, and keeps working.
        "temperature": cal["temperature"],
        "global_fitted_on": cal["global_fitted_on"],
        "min_positives": cal["min_positives"],
        "classes": cal["classes"],
        "fitted_on": args.split,
        "weights": str(weights),
        # Content, not location: decision.calibration_mismatch compares this
        # against the ACTIVE weights' digest, so a calibrator fitted on one
        # machine is still checkable on another.
        "weights_sha256": _digest(weights),
        "n_predictions": int(len(s)),
        "n_correct": int(y.sum()),
        "iou_threshold": args.iou,
        "nms_iou": served.iou_threshold,
        "conf_threshold": args.conf,
        "ece_before": round(before, 6),
        "ece_after": round(after, 6),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {show(out)}")
    print("ghostnet/decision.py picks this up automatically; 'low' uncertainty is now reachable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
