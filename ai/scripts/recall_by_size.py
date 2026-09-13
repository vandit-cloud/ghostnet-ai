"""Recall broken down by object size, because one number can hide two populations.

    python ai/scripts/recall_by_size.py --class wreck
    python ai/scripts/recall_by_size.py --class wreck --split test --device 0

Why this exists
---------------
`wreck` reports recall 0.32 on the test split, and §2 of EXPERIMENT_GV7_PLAN.md
read that as label noise worth a human audit. It is not. Split by object size:

    <0.2% of frame    16 / 143   recall 0.112
    0.2-0.5%          11 / 184   recall 0.060
    0.5-2%            13 / 174   recall 0.075
    >2%              176 / 335   recall 0.525

**On wrecks large enough to identify, recall is 0.525.** 501 of 836 test boxes
are smaller than 2% of frame, and the model finds about 8% of those, which drags
the headline down to 0.32.

Those small boxes are not careless annotation. AI4Shipwrecks ships pixel-wise
masks, and `masks_to_yolo.py` derives boxes from them, so they are tight by
construction. What they are is TILING DEBRIS: a wreck spanning a 1728 x 18179
waterfall gets cut by the 640x640 grid, and each surviving sliver is boxed
faithfully. The tiling report already counts 584 fragments dropped and 109 boxes
rejected as too small, so a threshold exists -- it is simply too permissive.

So this script is diagnostic, not decorative: it distinguishes "the detector is
weak" from "the evaluation set is mostly debris", and those have completely
different fixes. Run it before concluding anything from a low recall.

What it does NOT do
-------------------
It changes no labels. Dropping slivers from train/val while test keeps them
trains a model that is then scored on missing them -- §3.1's exact trap. That
correction is an announced, one-time event, not a side effect of a diagnostic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "ai" / "data" / "processed"
WEIGHTS = ROOT / "ai" / "models" / "trained" / "ghostnet.pt"
CLASSES = {"wreck": 0, "plane": 1, "debris": 2, "ghost_pot": 3, "ghost_net": 4}

# Fractions of frame area. The 2% boundary is where recall steps in the wreck
# data (0.075 below, 0.525 above), not a round number chosen in advance.
BANDS = [("<0.2%", 0.0, 0.002), ("0.2-0.5%", 0.002, 0.005),
         ("0.5-2%", 0.005, 0.02), (">2%", 0.02, 9.0)]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", default="wreck", choices=sorted(CLASSES))
    ap.add_argument("--split", default="test", choices=["test", "val", "train"])
    ap.add_argument("--weights", default=str(WEIGHTS))
    ap.add_argument("--conf", type=float, default=0.25,
                    help="the deployed operating point, not the mAP sweep default")
    ap.add_argument("--iou", type=float, default=0.5, help="match threshold")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from rank_label_suspects import read_labels, iou as box_iou
    from ultralytics import YOLO

    cls_id = CLASSES[args.cls]
    split = PROCESSED / args.split
    frames = []
    for lab in (split / "labels").glob("*.txt"):
        if any(r[0] == cls_id for r in read_labels(lab)):
            img = next((split / "images" / f"{lab.stem}{e}"
                        for e in (".png", ".jpg", ".jpeg")
                        if (split / "images" / f"{lab.stem}{e}").exists()), None)
            if img:
                frames.append((img, lab))
    if not frames:
        print(f"no {args.cls} in {args.split}")
        return 1
    print(f"  {len(frames)} {args.split} frames carry {args.cls}")

    model = YOLO(args.weights)
    tally = {name: [0, 0] for name, _, _ in BANDS}
    for img, lab in frames:
        gt = [r[1:] for r in read_labels(lab) if r[0] == cls_id]
        res = model.predict(str(img), imgsz=args.imgsz, device=args.device,
                            conf=args.conf, verbose=False)[0]
        preds = ([tuple(b) for b, c in zip(res.boxes.xywhn.tolist(), res.boxes.cls.tolist())
                  if int(c) == cls_id] if res.boxes is not None else [])
        for g in gt:
            area = g[2] * g[3]
            band = next(n for n, lo, hi in BANDS if lo <= area < hi)
            tally[band][1] += 1
            if any(box_iou(g, p) >= args.iou for p in preds):
                tally[band][0] += 1

    total_found = sum(v[0] for v in tally.values())
    total = sum(v[1] for v in tally.values())
    print(f"\n  {'size band':12s}{'found':>7s}{'total':>7s}{'recall':>9s}")
    for name, _, _ in BANDS:
        found, n = tally[name]
        print(f"  {name:12s}{found:7d}{n:7d}{(found / n if n else 0):9.3f}")
    print(f"  {'ALL':12s}{total_found:7d}{total:7d}{(total_found / total if total else 0):9.3f}")

    summary = {
        "class": args.cls, "split": args.split, "weights": str(args.weights),
        "conf": args.conf, "iou_match": args.iou,
        "bands": {n: {"found": tally[n][0], "total": tally[n][1],
                      "recall": (tally[n][0] / tally[n][1]) if tally[n][1] else None}
                  for n, _, _ in BANDS},
        "overall_recall": (total_found / total) if total else None,
        "note": ("A low overall recall on a split dominated by small boxes is not "
                 "evidence of a weak detector until this breakdown is read. See the "
                 "module docstring."),
    }
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\n  written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
