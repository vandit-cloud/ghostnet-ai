"""Score a ghost_net model -- U-Net OR YOLO-seg -- through ONE harness.

    python ai/scripts/evaluate_net_unet.py --weights ai/experiments/gvU1-unet-s0/weights/best.pt
    python ai/scripts/evaluate_net_unet.py --yolo --weights ai/experiments/gv7d3-netseg-s0/weights/best.pt

Why one script for both
-----------------------
Pixel Dice has never been measured for the YOLO-seg runs, and a U-Net Dice is
meaningless without it. Computing both through the same code -- the same
masks, the same native resolution, the same pooling -- is the only way the
two numbers can be compared. The same goes for box recall: Ultralytics'
recall is taken at the max-F1 confidence, per polygon, which a semantic model
cannot reproduce, so here both models are scored by the same rule at a FIXED
threshold.

What it reports, per threshold
------------------------------
* Dice / IoU on the test split, pooled over all pixels of all 11 chips (and
  the per-chip mean, which weights small chips equally).
* Centroid detection rate, through centroid_metric.py's own matcher (rule C,
  tolerance 0.10), imported rather than copied.
* Box recall / precision at IoU >= 0.5, one box per truth polygon against one
  box per predicted outline. Structurally harsh on a U-Net: two touching bead
  chains become one blob and one box, which scores as a miss. Reported, never
  used alone to judge a U-Net.
* False alarms on the 100 held-out empty chips (neg_holdout), per seabed type.

Harness check: run with --yolo on gv7d3-netseg-s0 first. Its centroid numbers
must match gv7d3's centroid_metrics.json; if they do not, this harness is
wrong and nothing it says about a U-Net can be trusted.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _net_unet as U  # noqa: E402
from centroid_metric import (Shape, aspect_correct, bootstrap_ci,  # noqa: E402
                             cluster_shapes, load_truth, match_centroids)

DATA = Path("E:/New folder/ai/data/net_seg_hardneg")
TOLERANCE = 0.10


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match_boxes(truth: list, preds: list, thr: float = 0.5) -> int:
    """Greedy one-to-one at IoU >= thr, best pairs first. Returns matched count."""
    pairs = sorted(((iou(t, p), ti, pi) for ti, t in enumerate(truth)
                    for pi, p in enumerate(preds)), reverse=True)
    mt, mp = set(), set()
    for v, ti, pi in pairs:
        if v < thr:
            break
        if ti not in mt and pi not in mp:
            mt.add(ti)
            mp.add(pi)
    return len(mt)


class UNetRunner:
    def __init__(self, weights: str, device: str):
        self.model, _ = U.load_checkpoint(Path(weights), device)
        self.device = device
        self.cache: dict[str, np.ndarray] = {}

    def detect(self, img: Path, conf: float, h: int, w: int):
        """-> (union mask HxW bool, [ {points, box, score} ])"""
        key = str(img)
        if key not in self.cache:  # one forward pass serves every threshold
            self.cache[key] = U.predict_prob(self.model, U.read_gray(img), self.device)
        prob = self.cache[key]
        return prob >= conf, U.blobs(prob, conf)


class YoloRunner:
    def __init__(self, weights: str, device: str):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.device = device

    def detect(self, img: Path, conf: float, h: int, w: int):
        # Two passes, on purpose. Outlines and boxes come from the DEFAULT
        # (retina_masks=False) pass, which is what centroid_metric.py and the
        # app use -- with retina masks the contours shift enough to move
        # gv7d3-s0 from 30 to 32 centroid hits, failing the harness check.
        # The Dice mask comes from the retina pass, i.e. native resolution,
        # the same resolution the U-Net's Dice is measured at.
        kw = dict(imgsz=U.IMGSZ, conf=conf, device=self.device, verbose=False)
        r = self.model.predict(str(img), **kw)[0]
        rr = self.model.predict(str(img), retina_masks=True, **kw)[0]
        union = np.zeros((h, w), bool)
        if rr.masks is not None:
            union = (rr.masks.data.cpu().numpy() > 0.5).any(axis=0)
        dets = []
        if r.masks is not None and r.boxes is not None:
            for i, poly in enumerate(r.masks.xyn):
                x1, y1, x2, y2 = r.boxes.xyxyn[i].tolist()
                dets.append({"points": [(float(x), float(y)) for x, y in poly],
                             "box": (x1, y1, x2, y2), "score": float(r.boxes.conf[i])})
        return union, dets


def score_test(runner, data: Path, conf: float) -> dict:
    inter = total = 0
    per_chip_dice, per_image = [], []
    tp_box = n_truth_box = n_pred_box = 0
    for img, lbl in U.list_split(data, "test"):
        gray = U.read_gray(img)
        h, w = gray.shape
        aspect = h / w
        polys = U.read_polygons(lbl)
        truth_mask = U.polygons_to_mask(polys, h, w) > 0
        pred_mask, dets = runner.detect(img, conf, h, w)

        i_, t_ = int((pred_mask & truth_mask).sum()), int(pred_mask.sum() + truth_mask.sum())
        inter, total = inter + i_, total + t_
        per_chip_dice.append(2 * i_ / t_ if t_ else 1.0)

        dets = [d for d in dets if d["points"]]
        truth_shapes = load_truth(lbl, aspect)
        pred_shapes = [Shape(points=aspect_correct(d["points"], aspect), score=d["score"])
                       for d in dets]
        hit, miss, fa = match_centroids(truth_shapes, pred_shapes, TOLERANCE)
        per_image.append({"image": img.name, "truth_nets": len(cluster_shapes(truth_shapes, TOLERANCE)),
                          "predictions": len(dets), "hits": hit, "misses": miss, "false_alarms": fa})

        tboxes = [(p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()) for p in polys]
        tp_box += match_boxes(tboxes, [d["box"] for d in dets])
        n_truth_box += len(tboxes)
        n_pred_box += len(dets)

    hits = sum(r["hits"] for r in per_image)
    nets = hits + sum(r["misses"] for r in per_image)
    fas = sum(r["false_alarms"] for r in per_image)
    dice = 2 * inter / total if total else float("nan")
    return {
        "dice_pooled": dice,
        "iou_pooled": dice / (2 - dice) if dice == dice else float("nan"),
        "dice_per_chip_mean": float(np.mean(per_chip_dice)),
        "centroid_detection_rate": hits / nets if nets else float("nan"),
        "centroid_precision": hits / (hits + fas) if hits + fas else float("nan"),
        "centroid_hits": hits, "truth_nets": nets, "centroid_false_alarms": fas,
        "centroid_bootstrap": bootstrap_ci(per_image, 1000),
        "box_recall_iou50": tp_box / n_truth_box if n_truth_box else float("nan"),
        "box_precision_iou50": tp_box / n_pred_box if n_pred_box else float("nan"),
        "box_tp": tp_box, "truth_boxes": n_truth_box, "pred_boxes": n_pred_box,
        "per_image": per_image,
    }


def score_negatives(runner, neg_dir: Path, conf: float) -> dict:
    fired, outlines = {}, 0
    for img in sorted(neg_dir.glob("*")):
        gray = U.read_gray(img)
        _, dets = runner.detect(img, conf, *gray.shape)
        fired[img.name] = len(dets)
        outlines += len(dets)
    by = collections.defaultdict(lambda: [0, 0])
    for k, n in fired.items():
        g = k.split("__")[1].rsplit("_", 1)[0]
        by[g][0] += 1
        by[g][1] += n > 0
    frames = sum(n > 0 for n in fired.values())
    return {"images": len(fired), "frames_with_false_alarm": frames,
            "false_alarm_frame_rate": frames / max(len(fired), 1),
            "false_outlines_per_frame": outlines / max(len(fired), 1),
            "by_group": {g: f"{hit}/{tot}" for g, (tot, hit) in sorted(by.items())}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--weights", required=True)
    ap.add_argument("--yolo", action="store_true", help="weights are a YOLO-seg best.pt")
    ap.add_argument("--data", type=Path, default=DATA,
                    help="its test/ is md5-identical to net_seg/test; neg_holdout/ lives here")
    ap.add_argument("--conf", type=float, nargs="+", default=None,
                    help="default: 0.25 0.5 for YOLO, 0.25 0.5 0.75 for U-Net")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    confs = a.conf or ([0.25, 0.5] if a.yolo else [0.25, 0.5, 0.75])
    runner = YoloRunner(a.weights, a.device) if a.yolo else UNetRunner(a.weights, a.device)
    result = {"weights": a.weights, "model": "yolo-seg" if a.yolo else "unet",
              "data": str(a.data), "tolerance": TOLERANCE,
              "min_blob_share": None if a.yolo else U.MIN_BLOB_SHARE, "by_conf": {}}
    for c in confs:
        t = score_test(runner, a.data, c)
        n = score_negatives(runner, a.data / "neg_holdout" / "images", c)
        result["by_conf"][str(c)] = {"test": t, "negatives": n}
        bs = t["centroid_bootstrap"]
        print(f"conf {c}:  Dice {t['dice_pooled']:.3f} (per-chip {t['dice_per_chip_mean']:.3f})  "
              f"centroid {t['centroid_detection_rate']:.3f} ({t['centroid_hits']}/{t['truth_nets']}, "
              f"CI {bs['ci95_low']:.2f}-{bs['ci95_high']:.2f}) prec {t['centroid_precision']:.3f}  "
              f"box R {t['box_recall_iou50']:.3f} P {t['box_precision_iou50']:.3f}  "
              f"empty-chip FA {n['frames_with_false_alarm']}/{n['images']}")
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
