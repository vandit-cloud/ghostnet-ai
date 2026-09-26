"""Score the detector with SLICED inference, against whole-frame, on one ruler.

    python ai/scripts/evaluate_sliced.py                     # both modes, test split
    python ai/scripts/evaluate_sliced.py --slice 320 --overlap 0.25
    python ai/scripts/evaluate_sliced.py --modes whole       # validate the evaluator only

Why this exists
---------------
`wreck` recall on boxes under 2% of frame is 0.075 on test -- and **0.40 on
train**, at the same size bands, with a comparable size mix
(ai/experiments/trainfit/). A stride-8 head can therefore localise these boxes;
it does so four to six times better on frames it has seen. The features exist.
What fails is seeing them at 640 px, where the median `ghost_pot` box is 44x44
px and the median sub-2% `wreck` sliver is far smaller.

Sliced inference attacks that from the inference side: run the model on 320 px
crops, and a box that covered 0.2% of the frame covers 0.8% of the crop. Four
times the area, same weights, no training run. If it works it ships to the demo
immediately -- there is no new checkpoint to promote and no ruler to re-baseline.

The full frame must stay in the merge
-------------------------------------
`debris` has a MEDIAN box area of 45.5% of frame and `plane` 24.2%. A 320 px
crop of a 640 px tile cannot contain those objects at all, so slices alone would
destroy the project's two best classes to help its two worst. Every slice pass
therefore also predicts on the whole frame and merges, which is what makes this
a strict addition rather than a trade. `--no-include-full` exists only to
measure that claim rather than assert it.

The evaluator is ours, so it is validated before it is believed
--------------------------------------------------------------
Ultralytics cannot score externally-merged boxes, so AP50 is computed here:
greedy highest-confidence matching at IoU 0.5, 101-point interpolated AP, which
is what Ultralytics does. An evaluator written for one number is worth nothing
until it reproduces a known one, so `--modes whole` scores unsliced predictions
through this same code and the result is compared against the recorded
test_metrics.json of the same weights. Agreement to a few thousandths means the
sliced number can be read on the same axis. Divergence means the evaluator is
wrong and the sliced number is meaningless -- in that order.

Deliberately NOT done here
--------------------------
No NMS tuning sweep, no per-class slice size, no confidence recalibration. The
review floors in ai/ghostnet/config.py were derived against whole-frame
detections (`derive_review_floor.py`); if sliced inference changes the score
distribution, those floors must be re-derived as a separate, announced step
before any of this reaches the decision layer.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_ROOT = Path("E:/New folder/ai/data/processed")
DEFAULT_WEIGHTS = Path("E:/New folder/ai/experiments/gv5-yolo11s/weights/best.pt")

#: Same bands as recall_by_size.py, as fractions of frame area. Kept identical
#: on purpose: a different banding would make the two reports unreadable side
#: by side, which is the only way either of them is useful.
BANDS = [("<0.2%", 0.0, 0.002), ("0.2-0.5%", 0.002, 0.005),
         ("0.5-2%", 0.005, 0.02), (">2%", 0.02, 9.0)]

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def read_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    """YOLO label rows as (cls, xc, yc, w, h), all normalised."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        p = line.split()
        if len(p) >= 5:
            rows.append((int(float(p[0])), *(float(v) for v in p[1:5])))
    return rows


def to_xyxy(xc, yc, w, h, iw, ih):
    return ((xc - w / 2) * iw, (yc - h / 2) * ih, (xc + w / 2) * iw, (yc + h / 2) * ih)


def iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / (area_a + area_b - inter)


def slice_origins(size: int, slice_px: int, overlap: float) -> list[int]:
    """Left/top offsets covering `size`, last slice flush to the far edge.

    Flush rather than padded: a padded final slice changes the object's
    position relative to the crop border, and border effects are exactly what
    this technique is sensitive to.
    """
    if slice_px >= size:
        return [0]
    step = max(1, int(slice_px * (1.0 - overlap)))
    origins = list(range(0, size - slice_px + 1, step))
    if origins[-1] != size - slice_px:
        origins.append(size - slice_px)
    return origins


def nms_per_class(dets: list[tuple], iou_thr: float) -> list[tuple]:
    """Greedy NMS within each class. dets: (cls, conf, x1, y1, x2, y2)."""
    kept: list[tuple] = []
    for cls in {d[0] for d in dets}:
        pool = sorted((d for d in dets if d[0] == cls), key=lambda d: -d[1])
        chosen: list[tuple] = []
        for d in pool:
            if all(iou(d[2:], c[2:]) < iou_thr for c in chosen):
                chosen.append(d)
        kept.extend(chosen)
    return kept


def predict_whole(model, img_path, imgsz, conf, device):
    r = model.predict(str(img_path), imgsz=imgsz, conf=conf, device=device,
                      verbose=False)[0]
    out = []
    if r.boxes is not None:
        for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                            r.boxes.conf.tolist()):
            out.append((int(c), float(cf), *b))
    return out, r.orig_shape  # (h, w)


def predict_sliced(model, img_path, slice_px, overlap, conf, device,
                   include_full, batch, imgsz):
    """Predict on overlapping crops (plus optionally the whole frame), merged."""
    import cv2

    im = cv2.imread(str(img_path))
    if im is None:
        return [], (0, 0)
    ih, iw = im.shape[:2]
    crops, offsets = [], []
    for y in slice_origins(ih, slice_px, overlap):
        for x in slice_origins(iw, slice_px, overlap):
            crops.append(im[y:y + slice_px, x:x + slice_px])
            offsets.append((x, y))

    dets: list[tuple] = []
    for i in range(0, len(crops), batch):
        chunk, offs = crops[i:i + batch], offsets[i:i + batch]
        # imgsz stays at the model's training size: the crop is UPSAMPLED to it,
        # which is the whole mechanism -- a 22 px object becomes ~44 px of input.
        results = model.predict(chunk, imgsz=imgsz, conf=conf, device=device,
                                verbose=False)
        for r, (ox, oy) in zip(results, offs):
            if r.boxes is None:
                continue
            for b, c, cf in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(),
                                r.boxes.conf.tolist()):
                dets.append((int(c), float(cf), b[0] + ox, b[1] + oy,
                             b[2] + ox, b[3] + oy))
    if include_full:
        full, _ = predict_whole(model, img_path, imgsz, conf, device)
        dets.extend(full)
    return dets, (ih, iw)


def average_precision(matched: list[int], confs: list[float], n_gt: int) -> float:
    """101-point interpolated AP50, matching Ultralytics' default method."""
    if n_gt == 0:
        return float("nan")
    if not confs:
        return 0.0
    order = sorted(range(len(confs)), key=lambda i: -confs[i])
    tp = fp = 0
    rec, prec = [], []
    for i in order:
        if matched[i]:
            tp += 1
        else:
            fp += 1
        rec.append(tp / n_gt)
        prec.append(tp / (tp + fp))
    # Monotone envelope, then sample at 101 recall points.
    for i in range(len(prec) - 2, -1, -1):
        prec[i] = max(prec[i], prec[i + 1])
    total = 0.0
    for k in range(101):
        r = k / 100.0
        candidates = [p for p, rr in zip(prec, rec) if rr >= r]
        total += max(candidates) if candidates else 0.0
    return total / 101.0


def score(per_image: dict, gts: dict, names: dict, iou_thr: float, conf_report: float):
    """AP50 / P / R per class, plus recall by size band and background flags."""
    out = {"per_class": {}, "bands": {}, "background": {}}
    band_tally = {n: {b: [0, 0] for b, _, _ in BANDS} for n in names.values()}

    for cid, cname in names.items():
        confs, matched = [], []
        n_gt = 0
        tp_at_report = fp_at_report = gt_hit_at_report = 0
        for key, gt_boxes in gts.items():
            g = [b for c, b, _ in gt_boxes if c == cid]
            n_gt += len(g)
            preds = sorted((d for d in per_image.get(key, []) if d[0] == cid),
                           key=lambda d: -d[1])
            used = set()
            for d in preds:
                best, best_i = 0.0, -1
                for j, gb in enumerate(g):
                    if j in used:
                        continue
                    v = iou(d[2:], gb)
                    if v > best:
                        best, best_i = v, j
                hit = best >= iou_thr
                if hit:
                    used.add(best_i)
                confs.append(d[1])
                matched.append(1 if hit else 0)
                if d[1] >= conf_report:
                    if hit:
                        tp_at_report += 1
                    else:
                        fp_at_report += 1
            # Size bands are recall-only and use the reporting confidence, so
            # they line up with recall_by_size.py rather than with AP.
            hi_preds = [d for d in preds if d[1] >= conf_report]
            for c, gb, area in gt_boxes:
                if c != cid:
                    continue
                band = next(n for n, lo, hi in BANDS if lo <= area < hi)
                band_tally[cname][band][1] += 1
                if any(iou(gb, d[2:]) >= iou_thr for d in hi_preds):
                    band_tally[cname][band][0] += 1
                    gt_hit_at_report += 1
        out["per_class"][cname] = {
            "gt_boxes": n_gt,
            "ap50": average_precision(matched, confs, n_gt),
            f"recall@{conf_report}": (gt_hit_at_report / n_gt) if n_gt else None,
            f"precision@{conf_report}": (tp_at_report / (tp_at_report + fp_at_report))
            if (tp_at_report + fp_at_report) else None,
        }
        out["bands"][cname] = {
            b: {"found": band_tally[cname][b][0], "total": band_tally[cname][b][1],
                "recall": (band_tally[cname][b][0] / band_tally[cname][b][1])
                if band_tally[cname][b][1] else None}
            for b, _, _ in BANDS}

    aps = [v["ap50"] for v in out["per_class"].values() if v["ap50"] == v["ap50"]]
    out["map50"] = sum(aps) / len(aps) if aps else float("nan")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    ap.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    ap.add_argument("--split", default="test")
    ap.add_argument("--modes", nargs="+", default=["whole", "sliced"],
                    choices=("whole", "sliced"))
    ap.add_argument("--slice", type=int, default=320, dest="slice_px")
    ap.add_argument("--overlap", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.01,
                    help="prediction floor for the AP curve; 0.01 not 0.001, because "
                         "slicing multiplies the box count per frame")
    ap.add_argument("--conf-report", type=float, default=0.25,
                    help="deployed operating point, for the recall/precision columns")
    ap.add_argument("--iou", type=float, default=0.5, help="match threshold")
    ap.add_argument("--nms-iou", type=float, default=0.6,
                    help="merge threshold for boxes from overlapping slices")
    ap.add_argument("--batch", type=int, default=8, help="crops per forward pass")
    ap.add_argument("--no-include-full", action="store_true",
                    help="slices only -- measures what the full frame contributes")
    ap.add_argument("--limit", type=int, default=None, help="first N frames (smoke test)")
    ap.add_argument("--device", default=0)
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "ai" / "experiments" / "sliced" / "sliced.json")
    args = ap.parse_args()

    import yaml
    from ultralytics import YOLO

    src = yaml.safe_load((args.data_root / "data.yaml").read_text())
    names = {int(k): v for k, v in src["names"].items()}

    images_dir = args.data_root / args.split / "images"
    labels_dir = args.data_root / args.split / "labels"
    frames = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if args.limit:
        frames = frames[:args.limit]
    print(f"{len(frames)} frames in {args.split}")

    model = YOLO(str(args.weights))
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "weights": str(args.weights),
        "split": args.split,
        "imgsz": args.imgsz,
        "slice_px": args.slice_px,
        "overlap": args.overlap,
        "conf": args.conf,
        "conf_report": args.conf_report,
        "iou_match": args.iou,
        "nms_iou": args.nms_iou,
        "include_full_frame": not args.no_include_full,
        "frames": len(frames),
        "modes": {},
    }

    for mode in args.modes:
        per_image: dict[str, list] = {}
        gts: dict[str, list] = {}
        bg_flagged = bg_total = 0
        print(f"\n[{mode}] predicting ...")
        for i, img in enumerate(frames):
            if i and i % 500 == 0:
                print(f"  {i}/{len(frames)}")
            if mode == "whole":
                dets, (ih, iw) = predict_whole(model, img, args.imgsz, args.conf,
                                               args.device)
            else:
                dets, (ih, iw) = predict_sliced(
                    model, img, args.slice_px, args.overlap, args.conf, args.device,
                    not args.no_include_full, args.batch, args.imgsz)
                dets = nms_per_class(dets, args.nms_iou)
            per_image[img.stem] = dets
            rows = read_labels(labels_dir / f"{img.stem}.txt")
            gts[img.stem] = [(c, to_xyxy(xc, yc, w, h, iw, ih), w * h)
                             for c, xc, yc, w, h in rows]
            if not rows:
                bg_total += 1
                if any(d[1] >= args.conf_report for d in dets):
                    bg_flagged += 1

        result = score(per_image, gts, names, args.iou, args.conf_report)
        result["background"] = {
            "frames": bg_total, "flagged": bg_flagged,
            "rate": (bg_flagged / bg_total) if bg_total else None,
        }
        report["modes"][mode] = result

        print(f"\n[{mode}] mAP50 {result['map50']:.4f}   "
              f"background false-alarm {result['background']['rate']:.4f} "
              f"({bg_flagged}/{bg_total})")
        for cname, v in result["per_class"].items():
            rec = v[f"recall@{args.conf_report}"]
            ap = v["ap50"]
            print(f"  {cname:<10} AP50 {ap:.3f}  " if ap == ap else f"  {cname:<10} AP50   n/a  ",
                  end="")
            print(f"R@{args.conf_report} {rec:.3f}  " if rec is not None else "R    n/a  ",
                  end="")
            print(f"({v['gt_boxes']} boxes)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {args.out}")

    if "whole" in report["modes"] and "sliced" in report["modes"]:
        w, s = report["modes"]["whole"], report["modes"]["sliced"]
        print(f"\n{'class':<12}{'AP50 whole':>12}{'AP50 sliced':>13}{'delta':>9}")
        for cname in names.values():
            a, b = w["per_class"][cname]["ap50"], s["per_class"][cname]["ap50"]
            if a != a or b != b:      # class absent from this sample
                continue
            print(f"{cname:<12}{a:>12.3f}{b:>13.3f}{b - a:>+9.3f}")
        print(f"{'mAP50':<12}{w['map50']:>12.3f}{s['map50']:>13.3f}"
              f"{s['map50'] - w['map50']:>+9.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
