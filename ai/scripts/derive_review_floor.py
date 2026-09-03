"""Derive the review floor from a measured recall / false-alarm curve.

    python ai/scripts/derive_review_floor.py
    python ai/scripts/derive_review_floor.py --limit 400      # a quick look

Writes ai/experiments/review_floor.json and prints the whole curve.

Why this script exists
----------------------
`review_floor_artificial` has been 0.20 since it was written, and the handoff
records that it "happens to be reasonable; it was not derived". A threshold
chosen by feel is the most consequential unmeasured number in the system: it
alone decides what a human ever sees.

The trap this avoids
--------------------
evaluate_background.py sweeps RAW detector scores. The review floor is applied
to CALIBRATED confidence, after temperature scaling. Those are different scales
-- at the current temperature, far apart -- so reading a false-alarm rate off
the raw curve and applying it to the floor silently compares two numbers that
merely look alike. Everything here is calibrated end to end, which is what
makes the answer usable.

What is measured, on the held-out test split and never validation
-----------------------------------------------------------------
  * RECALL over labelled objects, class-aware, IoU >= 0.5. A detection of the
    wrong class on the right pixels is not a find.
  * FALSE-ALARM RATE over frames whose labels are empty: the fraction that
    would put at least one box in front of a reviewer.

Choosing from the curve is a policy call, not a computation, so this states its
rule and prints the whole table rather than emitting one number: take the
highest floor that gives up no more than 5% of the recall available at 0.05.
The asymmetry is from decision.py -- a missed ghost net keeps fishing for
years, a false alarm costs a reviewer a few seconds.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

THRESHOLDS = [round(0.05 * i, 2) for i in range(1, 17)]   # 0.05 .. 0.80
RECALL_GIVE_UP = 0.05


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Recall vs false alarms, on calibrated confidence.")
    ap.add_argument("--weights", default=str(AI_ROOT / "models" / "trained" / "ghostnet.pt"))
    ap.add_argument("--split", default="test")
    ap.add_argument("--device", default="0")
    ap.add_argument("--raw-conf", type=float, default=0.02,
                    help="detector floor; must sit below the lowest calibrated threshold")
    ap.add_argument("--limit", type=int, default=0, help="cap frames, for a quick look")
    args = ap.parse_args()

    from ghostnet.config import Settings
    from ghostnet.decision import calibrate
    from ultralytics import YOLO

    settings = Settings(weights_path=args.weights, device=args.device)
    split = AI_ROOT / "data" / "processed" / args.split
    images = sorted(p for p in (split / "images").iterdir()
                    if p.suffix.lower() in (".png", ".jpg"))
    if args.limit:
        images = images[: args.limit]

    print()
    print("  weights " + args.weights)
    print("  %d frames in the %s split" % (len(images), args.split))
    print("  raw 0.50 calibrates to %.3f" % calibrate(0.5, settings))
    print()

    model = YOLO(args.weights)
    gt_total = 0
    hits = {t: 0 for t in THRESHOLDS}
    bg_frames = 0
    bg_flagged = {t: 0 for t in THRESHOLDS}

    for i in range(0, len(images), 16):
        batch = images[i : i + 16]
        preds = model.predict(source=[str(p) for p in batch], imgsz=settings.imgsz,
                              conf=args.raw_conf, iou=settings.iou_threshold,
                              device=args.device, verbose=False)
        for path, pred in zip(batch, preds):
            lp = split / "labels" / (path.stem + ".txt")
            rows = [r.split() for r in lp.read_text().splitlines() if r.strip()] if lp.exists() else []
            h, w = pred.orig_shape

            gt = []
            for r in rows:
                c = int(r[0])
                cx, cy, bw, bh = (float(v) for v in r[1:5])
                gt.append((c, ((cx - bw / 2) * w, (cy - bh / 2) * h,
                               (cx + bw / 2) * w, (cy + bh / 2) * h)))

            dets = []
            if pred.boxes is not None and len(pred.boxes):
                for b in pred.boxes:
                    dets.append((int(b.cls[0]), calibrate(float(b.conf[0]), settings),
                                 tuple(float(v) for v in b.xyxy[0].tolist())))

            if not gt:
                bg_frames += 1
                for t in THRESHOLDS:
                    if any(conf >= t for _c, conf, _xy in dets):
                        bg_flagged[t] += 1
                continue

            gt_total += len(gt)
            for t in THRESHOLDS:
                above = [d for d in dets if d[1] >= t]
                used: set[int] = set()
                for gc, gbox in gt:
                    for di, (dc, _conf, dbox) in enumerate(above):
                        if di in used or dc != gc:
                            continue
                        if iou(gbox, dbox) >= 0.5:
                            used.add(di)
                            hits[t] += 1
                            break

    base = hits[THRESHOLDS[0]] / gt_total if gt_total else 0.0
    curve = []
    for t in THRESHOLDS:
        rec = hits[t] / gt_total if gt_total else 0.0
        curve.append({
            "calibrated_threshold": t,
            "recall": round(rec, 4),
            "recall_retained": round(rec / base, 4) if base else 0.0,
            "false_alarm_rate": round(bg_flagged[t] / bg_frames, 4) if bg_frames else 0.0,
            "frames_flagged": bg_flagged[t],
        })

    eligible = [c for c in curve if c["recall_retained"] >= 1.0 - RECALL_GIVE_UP]
    recommended = max((c["calibrated_threshold"] for c in eligible), default=THRESHOLDS[0])

    print("  %d labelled objects, %d empty frames" % (gt_total, bg_frames))
    print()
    print("  calibrated   recall   retained   false alarms")
    for c in curve:
        star = "  <- recommended" if c["calibrated_threshold"] == recommended else ""
        print("      %.2f      %.3f     %6.1f%%       %6.2f%%%s"
              % (c["calibrated_threshold"], c["recall"],
                 100 * c["recall_retained"], 100 * c["false_alarm_rate"], star))

    out = AI_ROOT / "experiments" / "review_floor.json"
    out.write_text(json.dumps({
        "weights": args.weights,
        "split": args.split,
        "labelled_objects": gt_total,
        "empty_frames": bg_frames,
        "rule": "highest threshold retaining >= %d%% of recall at %.2f"
                % (100 * (1 - RECALL_GIVE_UP), THRESHOLDS[0]),
        "recommended_review_floor_artificial": recommended,
        "current_review_floor_artificial": Settings().review_floor_artificial,
        "curve": curve,
        "note": "Calibrated confidence throughout. evaluate_background.py sweeps RAW "
                "scores, so its thresholds are NOT comparable to review_floor_artificial.",
    }, indent=2), encoding="utf-8")

    print()
    print("  wrote " + str(out))
    print("  rule: highest floor retaining >= %d%% of the recall at %.2f"
          % (100 * (1 - RECALL_GIVE_UP), THRESHOLDS[0]))
    print("  current setting is %.2f" % Settings().review_floor_artificial)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
