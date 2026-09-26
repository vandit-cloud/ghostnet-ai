"""Side-by-side sheet: truth vs YOLO-seg (gv7d3-s0) vs U-Net (gvU1n-s1).

    python ai/scripts/build_unet_comparison_sheet.py

Writes ai/experiments/unet-scoring/compare_test.png (the 11 test chips) and
compare_negatives.png (the empty chips where either model fires, up to 8).
Each model is shown at its own operating point: YOLO conf 0.25, U-Net pixel 0.5.
Green = truth polygons, magenta = model outline. Header counts are centroid
hits/nets and false alarms, from the same harness as the numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _net_unet as U  # noqa: E402
from evaluate_net_unet import UNetRunner, YoloRunner  # noqa: E402
from centroid_metric import Shape, aspect_correct, load_truth, match_centroids  # noqa: E402

DATA = Path("E:/New folder/ai/data/net_seg_hardneg")
OUT = Path(__file__).resolve().parents[1] / "experiments" / "unet-scoring"
YOLO_W = "E:/New folder/ai/experiments/gv7d3-netseg-s0/weights/best.pt"
UNET_W = str(OUT.parent / "gvU1n-unet-hardneg-s1" / "weights" / "best.pt")
CELL = 300


def panel(gray, outlines, colour, title):
    h, w = gray.shape
    im = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for pts in outlines:
        p = np.round(np.array(pts) * [w, h]).astype(np.int32)
        if len(p) >= 2:
            cv2.polylines(im, [p], True, colour, 2)
    s = CELL / max(h, w)
    im = cv2.resize(im, (round(w * s), round(h * s)))
    canvas = np.full((CELL + 26, CELL, 3), 30, np.uint8)
    canvas[26:26 + im.shape[0], :im.shape[1]] = im
    cv2.putText(canvas, title, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def main() -> int:
    yolo, unet = YoloRunner(YOLO_W, "cpu"), UNetRunner(UNET_W, "cpu")
    rows = []
    for img, lbl in U.list_split(DATA, "test"):
        g = U.read_gray(img)
        h, w = g.shape
        asp = h / w
        truth = [p.tolist() for p in U.read_polygons(lbl)]
        cells = [panel(g, [], (0, 0, 0), img.stem[:22]), panel(g, truth, (0, 220, 0), "truth")]
        for name, r, c in (("YOLO-seg gv7d3", yolo, 0.25), ("U-Net gvU1n", unet, 0.5)):
            _, dets = r.detect(img, c, h, w)
            hit, miss, fa = match_centroids(load_truth(lbl, asp),
                                            [Shape(points=aspect_correct(d["points"], asp)) for d in dets], 0.10)
            cells.append(panel(g, [d["points"] for d in dets], (255, 0, 255),
                               f"{name}: {hit}/{hit + miss} nets, {fa} FA"))
        rows.append(np.hstack(cells))
    cv2.imwrite(str(OUT / "compare_test.png"), np.vstack(rows))

    rows = []
    for img in sorted((DATA / "neg_holdout" / "images").glob("*")):
        g = U.read_gray(img)
        h, w = g.shape
        yd = yolo.detect(img, 0.25, h, w)[1]
        ud = unet.detect(img, 0.5, h, w)[1]
        if yd or ud:
            rows.append(np.hstack([
                panel(g, [], (0, 0, 0), img.stem.split("__")[1]),
                panel(g, [d["points"] for d in yd], (255, 0, 255), f"YOLO-seg: {len(yd)} false"),
                panel(g, [d["points"] for d in ud], (255, 0, 255), f"U-Net: {len(ud)} false")]))
        if len(rows) == 8:
            break
    cv2.imwrite(str(OUT / "compare_negatives.png"), np.vstack(rows))
    print("written:", OUT / "compare_test.png", OUT / "compare_negatives.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
