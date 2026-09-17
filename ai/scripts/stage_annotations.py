"""Stage a hand-drawn class as an importable YOLO source.

    python ai/scripts/stage_annotations.py --class ghost_net
    python ai/scripts/stage_annotations.py --class plane --dry-run
    python ai/scripts/stage_annotations.py --list

Reads  ai/data/annotate/<class>/{images,labels}   (what labelImg writes)
Writes ai/data/raw/research/<CLASS>-HAND/{data.yaml,train/{images,labels}}

Then the normal road takes over:

    python ai/scripts/import_yolo.py --dataset <CLASS>-HAND
    python ai/scripts/build_dataset.py

Two classes come through here so far and they are not alike. `ghost_net` is
ground truth that did not previously exist in any form. `plane` is EXTRA boxes
for a class SCTD already supplies 39 of -- which means its convention is not a
free choice: SCTD boxes the aircraft's acoustic return and leaves the cast
shadow outside, so these must too, or the class gets two contradictory
definitions and learns neither. Worked examples are in each class's _guide/.

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

ANNOTATE = AI_ROOT / "data" / "annotate"
RESEARCH = AI_ROOT / "data" / "raw" / "research"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage a hand-drawn class for import.")
    ap.add_argument("--class", dest="cls", default=None,
                    help="a directory name under ai/data/annotate/, e.g. ghost_net")
    ap.add_argument("--list", action="store_true", help="show what is staged and how far along it is")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-empty", action="store_true",
                    help="also stage chips whose label file is empty (see module docstring "
                         "-- this asserts the frame has no net, and the source says it does)")
    args = ap.parse_args()

    if args.list or not args.cls:
        if not ANNOTATE.is_dir():
            print(f"no {ANNOTATE}")
            return 1
        print()
        print(f"  classes under {ANNOTATE}:")
        print()
        for d in sorted(p for p in ANNOTATE.iterdir() if p.is_dir()):
            imgs = len([p for p in (d / "images").iterdir()
                        if p.suffix.lower() in IMAGE_EXTS]) if (d / "images").is_dir() else 0
            lbls = len(list((d / "labels").glob("*.txt"))) - 1 if (d / "labels").is_dir() else 0
            known = "" if d.name in TRAINING_CLASSES else "   (NOT in TRAINING_CLASSES)"
            print(f"    {d.name:12s} {lbls:4d} of {imgs:4d} labelled{known}")
        print()
        return 0 if args.list else 1

    SRC = ANNOTATE / args.cls
    DEST = RESEARCH / (args.cls.upper().replace("_", "") + "-HAND")

    if args.cls not in TRAINING_CLASSES:
        print(f"'{args.cls}' is not in TRAINING_CLASSES -- add it to taxonomy.py first")
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

    # One class, numbered 0, exactly as labelImg wrote it. The training id is
    # whatever taxonomy.py says -- import_yolo maps by NAME, so neither number
    # is hardcoded anywhere on this path.
    (DEST / "data.yaml").write_text(
        "# Generated by ai/scripts/stage_annotations.py -- do not edit by hand.\n"
        f"# Hand-drawn boxes staged from ai/data/annotate/{args.cls}/.\n"
        f"# Convention and worked examples: ai/data/annotate/{args.cls}/_guide/\n"
        f"path: .\ntrain: train/images\n\nnc: 1\nnames:\n  0: {args.cls}\n",
        encoding="utf-8")

    print(f"\n  wrote {DEST}")
    print(f"  next:  python ai/scripts/import_yolo.py --dataset {DEST.name}")
    print("         python ai/scripts/build_dataset.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
