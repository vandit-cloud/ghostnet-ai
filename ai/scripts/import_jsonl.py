"""Import a HuggingFace-style dataset: one metadata.jsonl per split.

    python ai/scripts/import_jsonl.py --dataset GhostVision_DatasetAndModels --out ai/data/interim/GHOSTVISION
    python ai/scripts/import_jsonl.py --dataset ... --dry-run

Reads  <dataset>/**/<split>/metadata.jsonl  alongside the images
Writes ai/data/interim/<NAME>/<split>/{images,labels} + an import report

Record shape, as GhostVision ships it:

    {"file_name": "...jpg",
     "objects": {"bbox": [[x, y, w, h], ...],
                 "category": ["Crab-Pot", ...],
                 "area": [...]}}

The bbox convention is the trap
-------------------------------
These are COCO-style [x, y, width, height] in PIXELS from the top-left corner.
YOLO wants [centre_x, centre_y, width, height] NORMALISED to 0..1. Confusing
the two produces boxes that are plausibly placed and systematically wrong --
offset by half their own size, and never caught by a training log. The
conversion is asserted against the record's own `area` field where present.

Empty records are kept
----------------------
A record with no objects is a frame the annotators examined and found nothing
in. That is a verified-empty negative, and it is worth more than a mined one
because a human confirmed it. GhostVision ships 1,547 of them.
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
from ghostnet.taxonomy import KEEP_AS_BACKGROUND, TRAINING_CLASSES, source_to_training  # noqa: E402

RAW_ROOT = AI_ROOT / "data" / "raw"
INTERIM_ROOT = AI_ROOT / "data" / "interim"


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


def to_yolo(box, width: int, height: int) -> tuple[float, float, float, float] | None:
    """COCO [x, y, w, h] pixels -> YOLO [cx, cy, w, h] normalised, clipped."""
    x, y, w, h = (float(v) for v in box)
    x1, y1 = max(0.0, x), max(0.0, y)
    x2, y2 = min(float(width), x + w), min(float(height), y + h)
    if x2 - x1 <= 1.0 or y2 - y1 <= 1.0:
        return None
    return ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height,
            (x2 - x1) / width, (y2 - y1) / height)


def main() -> int:
    ap = argparse.ArgumentParser(description="Import a metadata.jsonl dataset.")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-box-side", type=int, default=8,
                    help="drop boxes whose short side is below this many pixels")
    ap.add_argument("--no-screen", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = find_dataset(args.dataset)
    if src is None:
        print(f"dataset '{args.dataset}' not found under ai/data/raw/")
        return 1

    manifests = sorted(src.rglob("metadata.jsonl"))
    if not manifests:
        print(f"no metadata.jsonl found under {src}")
        return 1

    out_root = Path(args.out) if args.out else INTERIM_ROOT / args.dataset.upper()
    report = Counter()
    per_class = Counter()
    per_split: dict[str, dict] = {}
    rejected: list[dict] = []
    unmapped = Counter()

    print(f"\nsource : {src}")
    print(f"output : {out_root if not args.dry_run else '(dry run)'}\n")

    for manifest in manifests:
        split = manifest.parent.name
        kept = background = 0
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            report["records"] += 1
            img_path = manifest.parent / record["file_name"]
            if not img_path.exists():
                report["missing_images"] += 1
                continue

            image = cv2.imread(str(img_path))
            if image is None:
                report["unreadable"] += 1
                continue
            h, w = image.shape[:2]

            if not args.no_screen:
                why = screen(overlay_signals(image), DEFAULT_LIMITS)
                if why:
                    rejected.append({"file": img_path.name, "split": split, "reason": why})
                    report["rejected_contaminated"] += 1
                    continue

            objects = record.get("objects") or {}
            boxes = objects.get("bbox") or []
            names = objects.get("category") or []
            lines, saw_unmapped, tiny_dropped = [], False, False

            for i, box in enumerate(boxes):
                raw_name = names[i] if i < len(names) else ""
                training, reason = source_to_training(raw_name)
                if training is None:
                    if reason.startswith(KEEP_AS_BACKGROUND):
                        report["boxes_dropped_by_policy"] += 1
                    else:
                        unmapped[raw_name or "(blank)"] += 1
                        saw_unmapped = True
                    continue
                if min(float(box[2]), float(box[3])) < args.min_box_side:
                    report["boxes_too_small"] += 1
                    tiny_dropped = True
                    continue
                yolo = to_yolo(box, w, h)
                if yolo is None:
                    report["boxes_degenerate"] += 1
                    continue
                cls_id = TRAINING_CLASSES.index(training)
                lines.append(f"{cls_id} " + " ".join(f"{v:.6f}" for v in yolo))
                per_class[training] += 1

            if not lines and (saw_unmapped or tiny_dropped):
                # Every box on this frame was dropped -- unrecognised class,
                # or too small to learn. Writing an empty label would assert
                # the frame is empty over a real annotated object, which is
                # a false lesson. Same quarantine rule as the other
                # converters. A record that genuinely HAS no objects still
                # becomes a negative, which is the point of keeping them.
                report["frames_quarantined"] += 1
                continue
            if not lines:
                background += 1
            kept += 1
            report["frames_imported"] += 1

            if not args.dry_run:
                oi, ol = out_root / split / "images", out_root / split / "labels"
                oi.mkdir(parents=True, exist_ok=True)
                ol.mkdir(parents=True, exist_ok=True)
                shutil.copy2(img_path, oi / img_path.name)
                (ol / (img_path.stem + ".txt")).write_text(
                    "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        per_split[split] = {"imported": kept, "background": background}
        print(f"  {split:8s} imported={kept:5d}  of which background={background:5d}")

    print(f"\n  {report['records']:6d} records read")
    print(f"  {report['frames_imported']:6d} frames imported")
    for name, n in per_class.most_common():
        print(f"           {name:<12s} {n} boxes")
    if report["boxes_too_small"]:
        print(f"  {report['boxes_too_small']:6d} boxes below --min-box-side {args.min_box_side}px")
    if report["boxes_degenerate"]:
        print(f"  {report['boxes_degenerate']:6d} degenerate boxes dropped")
    if report["rejected_contaminated"]:
        print(f"  {report['rejected_contaminated']:6d} frames rejected as contaminated")
    if report["frames_quarantined"]:
        print(f"  {report['frames_quarantined']:6d} frames quarantined (unmapped class present)")
    if unmapped:
        print("  ! UNMAPPED categories -- add them to taxonomy.py:")
        for k, v in unmapped.most_common():
            print(f"           {k:<14s} {v}")
    if report["missing_images"]:
        print(f"  ! {report['missing_images']} records reference a missing image")

    if not report["frames_imported"]:
        print("\nnothing imported.")
        return 1

    if not args.dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "import_report.json").write_text(json.dumps({
            "source": str(src),
            "counts": dict(report),
            "boxes_per_class": dict(per_class),
            "per_split": per_split,
            "unmapped": dict(unmapped),
            "rejected": rejected[:100],
            "screening": {"enabled": not args.no_screen, "limits": DEFAULT_LIMITS},
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {show(out_root / 'import_report.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
