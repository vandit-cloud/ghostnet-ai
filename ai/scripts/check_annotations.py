"""Check hand-drawn ghost_net boxes before they reach the dataset.

    python ai/scripts/check_annotations.py
    python ai/scripts/check_annotations.py --render        # write an overlay sheet
    python ai/scripts/check_annotations.py --max-cover 0.25

Reads  ai/data/annotate/ghost_net/{images,labels}
Writes nothing, unless --render.

Why a coverage check and not just "does it parse"
-------------------------------------------------
The failure mode for this particular class is not a malformed file. It is a
box that is technically valid and semantically useless: one rectangle drawn
around a whole net array, 60-70% of the frame, mostly empty seabed.

That matters more here than in a normal detection task. The negative set now
holds 782 trench_gully chips that are nothing but thin curvilinear features on
grey seabed. At whole-frame scale a loose net box and a gully tile are the
same picture, and the only thing separating the two classes is how tightly the
box is drawn. So box tightness IS the annotation quality metric, and it is
worth measuring rather than eyeballing across 73 files.

The thresholds below are calibrated on the chips reviewed so far, where good
boxes landed at 2-10% of frame. They are advisory: this script never edits or
rejects anything, it only tells you where to look.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = AI_ROOT / "data" / "annotate" / "ghost_net"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def find_image(images_dir: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = images_dir / (stem + ext)
        if p.exists():
            return p
    return None


def parse(label: Path) -> tuple[list[tuple[float, ...]], list[str]]:
    """Boxes as (cls, cx, cy, w, h), plus any lines that are not that."""
    boxes, errs = [], []
    for n, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            errs.append(f"line {n}: expected 5 fields, got {len(parts)}")
            continue
        try:
            cls = int(parts[0])
            cx, cy, w, h = (float(v) for v in parts[1:])
        except ValueError:
            errs.append(f"line {n}: non-numeric field")
            continue
        boxes.append((cls, cx, cy, w, h))
    return boxes, errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Sanity-check hand-drawn YOLO boxes.")
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--max-cover", type=float, default=0.35,
                    help="flag a box covering more than this fraction of the frame")
    ap.add_argument("--min-cover", type=float, default=0.0008,
                    help="flag a box smaller than this (usually a stray click)")
    ap.add_argument("--max-aspect", type=float, default=8.0,
                    help="flag a box longer than this many times its width, or vice versa")
    # 0.75, not the 0.60 first guessed. These chips are CROPS the source cut
    # around the target, so the object is expected to dominate the frame -- a
    # dense net array legitimately reaches 70%. Reviewing the six highest-union
    # images by eye, five were correctly high and one (HN_003) was genuinely
    # over-boxed, so a threshold under 70% is mostly false alarms.
    ap.add_argument("--max-union", type=float, default=0.75,
                    help="flag an image whose boxes TOGETHER cover more than this")
    ap.add_argument("--render", action="store_true",
                    help="write review_<stem>.png overlays for every flagged image")
    args = ap.parse_args()

    base = Path(args.dir)
    images_dir, labels_dir = base / "images", base / "labels"
    if not labels_dir.is_dir():
        print(f"no labels dir at {labels_dir}")
        return 1

    total_images = sum(1 for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    labels = sorted(p for p in labels_dir.glob("*.txt") if p.stem != "classes")
    strays = sorted(labels_dir.glob("*.xml"))

    covers: list[float] = []
    unions: list[tuple[str, float, int]] = []
    n_boxes = 0
    n_empty = 0
    problems: list[tuple[str, str]] = []
    flagged: set[str] = set()

    for lbl in labels:
        img = find_image(images_dir, lbl.stem)
        if img is None:
            problems.append((lbl.stem, "no matching image"))
            flagged.add(lbl.stem)
            continue

        boxes, errs = parse(lbl)
        for e in errs:
            problems.append((lbl.stem, e))
            flagged.add(lbl.stem)
        if not boxes:
            n_empty += 1
            continue

        from PIL import Image
        with Image.open(img) as im:
            W, H = im.size

        # UNION of all boxes, not just the biggest one. Per-box coverage is
        # gameable: eight boxes at 10% each pass every per-box threshold while
        # between them claiming 80% of the frame is net. That is the original
        # whole-frame mistake reassembled out of pieces, and only the union
        # shows it.
        mask = [[False] * 64 for _ in range(64)]
        for _c, cx, cy, w, h in boxes:
            for gy in range(64):
                for gx in range(64):
                    if abs((gx + 0.5) / 64 - cx) <= w / 2 and abs((gy + 0.5) / 64 - cy) <= h / 2:
                        mask[gy][gx] = True
        union = sum(sum(row) for row in mask) / (64 * 64)
        unions.append((lbl.stem, union, len(boxes)))
        if union > args.max_union:
            problems.append((lbl.stem, f"boxes cover {union:.0%} of the frame between them"
                                       " -- is the net really everywhere, or is this the"
                                       " whole-frame box in pieces?"))
            flagged.add(lbl.stem)

        for i, (cls, cx, cy, w, h) in enumerate(boxes, 1):
            n_boxes += 1
            cover = w * h
            covers.append(cover)
            px_w, px_h = w * W, h * H

            if cls != 0:
                problems.append((lbl.stem, f"box {i}: class id {cls}, expected 0 (ghost_net)"))
                flagged.add(lbl.stem)
            # One pixel of slack. A box dragged flush to the edge comes back
            # as 1.0000001 after the round trip through normalised floats, and
            # flagging that is noise -- it cost a batch review once.
            ex = max(0.0, -(cx - w / 2)) * W, max(0.0, -(cy - h / 2)) * H
            ex += (max(0.0, (cx + w / 2) - 1.0) * W, max(0.0, (cy + h / 2) - 1.0) * H)
            if max(ex) > 1.0:
                problems.append((lbl.stem, f"box {i}: extends {max(ex):.0f} px outside the image"))
                flagged.add(lbl.stem)
            if cover > args.max_cover:
                problems.append((lbl.stem, f"box {i}: covers {cover:.0%} of frame -- split it"))
                flagged.add(lbl.stem)
            elif cover < args.min_cover:
                problems.append((lbl.stem, f"box {i}: only {px_w:.0f}x{px_h:.0f} px -- stray click?"))
                flagged.add(lbl.stem)
            if px_w > 0 and px_h > 0:
                aspect = max(px_w / px_h, px_h / px_w)
                if aspect > args.max_aspect:
                    problems.append((lbl.stem, f"box {i}: aspect {aspect:.1f}:1 -- mostly background, split it"))
                    flagged.add(lbl.stem)

    print(f"\n  {len(labels)} of {total_images} images labelled"
          f"   {n_boxes} boxes   {n_empty} deliberately empty")
    if covers:
        print(f"  coverage  median {statistics.median(covers):.1%}"
              f"   min {min(covers):.1%}   max {max(covers):.1%}"
              f"   (good boxes on this data land at 2-10%)")

    if unions:
        worst = sorted(unions, key=lambda u: -u[1])[:3]
        med_u = sorted(u[1] for u in unions)[len(unions) // 2]
        print(f"  union     median {med_u:.0%} of frame boxed"
              + "   worst: " + ", ".join(f"{n} {u:.0%}" for n, u, _ in worst))

    if strays:
        print(f"\n  ! {len(strays)} PascalVOC .xml file(s) -- the importer reads .txt only.")
        print("    Flip the format button to YOLO and redo these:")
        for s in strays:
            print(f"        {s.name}")

    if problems:
        print(f"\n  ! {len(problems)} thing(s) to look at, across {len(flagged)} image(s):\n")
        current = None
        for stem, msg in problems:
            if stem != current:
                print(f"    {stem}")
                current = stem
            print(f"        {msg}")
    else:
        print("\n  no problems found.")

    if args.render and flagged:
        from PIL import Image, ImageDraw
        for stem in sorted(flagged):
            img = find_image(images_dir, stem)
            if img is None:
                continue
            boxes, _ = parse(labels_dir / (stem + ".txt"))
            im = Image.open(img).convert("RGB")
            W, H = im.size
            s = max(1, 900 // max(W, 1))
            im = im.resize((W * s, H * s), Image.LANCZOS)
            d = ImageDraw.Draw(im)
            for i, (_c, cx, cy, w, h) in enumerate(boxes, 1):
                x1, y1 = (cx - w / 2) * W * s, (cy - h / 2) * H * s
                x2, y2 = (cx + w / 2) * W * s, (cy + h / 2) * H * s
                d.rectangle([x1, y1, x2, y2], outline=(255, 60, 60), width=3)
                d.text((x1 + 4, y1 + 2), f"{i} {w * h:.0%}", fill=(255, 255, 0))
            dest = base / f"review_{stem}.png"
            im.save(dest)
        print("" + chr(10) + "  wrote " + str(len(flagged)) + " overlay(s) to " + str(base / "review_<stem>.png"))

    return 1 if (problems or strays) else 0


if __name__ == "__main__":
    sys.exit(main())
