"""Stage the hand-drawn ghost_net boxes as an importable YOLO source.

    python ai/scripts/stage_ghost_net.py
    python ai/scripts/stage_ghost_net.py --dry-run

Reads  ai/data/annotate/ghost_net/{images,labels}   (what labelImg writes)
Writes ai/data/raw/research/GHOSTNET-HAND/{data.yaml,train/{images,labels}}

Then the normal road takes over:

    python ai/scripts/import_yolo.py --dataset GHOSTNET-HAND
    python ai/scripts/build_dataset.py

Why a staging step instead of importing the annotate folder directly
--------------------------------------------------------------------
Two reasons, both about not being clever.

import_yolo.py expects a source shaped like every other source: a data.yaml
naming the classes, and <split>/{images,labels} beneath it. The annotate folder
is shaped for labelImg instead -- flat, no data.yaml, no split. Copying 73 small
chips into that shape costs a few megabytes and lets the class remap, the
overlay screening and the import report all work unchanged. Teaching the
importer a second layout to save the copy would be the worse trade.

The second reason is that labelImg must keep pointing at a directory nothing
else writes to. Annotation is a long manual job; a script that reorganises the
folder underneath an open editor is a good way to lose an evening's work.

What is deliberately NOT staged
-------------------------------
A chip with an EMPTY label file. The source dataset states there is a net in
every one of these 73 chips. An empty label asserts the opposite, and that is
the single most damaging label this project could emit -- it teaches the
detector to ignore the object the whole system exists to find. If the
annotator could not see the net, the honest outcome is to leave the chip out
of training entirely, not to swear the frame is empty. Those chips stay
available as an image-level recall set, which needs no boxes.

The class id is remapped by NAME, not by number. labelImg writes id 0 because
ghost_net is the only entry in its classes.txt; the training id is 4. data.yaml
carries the name across, and ghostnet.taxonomy does the rest -- so this script
never hardcodes either number.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.taxonomy import TRAINING_CLASSES  # noqa: E402

SRC = AI_ROOT / "data" / "annotate" / "ghost_net"
DEST = AI_ROOT / "data" / "raw" / "research" / "GHOSTNET-HAND"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage hand-drawn ghost_net boxes for import.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-empty", action="store_true",
                    help="also stage chips whose label file is empty (see module docstring "
                         "-- this asserts the frame has no net, and the source says it does)")
    args = ap.parse_args()

    if "ghost_net" not in TRAINING_CLASSES:
        print("ghost_net is not in TRAINING_CLASSES -- add it to taxonomy.py first")
        return 1
    if not (SRC / "labels").is_dir():
        print(f"no labels at {SRC / 'labels'}")
        return 1

    staged, empty, unlabelled, bad = [], [], [], []
    images = sorted(p for p in (SRC / "images").iterdir() if p.suffix.lower() in IMAGE_EXTS)
    for img in images:
        lbl = SRC / "labels" / (img.stem + ".txt")
        if not lbl.exists():
            unlabelled.append(img.stem)
            continue
        lines = [ln for ln in lbl.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            (staged if args.keep_empty else empty).append((img, lbl, 0))
            continue
        if any(len(ln.split()) != 5 for ln in lines):
            bad.append(img.stem)
            continue
        staged.append((img, lbl, len(lines)))

    boxes = sum(n for _i, _l, n in staged)
    print(f"\n  source : {SRC}")
    print(f"  dest   : {DEST if not args.dry_run else '(dry run)'}\n")
    print(f"  {len(images):4d} chips present")
    print(f"  {len(staged):4d} staged        {boxes} boxes")
    if empty:
        print(f"  {len(empty):4d} SKIPPED -- label file is empty. The source says every one of")
        print("       these holds a net, so an empty label would teach the detector to")
        print("       miss it. They remain usable as an image-level recall set.")
        for i, (img, _l, _n) in enumerate(empty):
            if i < 8:
                print(f"           {img.stem}")
    if unlabelled:
        print(f"  {len(unlabelled):4d} not yet annotated")
    if bad:
        print(f"  ! {len(bad)} malformed label file(s): {', '.join(bad[:5])}")
        return 1
    if not staged:
        print("\n  nothing to stage.")
        return 1

    if args.dry_run:
        return 0

    for sub in ("images", "labels"):
        d = DEST / "train" / sub
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    for img, lbl, _n in staged:
        shutil.copy2(img, DEST / "train" / "images" / img.name)
        shutil.copy2(lbl, DEST / "train" / "labels" / lbl.name)

    # Names in id order, exactly as labelImg numbered them. Only ghost_net is
    # used; the name is what import_yolo maps through the taxonomy.
    (DEST / "data.yaml").write_text(
        "# Generated by ai/scripts/stage_ghost_net.py -- do not edit by hand.\n"
        "# Hand-drawn boxes on the 73 fishing-net chips of China-Offshore-SSS-AI,\n"
        "# which ships them as classification only (its class name: hard_negative).\n"
        "# Convention and worked examples: ai/data/annotate/ghost_net/_guide/\n"
        "path: .\ntrain: train/images\n\nnc: 1\nnames:\n  0: ghost_net\n",
        encoding="utf-8")

    print(f"\n  wrote {DEST}")
    print("  next:  python ai/scripts/import_yolo.py --dataset GHOSTNET-HAND")
    print("         python ai/scripts/build_dataset.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
