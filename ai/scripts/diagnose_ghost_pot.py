"""Why does ghost_pot not fit its own training data? (train recall 0.28, zero train/val gap)

    python ai/scripts/diagnose_ghost_pot.py [--weights <box detector best.pt>] [--per-family 60]

All ghost_pot boxes come from one source, GHOSTVISION, a Roboflow export:
`<original>_png_jpg.rf.<hash>.jpg`, several augmented copies per original, and
every split drawn from different surveys (val is all `Contact_*_sslo`). This
script measures three candidate causes on TRAIN frames, per survey family:

1. Box looseness. Roboflow rotates and shears copies and re-fits the box
   axis-aligned around the rotated corners, so a rotated copy's box is larger
   than the pot. A detector drawing a tight box then fails IoU 0.5 while
   hitting the pot. Measured as recall at IoU 0.5 against IoU 0.3 and 0.1.
2. Rotated copies. Side-scan is not rotation-invariant (train_net_seg.py
   docstring). Detected by the black wedge Roboflow leaves in rotated frames;
   recall is split by rotated vs unrotated.
3. Tiny targets. Recall by box side in pixels at 640.

Output: ai/experiments/ghost-pot-diagnosis/diagnosis.json + a printed table.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
from pathlib import Path

import cv2
import numpy as np

DATA = Path("E:/New folder/ai/data/processed")
OUT = Path(__file__).resolve().parents[1] / "experiments" / "ghost-pot-diagnosis"
POT = 3


def family(path: str) -> str:
    orig = Path(path).name.split("__", 1)[1].split(".rf.")[0]
    return re.match(r"([A-Za-z]+\d*)", orig).group(1)


def rotated(img: np.ndarray) -> bool:
    """Roboflow fills the area a rotation/shear exposes with pure black.

    Real side-scan has a dark water column, but not as a pure-zero wedge in a
    corner. A corner patch that is >= 90% exactly-black pixels marks a rotated
    or sheared copy.
    """
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = max(8, g.shape[0] // 20)
    corners = [g[:k, :k], g[:k, -k:], g[-k:, :k], g[-k:, -k:]]
    return any((c <= 3).mean() >= 0.9 for c in corners)


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def best_ious(truth, preds):
    """Best IoU each truth box gets from any prediction (not one-to-one: this
    asks 'was the pot hit at all, and how tightly', not an mAP)."""
    return [max((iou(t, p) for p in preds), default=0.0) for t in truth]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--weights", default=str(Path(__file__).resolve().parents[1]
                                             / "experiments" / "gv8b-nosynth" / "weights" / "best.pt"))
    ap.add_argument("--per-family", type=int, default=60, help="train frames sampled per survey family")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--device", default="0")
    a = ap.parse_args()

    files = [l.strip() for l in (DATA / "train_nosynth.txt").read_text().splitlines() if "GHOSTVISION" in l]
    by_fam = collections.defaultdict(list)
    for f in files:
        by_fam[family(f)].append(f)
    rng = random.Random(0)
    sample = [f for fam in sorted(by_fam) for f in rng.sample(by_fam[fam], min(a.per_family, len(by_fam[fam])))]

    from ultralytics import YOLO
    model = YOLO(a.weights)

    rows = []  # one per truth pot box
    frames_rot = collections.Counter()
    for f in sample:
        lbl = Path(f.replace("\\images\\", "\\labels\\").replace("/images/", "/labels/")).with_suffix(".txt")
        truth = []
        if lbl.exists():
            for line in lbl.read_text().splitlines():
                p = line.split()
                if p and int(p[0]) == POT:
                    x, y, w, h = map(float, p[1:5])
                    truth.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2))
        img = cv2.imread(f)
        rot = rotated(img)
        frames_rot[(family(f), rot)] += 1
        if not truth:
            continue
        r = model.predict(f, imgsz=640, conf=a.conf, device=a.device, verbose=False)[0]
        preds = [tuple(b) for b, c in zip(r.boxes.xyxyn.tolist(), r.boxes.cls.tolist()) if int(c) == POT]
        any_cls = [tuple(b) for b in r.boxes.xyxyn.tolist()]
        for t, bi, ba in zip(truth, best_ious(truth, preds), best_ious(truth, any_cls)):
            side = float(np.sqrt((t[2] - t[0]) * (t[3] - t[1]))) * 640
            rows.append({"family": family(f), "rotated": rot, "side_px": side,
                         "best_iou_pot": bi, "best_iou_any_class": ba})

    def rec(rs, thr, key="best_iou_pot"):
        return sum(r[key] >= thr for r in rs) / len(rs) if rs else float("nan")

    def summary(rs):
        return {"boxes": len(rs), "recall_iou50": rec(rs, 0.5), "recall_iou30": rec(rs, 0.3),
                "recall_iou10": rec(rs, 0.1), "hit_as_other_class_iou30": rec(rs, 0.3, "best_iou_any_class") - rec(rs, 0.3),
                "median_side_px": float(np.median([r["side_px"] for r in rs])) if rs else None}

    result = {"weights": a.weights, "conf": a.conf, "frames_sampled": len(sample),
              "overall": summary(rows),
              "by_rotation": {str(k): summary([r for r in rows if r["rotated"] == k]) for k in (False, True)},
              "by_size": {}, "by_family": {},
              "rotated_frame_share_by_family": {}}
    for lo, hi in ((0, 16), (16, 32), (32, 64), (64, 1e9)):
        result["by_size"][f"{lo}-{hi if hi < 1e9 else 'inf'}px"] = summary(
            [r for r in rows if lo <= r["side_px"] < hi])
    for fam in sorted(by_fam):
        result["by_family"][fam] = summary([r for r in rows if r["family"] == fam])
        n_r, n_u = frames_rot[(fam, True)], frames_rot[(fam, False)]
        result["rotated_frame_share_by_family"][fam] = n_r / max(n_r + n_u, 1)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diagnosis.json").write_text(json.dumps(result, indent=2))

    def line(name, s):
        print(f"  {name:18s} n={s['boxes']:4d}  R@.5 {s['recall_iou50']:.3f}  R@.3 {s['recall_iou30']:.3f}  "
              f"R@.1 {s['recall_iou10']:.3f}  other-class +{s['hit_as_other_class_iou30']:.3f}  side {s["median_side_px"] or 0:.0f}px")
    print(f"\nTRAIN frames sampled: {len(sample)}  ({a.per_family}/family), conf {a.conf}")
    line("OVERALL", result["overall"])
    for k, s in result["by_rotation"].items():
        line(f"rotated={k}", s)
    for k, s in result["by_size"].items():
        line(f"side {k}", s)
    for k, s in result["by_family"].items():
        line(f"{k} (rot {result['rotated_frame_share_by_family'][k]:.0%})", s)
    print(f"\nwritten: {OUT / 'diagnosis.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
