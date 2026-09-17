"""Measure the artificial-vs-natural claim: how often does the model cry wolf?

    python ai/scripts/evaluate_background.py --weights ai/experiments/<run>/weights/best.pt

Writes <run>/background_metrics.json beside the weights.

Why this is the headline number
-------------------------------
The problem statement asks the system to "separate natural seafloor topology
from artificial anomalies". There is no `natural` class to score, and there
never can be: nobody draws boxes around rocks, so every natural example we have
is a hard negative -- an image with no object on it.

The honest way to score that claim is therefore to point the detector at
seabed CARRYING NO ANNOTATION and count how often it reports something. That is
a false-positive rate on real sonar, not a class confidence, and it is the
number a reviewer actually feels: it is the rate at which a survey crew would
be sent to look at a rock.

Say "carrying no annotation", never "verified empty". We know nobody drew a box
on these tiles; we do NOT know they hold nothing. Roughly half come from survey
lines the source dataset left entirely unannotated, so every rate here is an
UPPER BOUND on the true false-alarm rate.

Reported as a curve, not a single figure, because the answer depends entirely
on the confidence threshold -- and quoting the rate at a threshold nobody would
deploy is the easiest way to flatter a model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

PROCESSED = AI_ROOT / "data" / "processed"
THRESHOLDS = (0.10, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70)


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="False-positive rate on seabed carrying no annotation.")
    ap.add_argument("--weights", required=True)
    ap.add_argument("--split", default="test", help="use the held-out split, not val")
    ap.add_argument("--data-root", default=str(PROCESSED))
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="0")
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        print(f"weights not found: {weights}")
        return 1

    # Only used to translate each raw threshold into the calibrated confidence
    # a deployed reviewer would actually see. See scale_warning below.
    from ghostnet.config import Settings
    from ghostnet.decision import calibrate

    settings = Settings(weights_path=str(weights), device=args.device)

    root = Path(args.data_root) / args.split
    images, labels = root / "images", root / "labels"
    if not images.is_dir():
        print(f"no {args.split} split at {root}")
        return 1

    background = [
        p for p in sorted(images.iterdir())
        if (labels / (p.stem + ".txt")).exists()
        and not (labels / (p.stem + ".txt")).read_text(encoding="utf-8").strip()
    ]
    if not background:
        print("no background tiles in this split -- nothing to measure.")
        print("Without tiles carrying no annotation there is no way to score the")
        print("artificial-vs-natural claim at all.")
        return 1

    from ultralytics import YOLO

    print(f"\n  weights {show(weights)}")
    print(f"  split   {args.split}: {len(background)} tiles carrying no annotation\n")

    model = YOLO(str(weights))
    best_score: list[float] = []
    detections: list[int] = []
    for i in range(0, len(background), args.batch):
        chunk = background[i:i + args.batch]
        for res in model.predict(source=[str(p) for p in chunk], imgsz=args.imgsz,
                                 conf=min(THRESHOLDS), device=args.device, verbose=False):
            boxes = getattr(res, "boxes", None)
            confs = [float(b.conf[0]) for b in boxes] if boxes is not None and len(boxes) else []
            best_score.append(max(confs, default=0.0))
            detections.append(len(confs))
        print(f"  {min(i + args.batch, len(background))}/{len(background)}", end="\r")

    s = np.asarray(best_score)
    d = np.asarray(detections)
    rows = []
    print("\n\n  false alarms on empty seabed")
    print("  raw thr  (calibrated)   frames flagged        rate    false boxes/frame")
    for t in THRESHOLDS:
        flagged = int((s >= t).sum())
        boxes = int(sum(1 for _ in range(0)) or (d[(s >= t)].sum() if flagged else 0))
        # The threshold here is a RAW detector score. The shipped review floor
        # is applied to CALIBRATED confidence, so the two are not the same
        # scale and a rate read off this table does not describe the deployed
        # operating point. Record the equivalent so nobody has to know that.
        rows.append({"threshold": t, "frames_flagged": flagged,
                     "rate": flagged / len(s), "total_boxes": int(boxes),
                     "calibrated_equivalent": round(calibrate(t, settings), 4)})
        print(f"  {t:7.2f}  ({calibrate(t, settings):9.3f})   {flagged:5d} / {len(s):<5d}   "
              f"{flagged / len(s) * 100:8.2f}%   {boxes / len(s):8.3f}")

    out = weights.parent.parent / "background_metrics.json"
    out.write_text(json.dumps({
        "weights": str(weights),
        "split": args.split,
        "background_tiles": len(s),
        "curve": rows,
        "note": ("False-positive rate on tiles CARRYING NO ANNOTATION -- real side-scan seabed "
                 "that nobody drew a box on. This is NOT the same as seabed verified to contain "
                 "nothing: roughly half these tiles come from survey lines the source dataset "
                 "left entirely unannotated, so every rate here is an UPPER BOUND. This is how "
                 "the artificial-vs-natural requirement is scored: there is no natural class, "
                 "because nobody draws boxes around rocks."),
        "scale_warning": ("`threshold` is a RAW detector score, and the review floor is applied "
                          "to CALIBRATED confidence -- different scales, so do not compare a row "
                          "here with a row in review_floor.json. "
                          "WHICH ROW IS THE DEPLOYED ONE: the shipped detector gate is "
                          "config.raw_conf_threshold = 0.10, and the shipped review floor is "
                          "0.20 calibrated, which corresponds to a raw score of about 0.02. "
                          "0.02 < 0.10, so the RAW GATE IS THE BINDING CONSTRAINT and the review "
                          "floor rejects nothing that survived it -- the floor is inert in the "
                          "shipped configuration. The deployed false-alarm rate is therefore the "
                          "row at raw threshold 0.10 in THIS file. review_floor.json's "
                          "false_alarm_rate column is measured with the detector opened to raw "
                          "0.02 (derive_review_floor.py --raw-conf), which is deliberate so the "
                          "calibrated sweep is not truncated, but it is not the shipped gate and "
                          "its rates are correspondingly higher."),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {show(out)}")
    print("\n  Quote this WITH its threshold. The rate at a threshold nobody would")
    print("  deploy is not a result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
