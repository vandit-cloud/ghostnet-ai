"""Mine candidate MISSING ghost_pot boxes from the staged hand-label set.

    python ai/scripts/mine_ghost_pot_candidates.py --weights ai/experiments/gv8b-nosynth/weights/best.pt

Why (ai/experiments/ghost-pot-diagnosis/NOTES.md): many real pots in
GHOSTVISION carry no box, so the detector is trained to call them background,
and it scores its true pots about as low as its false ones. The pots it still
finds WITHOUT a matching label are the cheapest place to look for the missing
ones: a reviewer answers "pot or not" per candidate instead of searching 2,533
frames.

Reads  E:/New folder/ai/data/annotate/ghost_pot/{images,labels}  (staged by
       stage_ghost_pot_relabel.py; labels are class 0 = ghost_pot)
Writes <out>/candidates.json  one entry per detector pot with no existing box
       <out>/sheets/sheet_NNN.png  numbered crops for review

A candidate is a ghost_pot prediction whose IoU with every existing box is
below --match-iou and whose centre lies outside every existing box. Nothing
here edits a label; accepting candidates is a separate, explicit step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

STAGED = Path("E:/New folder/ai/data/annotate/ghost_pot")


def read_boxes(label: Path, w: int, h: int) -> list[tuple[float, float, float, float]]:
    out = []
    if label.exists():
        for line in label.read_text(encoding="utf-8").splitlines():
            p = line.split()
            if len(p) >= 5:
                x, y, bw, bh = (float(v) for v in p[1:5])
                out.append(((x - bw / 2) * w, (y - bh / 2) * h, (x + bw / 2) * w, (y + bh / 2) * h))
    return out


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def inside(pt, box) -> bool:
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def crop(img, box, size=112, context=2.5):
    """A square crop centred on the box, `context` times its larger side
    (at least 48 px), with the box drawn, resized to `size`."""
    h, w = img.shape[:2]
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    half = max(24.0, context * max(box[2] - box[0], box[3] - box[1]) / 2)
    x0, y0, x1, y1 = int(cx - half), int(cy - half), int(cx + half), int(cy + half)
    pad = max(0, -x0, -y0, x1 - w, y1 - h)
    canvas = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    c = canvas[y0 + pad:y1 + pad, x0 + pad:x1 + pad].copy()
    s = size / c.shape[0]
    c = cv2.resize(c, (size, size), interpolation=cv2.INTER_LINEAR)
    bx0, by0 = int((box[0] - x0) * s), int((box[1] - y0) * s)
    bx1, by1 = int((box[2] - x0) * s), int((box[3] - y0) * s)
    cv2.rectangle(c, (bx0, by0), (bx1, by1), (0, 255, 0), 1)
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--staged", default=str(STAGED))
    ap.add_argument("--out", default=None, help="default <staged>/_mined")
    ap.add_argument("--conf", type=float, default=0.03)
    ap.add_argument("--match-iou", type=float, default=0.3)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--per-sheet", type=int, default=60)
    args = ap.parse_args()

    from ultralytics import YOLO

    staged = Path(args.staged)
    out = Path(args.out) if args.out else staged / "_mined"
    (out / "sheets").mkdir(parents=True, exist_ok=True)

    model = YOLO(args.weights)
    pot_ids = [k for k, v in model.names.items() if v == "ghost_pot"]
    if len(pot_ids) != 1:
        print(f"no single ghost_pot class in {model.names}")
        return 1
    pot = pot_ids[0]

    images = sorted(p for p in (staged / "images").iterdir() if p.suffix.lower() in (".jpg", ".png"))
    cands, matched, total_pred = [], 0, 0
    for i in range(0, len(images), 16):
        chunk = images[i:i + 16]
        for img_path, r in zip(chunk, model.predict([str(p) for p in chunk], imgsz=640, conf=args.conf,
                                                    device=args.device, verbose=False)):
            h, w = r.orig_shape
            truth = read_boxes(staged / "labels" / f"{img_path.stem}.txt", w, h)
            for b in r.boxes:
                if int(b.cls[0]) != pot:
                    continue
                total_pred += 1
                box = [float(v) for v in b.xyxy[0].tolist()]
                centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
                if any(iou(box, t) >= args.match_iou or inside(centre, t) for t in truth):
                    matched += 1
                    continue
                cands.append({"image": img_path.name, "xyxy": [round(v, 1) for v in box],
                              "score": round(float(b.conf[0]), 4), "wh": [w, h]})
        print(f"\r  {min(i + 16, len(images))}/{len(images)} frames, {len(cands)} candidates", end="", flush=True)
    print()

    cands.sort(key=lambda c: c["score"], reverse=True)
    for k, c in enumerate(cands):
        c["id"] = k
    (out / "candidates.json").write_text(json.dumps({
        "weights": args.weights, "conf": args.conf, "match_iou": args.match_iou,
        "frames": len(images), "pot_predictions": total_pred, "matched_existing": matched,
        "candidates": cands}, indent=1), encoding="utf-8")

    cache: dict[str, np.ndarray] = {}
    for s in range(0, len(cands), args.per_sheet):
        tiles = []
        for c in cands[s:s + args.per_sheet]:
            if c["image"] not in cache:
                cache = {c["image"]: cv2.imread(str(staged / "images" / c["image"]))}
            t = crop(cache[c["image"]], c["xyxy"])
            cv2.rectangle(t, (0, 0), (58, 14), (0, 0, 0), -1)
            cv2.putText(t, f'{c["id"]} {c["score"]:.2f}', (2, 11), 0, 0.36, (0, 255, 255), 1)
            tiles.append(t)
        while len(tiles) % 10:
            tiles.append(np.zeros_like(tiles[0]))
        sheet = np.vstack([np.hstack(tiles[r:r + 10]) for r in range(0, len(tiles), 10)])
        cv2.imwrite(str(out / "sheets" / f"sheet_{s // args.per_sheet:03d}.png"), sheet)

    print(f"  {total_pred} ghost_pot predictions at conf {args.conf}: {matched} on an existing box, "
          f"{len(cands)} candidates -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
