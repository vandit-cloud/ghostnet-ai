"""Convert labelme polygon JSON to YOLO segmentation labels.

    python ai/scripts/labelme_to_yoloseg.py --class ghost_net
    python ai/scripts/labelme_to_yoloseg.py --class ghost_net --dry-run

Reads  ai/data/annotate/<class>_seg/images/*.json   (labelme --autosave writes
       the JSON beside the image it belongs to)
Writes ai/data/annotate/<class>_seg/labels/*.txt

This is D2 in docs/EXPERIMENT_GV7_PLAN.md section 10.2: replacing axis-aligned
boxes with polygons for `ghost_net`, because a net is a long, thin, fragmented,
string-like object that a rectangle describes badly. GhostNetZero rejected
bounding boxes for exactly this reason and reported ~90% detection on 412 real
images -- see section 10.1.

YOLO segmentation label format, one object per line:

    <class_id> x1 y1 x2 y2 ... xn yn

with every coordinate normalised to 0..1 against the image it came from. Note
this is NOT the detection format: there is no width/height pair, and the point
count varies per object. Ultralytics infers the task from the label shape, so a
detection label in a -seg dataset trains silently and wrongly.

Why not the labelme2yolo package
--------------------------------
It renames files and invents its own train/val split. Both fight the pipeline
this repo already has, where `stage_annotations.py` owns the shape of a source
and `build_dataset.py` owns the split -- and where a filename is the only thing
tying a tile back to its origin frame. Forty lines here is cheaper than undoing
that.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
ANNOTATE = AI_ROOT / "data" / "annotate"


def convert_one(blob: dict, class_id: int, wanted: str) -> tuple[list[str], int]:
    """One labelme document -> YOLO-seg lines, plus a count of skipped shapes."""
    w, h = float(blob["imageWidth"]), float(blob["imageHeight"])
    lines: list[str] = []
    skipped = 0
    for shape in blob.get("shapes", []):
        if shape.get("label") != wanted:
            skipped += 1
            continue
        if shape.get("shape_type") != "polygon":
            # A rectangle here is almost certainly a slip of the hand back into
            # the old tool. Converting it would silently reintroduce exactly the
            # box annotation this track exists to replace, so refuse it loudly.
            raise ValueError(
                f"shape_type {shape.get('shape_type')!r} is not a polygon -- "
                f"draw with the polygon tool (Ctrl+N), not the rectangle tool"
            )
        pts = shape.get("points", [])
        if len(pts) < 3:
            raise ValueError(f"polygon has {len(pts)} points; at least 3 are needed")

        # Clamp rather than reject: labelme lets a vertex sit a pixel outside
        # the canvas, which is a drawing artifact and not a real error, but an
        # out-of-range coordinate makes ultralytics drop the whole label file.
        coords = []
        for x, y in pts:
            coords.append(f"{min(max(x / w, 0.0), 1.0):.6f}")
            coords.append(f"{min(max(y / h, 0.0), 1.0):.6f}")
        lines.append(f"{class_id} " + " ".join(coords))
    return lines, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="labelme polygons -> YOLO segmentation labels")
    ap.add_argument("--class", dest="cls", default="ghost_net")
    ap.add_argument("--class-id", type=int, default=0,
                    help="id WITHIN the staged source; build_dataset.py remaps to the "
                         "global taxonomy, so this is 0 for a single-class source")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = ANNOTATE / f"{args.cls}_seg"
    images = root / "images"
    labels = root / "labels"
    if not images.is_dir():
        print(f"no such directory: {images}")
        return 1

    jsons = sorted(images.glob("*.json"))
    all_images = [p for p in images.iterdir()
                  if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}]
    if not jsons:
        print(f"no labelme .json files in {images}")
        print(f"{len(all_images)} image(s) are staged and waiting to be annotated.")
        return 1

    if not args.dry_run:
        labels.mkdir(parents=True, exist_ok=True)

    written = polygons = skipped_total = 0
    empty: list[str] = []
    for jp in jsons:
        try:
            blob = json.loads(jp.read_text(encoding="utf-8"))
            lines, skipped = convert_one(blob, args.class_id, args.cls)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"  FAIL {jp.name}: {exc}")
            return 1
        skipped_total += skipped
        if not lines:
            # An image with no polygon is a legitimate negative, but for THIS
            # class it is far more likely to be one that was opened and not
            # finished. Name them rather than writing 73 silent empty files.
            empty.append(jp.stem)
            continue
        polygons += len(lines)
        if not args.dry_run:
            (labels / f"{jp.stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        written += 1

    print(f"\nsource   : {images}")
    print(f"output   : {labels if not args.dry_run else '(dry run)'}")
    print(f"annotated: {len(jsons)}/{len(all_images)} image(s) have a .json")
    print(f"written  : {written} label file(s), {polygons} polygon(s)")
    if skipped_total:
        print(f"skipped  : {skipped_total} shape(s) with a label other than {args.cls!r}")
    if empty:
        print(f"\nWARNING: {len(empty)} annotated image(s) carry no {args.cls} polygon:")
        for stem in empty[:10]:
            print(f"  {stem}")
        if len(empty) > 10:
            print(f"  ... and {len(empty) - 10} more")
        print("Each is either a genuine negative or an unfinished image. Check before importing.")
    remaining = len(all_images) - len(jsons)
    if remaining > 0:
        print(f"\n{remaining} image(s) still have no annotation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
