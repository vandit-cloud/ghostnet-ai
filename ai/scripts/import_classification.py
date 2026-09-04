"""Import a folder-per-class dataset -- for its BACKGROUND images only.

    python ai/scripts/import_classification.py --dataset MARINE-PULSE
    python ai/scripts/import_classification.py --dataset MARINE-PULSE --dry-run

Reads  ai/data/raw/**/<DATASET>/[<split>/]<class name>/*.jpg
Writes ai/data/interim/<DATASET>/<split>/{images,labels} + an import report

Why this only takes negatives
-----------------------------
A classification dataset says "there is a pipeline somewhere in this image".
It does not say WHERE, and a detector needs a box. There are only three things
one could do with such a positive, and two of them are wrong:

  * invent a box, usually the whole frame -- fabricating ground truth, and it
    teaches the detector that an object fills the image;
  * import it with an empty label -- asserting the frame is empty when it
    demonstrably is not, which actively teaches the model to miss that object;
  * skip it. This script skips it, and says how many it skipped.

The BACKGROUND classes are different. "Plain seabed" carries all the
information a detector needs from it: there is nothing here. That is exactly an
empty label file, and those frames are the hard negatives the
artificial-vs-natural metric depends on.

What Marine-PULSE actually buys
-------------------------------
88 seabed-surface frames, against the 3,286 negative tiles already mined from
AI4Shipwrecks. The volume is irrelevant; the INSTRUMENT DIVERSITY is the point.
Marine-PULSE was recorded on EdgeTech 4200FS, Benthos SIS-1624, EdgeTech
4200MP, Klein 2000 and Klein 3000, where every existing negative comes from one
survey system. A model whose idea of "normal seabed" comes from a single sonar
is brittle in a way no amount of same-instrument data reveals.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _screening import DEFAULT_LIMITS, overlay_signals, screen  # noqa: E402
from ghostnet.taxonomy import source_to_training  # noqa: E402

RAW_ROOT = AI_ROOT / "data" / "raw"
INTERIM_ROOT = AI_ROOT / "data" / "interim"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
KNOWN_SPLITS = {"train", "val", "valid", "test"}


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def find_dataset(name: str) -> Path | None:
    if not RAW_ROOT.exists():
        return None
    for bucket in RAW_ROOT.iterdir():
        if bucket.is_dir():
            for child in bucket.iterdir():
                if child.is_dir() and child.name.lower() == name.lower():
                    return child
    return None


def class_folders(root: Path) -> list[tuple[str, str, Path]]:
    """(split, class_name, folder) for every leaf folder holding images.

    Handles both layouts seen in the wild: <class>/ at the top, and
    <split>/<class>/ where the dataset ships its own split.
    """
    found = []
    for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
        if not any(f.suffix.lower() in IMAGE_EXTS for f in folder.iterdir() if f.is_file()):
            continue
        rel = folder.relative_to(root)
        if len(rel.parts) >= 2 and rel.parts[0].lower() in KNOWN_SPLITS:
            found.append((rel.parts[0].lower(), rel.parts[-1], folder))
        else:
            found.append(("train", rel.parts[-1], folder))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="Import background images from a folder-per-class dataset.")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-screen", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = find_dataset(args.dataset)
    if src is None:
        print(f"dataset '{args.dataset}' not found under ai/data/raw/")
        return 1

    folders = class_folders(src)
    if not folders:
        print(f"no class folders with images under {src}")
        return 1

    out_root = Path(args.out) if args.out else INTERIM_ROOT / args.dataset.upper()
    report = Counter()
    per_class: dict[str, dict] = {}
    rejected: list[dict] = []

    print(f"\nsource : {src}")
    print(f"output : {out_root if not args.dry_run else '(dry run)'}\n")
    print("  class folders")

    for split, class_name, folder in folders:
        files = sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS)
        training, reason = source_to_training(class_name)
        key = f"{split}/{class_name}"

        if reason.startswith("background"):
            verdict, kept = "BACKGROUND -> empty labels", 0
            for img in files:
                if not args.no_screen:
                    image = cv2.imread(str(img))
                    if image is None:
                        report["unreadable"] += 1
                        continue
                    why = screen(overlay_signals(image), DEFAULT_LIMITS)
                    if why:
                        rejected.append({"file": img.name, "class": class_name, "reason": why})
                        report["rejected_contaminated"] += 1
                        continue
                kept += 1
                if not args.dry_run:
                    oi, ol = out_root / split / "images", out_root / split / "labels"
                    oi.mkdir(parents=True, exist_ok=True)
                    ol.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(img, oi / img.name)
                    (ol / (img.stem + ".txt")).write_text("", encoding="utf-8")
            report["background_imported"] += kept
            per_class[key] = {"verdict": "background", "found": len(files), "imported": kept}

        elif training is not None:
            # A real object class, but no box tells us where it is. Skipping is
            # the only honest option -- see the module docstring.
            verdict = f"positive ({training}) -- SKIPPED, no boxes in a classification set"
            report["positives_skipped"] += len(files)
            per_class[key] = {"verdict": "positive_no_boxes", "found": len(files), "imported": 0}

        elif reason.startswith("excluded"):
            verdict = "excluded by policy -- skipped"
            report["excluded_skipped"] += len(files)
            per_class[key] = {"verdict": "excluded", "found": len(files), "imported": 0}

        else:
            verdict = "UNMAPPED -- add it to taxonomy.py or it is silently lost"
            report["unmapped_skipped"] += len(files)
            per_class[key] = {"verdict": "unmapped", "found": len(files), "imported": 0}

        print(f"    {split:6s} {class_name:28s} {len(files):4d}  {verdict}")

    print(f"\n  {report['background_imported']:5d} background images imported (empty labels)")
    if report["positives_skipped"]:
        print(f"  {report['positives_skipped']:5d} positives skipped: classification labels give no box,")
        print("        and inventing one, or calling the frame empty, would both be wrong")
    if report["excluded_skipped"]:
        print(f"  {report['excluded_skipped']:5d} skipped by exclusion policy")
    if report["rejected_contaminated"]:
        print(f"  {report['rejected_contaminated']:5d} rejected as contaminated")
    if report["unmapped_skipped"]:
        print(f"  ! {report['unmapped_skipped']} images in UNMAPPED classes -- add them to taxonomy.py:")
        for k, v in per_class.items():
            if v["verdict"] == "unmapped":
                print(f"        {k}  ({v['found']} images)")

    if not report["background_imported"]:
        print("\nnothing imported: this dataset has no class that maps to background.")
        return 1

    if not args.dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "import_report.json").write_text(json.dumps({
            "source": str(src),
            "mode": "classification -> background only",
            "per_class": per_class,
            "counts": dict(report),
            "rejected": rejected,
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {show(out_root / 'import_report.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
