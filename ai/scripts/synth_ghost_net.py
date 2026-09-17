"""Copy-paste synthesis for the ghost_net class (plan J2).

    python ai/scripts/synth_ghost_net.py --n 1500
    python ai/scripts/synth_ghost_net.py --n 20 --preview     # look before you commit

Reads  ai/data/annotate/ghost_net/{images,labels}   -- 298 hand-drawn real boxes
       ai/data/processed/train/                     -- empty-label seabed tiles
Writes ai/data/interim/GHOSTNET-SYNTH/train/{images,labels}

Why this is not inventing ground truth
--------------------------------------
The build plans forbid fabricating labels, and this does not. Every net pixel
here is a REAL net pixel, photographed by a real sonar; only the arrangement is
synthetic, and the position is not guessed but known exactly, because we chose
it. That is a different act from drawing a box where a net might be.

`ghost_net` has 215 training boxes and scores mAP50 0.009 with recall 0.000.
`ghost_pot` needed 7,434 boxes to reach 0.314. There is no more real net data
to collect -- China-Offshore's 73 chips are the only public side-scan nets
anyone has found -- so the choice is synthesis or leaving the headline class
permanently broken.

Multiplicative compositing, not pasting a rectangle
----------------------------------------------------
The obvious implementation crops a box from a source chip and pastes it onto a
background. It fails in a specific, well-known way: the paste boundary is a
brightness discontinuity, and a detector will happily learn the SEAM instead of
the net. It scores beautifully on synthetic data and finds nothing real.

A net does not replace the seabed, it ATTENUATES the return from it. So the
source box is separated into the net and the seabed it sits on -- a
morphological closing with a kernel wider than the netting estimates what the
seabed would look like without it -- and only the ratio between them is
transferred:

    attenuation = source / closing(source)        clipped to <= 1.0
    output      = background * attenuation

Where the source has no net the ratio is 1.0 and the background passes through
untouched, so the composite has no boundary at all. There is nothing to learn
except the net.

Choices that are deliberate
---------------------------
* ROTATION IS 90-DEGREE ONLY. Netting is one to three pixels wide; an arbitrary
  rotation interpolates it into a blur that no longer looks like the thing.
* BACKGROUNDS COME FROM THE TRAIN SPLIT ONLY. Compositing onto val or test
  seabed would leak the evaluation set into training through the back door,
  which is exactly the failure build_dataset.py exists to prevent.
* THE LABEL IS THE ATTENUATED PIXELS, not the source rectangle. After a flip or
  a scale the tight box moves, and a stale rectangle would teach a systematic
  offset.
* OUTPUT IS TRAIN-ONLY, enforced in SPLIT_POLICY. Synthetic data must never
  reach the test split: a score on generated nets is self-congratulation. The
  36 real held-out boxes remain the only thing that counts.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

SRC = AI_ROOT / "data" / "annotate" / "ghost_net"
TRAIN = AI_ROOT / "data" / "processed" / "train"
DEST = AI_ROOT / "data" / "interim" / "GHOSTNET-SYNTH"
IMAGE_EXTS = (".png", ".jpg", ".jpeg")

#: Wider than the netting, narrower than the features we must not erase.
CLOSE_KSIZE = 9
#: Below this the pixel counts as net for the purpose of the bounding box.
NET_ATTENUATION = 0.92
#: Never brighten, and never black out completely.
MIN_ATTENUATION = 0.15
#: Smallest side of a composited box. A net scaled down to eight pixels is a
#: label the detector cannot learn and the annotation convention would never
#: have drawn by hand.
MIN_BOX_PX = 14


def load_sources(rng: random.Random) -> list:
    """Every hand-drawn net box, as an attenuation map."""
    import cv2
    import numpy as np

    out = []
    for lp in sorted((SRC / "labels").glob("*.txt")):
        if lp.stem == "classes":
            continue
        img = next((SRC / "images" / (lp.stem + e) for e in IMAGE_EXTS
                    if (SRC / "images" / (lp.stem + e)).exists()), None)
        if img is None:
            continue
        g = cv2.imread(str(img), cv2.IMREAD_GRAYSCALE)
        if g is None:
            continue
        h, w = g.shape
        for line in lp.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            _c, cx, cy, bw, bh = (float(v) for v in line.split())
            x1, y1 = max(0, int((cx - bw / 2) * w)), max(0, int((cy - bh / 2) * h))
            x2, y2 = min(w, int((cx + bw / 2) * w)), min(h, int((cy + bh / 2) * h))
            patch = g[y1:y2, x1:x2]
            if patch.size == 0 or min(patch.shape) < 8:
                continue
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_KSIZE, CLOSE_KSIZE))
            seabed = cv2.morphologyEx(patch, cv2.MORPH_CLOSE, kernel).astype(np.float32)
            atten = patch.astype(np.float32) / np.maximum(seabed, 1.0)
            atten = np.clip(atten, MIN_ATTENUATION, 1.0)
            if (atten < NET_ATTENUATION).mean() < 0.02:
                continue                      # nothing much in this box
            out.append(atten)
    rng.shuffle(out)
    return out


#: A background must be bright enough for an attenuation to show, and textured
#: enough to be seabed. Both thresholds exist because the first preview pasted
#: nets onto pure-black nadir and padding tiles, where multiplying by 0.85
#: leaves 0 and the label points at nothing.
MIN_BG_MEAN = 60.0
MIN_BG_STD = 8.0
MAX_DEAD_ROWS = 0.02


def backgrounds(limit: int | None = None) -> list[Path]:
    """Usable empty seabed from the TRAIN split only -- never val or test.

    Empty-label is necessary but nowhere near sufficient. A tile can be
    unlabelled because it is padding, because it is the black water column, or
    because it is a dropout -- and a net composited onto any of those is a
    label with no object under it, which is precisely the kind of fabricated
    ground truth this whole approach is supposed to avoid.
    """
    import cv2

    from ghostnet.dropout import invalid_row_mask

    keep, rejected = [], {"dark": 0, "flat": 0, "dropout": 0}
    for lp in sorted((TRAIN / "labels").glob("*.txt")):
        if lp.stat().st_size:
            continue
        img = next((TRAIN / "images" / (lp.stem + e) for e in IMAGE_EXTS
                    if (TRAIN / "images" / (lp.stem + e)).exists()), None)
        if img is None:
            continue
        g = cv2.imread(str(img), cv2.IMREAD_GRAYSCALE)
        if g is None:
            continue
        if g.mean() < MIN_BG_MEAN:
            rejected["dark"] += 1
        elif g.std() < MIN_BG_STD:
            rejected["flat"] += 1
        elif invalid_row_mask(g).mean() > MAX_DEAD_ROWS:
            rejected["dropout"] += 1
        else:
            keep.append(img)
        if limit and len(keep) >= limit:
            break
    print(f"  backgrounds rejected: {rejected['dark']} too dark, "
          f"{rejected['flat']} featureless, {rejected['dropout']} carrying dropouts")
    return keep


def transform(atten, rng: random.Random):
    import cv2
    import numpy as np

    a = atten
    if rng.random() < 0.5:
        a = a[:, ::-1]
    if rng.random() < 0.5:
        a = a[::-1, :]
    for _ in range(rng.choice((0, 1, 2, 3))):
        a = np.rot90(a)
    scale = rng.uniform(0.7, 1.35)
    h, w = a.shape
    nh, nw = max(8, int(h * scale)), max(8, int(w * scale))
    return cv2.resize(np.ascontiguousarray(a), (nw, nh), interpolation=cv2.INTER_LINEAR)


def composite(bg, atten, rng: random.Random):
    """Multiply a net's attenuation into a background. Returns (image, box)."""
    import numpy as np

    H, W = bg.shape
    h, w = atten.shape
    if h >= H or w >= W:
        return None, None
    y = rng.randint(0, H - h - 1)
    x = rng.randint(0, W - w - 1)

    out = bg.astype(np.float32)
    out[y:y + h, x:x + w] *= atten
    out = np.clip(out, 0, 255).astype(np.uint8)

    # The label is where the net actually is, after the transform.
    ys, xs = np.where(atten < NET_ATTENUATION)
    if ys.size == 0:
        return None, None
    bx1, by1 = x + int(xs.min()), y + int(ys.min())
    bx2, by2 = x + int(xs.max()) + 1, y + int(ys.max()) + 1
    if bx2 - bx1 < MIN_BOX_PX or by2 - by1 < MIN_BOX_PX:
        return None, None
    return out, (bx1, by1, bx2, by2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Composite real net returns onto real seabed.")
    ap.add_argument("--n", type=int, default=1500, help="frames to generate")
    ap.add_argument("--per-frame", type=int, default=2, help="max nets composited per frame")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--preview", action="store_true", help="write a contact sheet and stop")
    args = ap.parse_args()

    import cv2
    import numpy as np

    from ghostnet.taxonomy import CLASS_TO_ID

    if "ghost_net" not in CLASS_TO_ID:
        print("ghost_net is not a training class -- add it to taxonomy.py first")
        return 1

    rng = random.Random(args.seed)
    sources = load_sources(rng)
    bgs = backgrounds(limit=1200 if args.preview else None)
    print()
    print(f"  {len(sources)} usable net attenuation maps from {SRC.name}")
    print(f"  {len(bgs)} empty seabed tiles from the TRAIN split")
    if not sources or not bgs:
        print("  nothing to work with")
        return 1

    cls_id = CLASS_TO_ID["ghost_net"]
    if args.preview:
        tiles = []
        for i in range(9):
            bg = cv2.imread(str(rng.choice(bgs)), cv2.IMREAD_GRAYSCALE)
            img, box = composite(bg, transform(rng.choice(sources), rng), rng)
            if img is None:
                continue
            v = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            cv2.rectangle(v, box[:2], box[2:], (60, 255, 60), 2)
            tiles.append(cv2.resize(v, (320, 320)))
        sheet = np.zeros((3 * 320, 3 * 320, 3), np.uint8)
        for i, t in enumerate(tiles[:9]):
            sheet[(i // 3) * 320:(i // 3 + 1) * 320, (i % 3) * 320:(i % 3 + 1) * 320] = t
        out = AI_ROOT / "data" / "annotate" / "ghost_net" / "_guide" / "09_synthetic_preview.jpg"
        cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"\n  wrote {out}")
        print("  Look for a visible paste boundary. There should not be one.")
        return 0

    for sub in ("images", "labels"):
        d = DEST / "train" / sub
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*"):
            old.unlink()

    made = boxes = 0
    for i in range(args.n):
        bg = cv2.imread(str(rng.choice(bgs)), cv2.IMREAD_GRAYSCALE)
        if bg is None:
            continue
        img, rows = bg, []
        for _ in range(rng.randint(1, args.per_frame)):
            got, box = composite(img, transform(rng.choice(sources), rng), rng)
            if got is None:
                continue
            img = got
            H, W = img.shape
            x1, y1, x2, y2 = box
            rows.append(f"{cls_id} {(x1 + x2) / 2 / W:.6f} {(y1 + y2) / 2 / H:.6f} "
                        f"{(x2 - x1) / W:.6f} {(y2 - y1) / H:.6f}")
        if not rows:
            continue
        stem = f"synthnet_{i:05d}"
        cv2.imwrite(str(DEST / "train" / "images" / f"{stem}.png"), img)
        (DEST / "train" / "labels" / f"{stem}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
        made += 1
        boxes += len(rows)

    (DEST / "synthesis_report.json").write_text(json.dumps({
        "frames": made, "boxes": boxes,
        "source_boxes": len(sources), "backgrounds": len(bgs),
        "seed": args.seed, "close_ksize": CLOSE_KSIZE,
        "net_attenuation_threshold": NET_ATTENUATION,
        "method": "multiplicative attenuation transfer; real net returns on real train-split seabed",
        "warning": "SYNTHETIC. Train split only -- see SPLIT_POLICY. Never score on this.",
    }, indent=2), encoding="utf-8")

    print(f"\n  {made} frames, {boxes} ghost_net boxes -> {DEST}")
    print("  next:  python ai/scripts/build_dataset.py")
    print("  These are TRAIN ONLY. The 36 real held-out boxes stay the only score.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
