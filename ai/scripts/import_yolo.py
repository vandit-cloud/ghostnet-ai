"""Import an already-YOLO dataset: remap its classes, screen contaminated frames.

    python ai/scripts/import_yolo.py --dataset SONARDETECT --only-classes other
    python ai/scripts/import_yolo.py --dataset SONARDETECT --dry-run
    python ai/scripts/import_yolo.py --dataset SONARDETECT --no-screen

Reads  ai/data/raw/**/<DATASET>/  (data.yaml + <split>/{images,labels})
Writes ai/data/interim/<DATASET>/<split>/{images,labels} + an import report

Two jobs, both necessary
------------------------
1. CLASS REMAPPING. The source numbers its own classes; we number ours. Its
   data.yaml gives the names, which go through ghostnet.taxonomy exactly like
   any other source, so 'shipwreck' -> wreck and 'other' -> debris without a
   second alias table to keep in sync.

2. OVERLAY SCREENING. sonar_detect is scraped from the web, and a good fraction
   of its frames are not raw sonar: screenshots of acquisition software with
   toolbars, annotated figures with leader lines and labels, measurement scale
   bars, copyright banners, and the annotator's own circles burned into the
   pixels. A detector trained on those learns the overlay, not the object --
   a shortcut that validates beautifully and fails on real sonar.

Why the screening is deliberately imperfect
-------------------------------------------
Perfectly separating scraped web imagery is its own research problem. Thin
toolbars and small text captions are too few pixels to trip any threshold that
does not also reject good data. So the strategy is to reduce exposure rather
than to chase perfect recall:

  * Import ONLY the classes this dataset uniquely provides. Wrecks and aircraft
    already come from SCTD and AI4Shipwrecks, which are clean; sonar_detect's
    unique contribution is `other` -> debris, the class nearest the problem
    statement. That cuts the frames at risk from 561 to 74.
  * Screen those, and report exactly what was rejected and why, so the residual
    noise is a documented number rather than an unpleasant surprise.

A limitation to know about
---------------------------
RED annotation on an AMBER sonar palette is not reliably detected, and no
threshold here will fix it. Red sits at hue 0 and the copper ramp sits near
hue 17, so a red ring is not 'off hue'; and a saturated amber return reaches
the same saturation as paint. The two genuinely overlap in colour space.
Far-hue paint -- cyan, green, white, blue -- IS caught, as are toolbars,
caption bars and large painted areas.

This is why exposure reduction matters more than the filter: 71 frames of
one class, all of which have been looked at, beats a clever screener over
561 frames nobody inspected. Residual contamination is a documented number,
not a claim of cleanliness.

The one signal that is NOT used
-------------------------------
"Large flat dark region" looks like an obvious screenshot cue and is the worst
possible one here: acoustic shadow is flat and near-black, and it is the single
most informative feature in a side-scan image. Screening on it throws away the
best data. Only flat MID-TONE regions count, which is UI chrome, not shadow.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.taxonomy import (  # noqa: E402
    KEEP_AS_BACKGROUND,
    TRAINING_CLASSES,
    source_to_training,
)

RAW_ROOT = AI_ROOT / "data" / "raw"
INTERIM_ROOT = AI_ROOT / "data" / "interim"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")


def show(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


def overlay_signals(image: np.ndarray) -> dict[str, float]:
    """Three measurements that separate raw sonar from a screenshot.

    off_hue      Sonar palettes are one hue -- greyscale, or a single amber or
                 copper ramp. A saturated colour far from the frame's dominant
                 hue is paint: an annotator's red circle, a cyan box, a leader
                 line. Almost never present in genuine imagery.
    flat_midtone Blocks with no texture at all, at mid brightness. Sonar always
                 carries speckle; a smooth grey panel is a toolbar. Explicitly
                 mid-tone, because flat DARK is acoustic shadow and precious.
    ui_rows      Image rows that are near-constant across the full width and
                 not dark. Window borders and toolbars span the frame; seabed
                 does not.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, sat, val = (hsv[..., i].astype(np.int16) for i in range(3))

    saturated = sat > 60
    dominant = int(np.bincount(hue[saturated], minlength=180).argmax()) if saturated.any() else 0
    delta = np.minimum(np.abs(hue - dominant), 180 - np.abs(hue - dominant))
    off_hue = float(((sat > 120) & (val > 80) & (delta > 25)).mean())

    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    k = 16
    h, w = grey.shape[0] // k * k, grey.shape[1] // k * k
    if h and w:
        blocks = grey[:h, :w].reshape(h // k, k, w // k, k).swapaxes(1, 2).reshape(-1, k, k)
        sd, mu = blocks.std(axis=(1, 2)), blocks.mean(axis=(1, 2))
        flat_midtone = float(((sd < 3.0) & (mu > 55) & (mu < 225)).mean())
    else:
        flat_midtone = 0.0

    ui_rows = float(((grey.std(axis=1) < 4.0) & (grey.mean(axis=1) > 40)).mean())

    # Fully-saturated maximum-value pixels. Annotation paint is exactly
    # S=255; a sonar ramp compressed to JPEG rarely is, over any area.
    pure_paint = float(((sat >= 250) & (val >= 200)).mean())

    return {"off_hue": off_hue, "flat_midtone": flat_midtone,
            "ui_rows": ui_rows, "pure_paint": pure_paint}


def screen(signals: dict[str, float], limits: dict[str, float]) -> str | None:
    """Return the reason this frame is contaminated, or None to keep it."""
    if signals["off_hue"] > limits["off_hue"]:
        return f"burned-in coloured graphics (off_hue {signals['off_hue']:.3f})"
    if signals["flat_midtone"] > limits["flat_midtone"]:
        return f"UI panel or caption bar (flat_midtone {signals['flat_midtone']:.3f})"
    if signals["ui_rows"] > limits["ui_rows"]:
        return f"toolbar or window border (ui_rows {signals['ui_rows']:.3f})"
    if signals["pure_paint"] > limits["pure_paint"]:
        return f"large area of pure paint (pure_paint {signals['pure_paint']:.3f})"
    return None


def find_dataset(name: str) -> Path | None:
    if not RAW_ROOT.exists():
        return None
    for bucket in RAW_ROOT.iterdir():
        if bucket.is_dir():
            for child in bucket.iterdir():
                if child.is_dir() and child.name.lower() == name.lower():
                    return child
    return None


def source_names(root: Path) -> list[str] | None:
    """Class names, in id order, from the dataset's own data.yaml."""
    for cfg in list(root.rglob("data.yaml")) + list(root.rglob("*.yaml")):
        try:
            import yaml

            blob = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        names = blob.get("names") if isinstance(blob, dict) else None
        if isinstance(names, dict):
            return [names[i] for i in sorted(names)]
        if isinstance(names, list):
            return names
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Import a YOLO-format dataset with class remapping and screening.")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only-classes", nargs="*", default=None,
                    help="import only these SOURCE class names. Use it to take just what a dataset "
                         "uniquely provides and leave its riskier classes behind.")
    ap.add_argument("--no-screen", action="store_true", help="import every frame, contaminated or not")
    # Tuned against the actual distribution, not guessed. At 0.010 this
    # rejected 9 of 74 debris frames and only 2 were genuinely contaminated:
    # bright amber returns shift hue enough to look like paint against a
    # darker copper background. 0.040 keeps both true positives and returns
    # six real frames to a class we are already short of.
    ap.add_argument("--max-off-hue", type=float, default=0.040)
    ap.add_argument("--max-flat-midtone", type=float, default=0.120)
    ap.add_argument("--max-ui-rows", type=float, default=0.060)
    # Conservative on purpose. Real frames reach ~5% pure-saturated pixels
    # from bright amber returns, so anything tighter costs real data.
    ap.add_argument("--max-pure-paint", type=float, default=0.150)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = find_dataset(args.dataset)
    if src is None:
        print(f"dataset '{args.dataset}' not found under ai/data/raw/")
        return 1
    names = source_names(src)
    if not names:
        print(f"no data.yaml with class names under {src}; cannot remap ids safely")
        return 1

    limits = {"off_hue": args.max_off_hue,
              "flat_midtone": args.max_flat_midtone,
              "ui_rows": args.max_ui_rows,
              "pure_paint": args.max_pure_paint}
    wanted = {n.strip().lower() for n in args.only_classes} if args.only_classes else None
    out_root = Path(args.out) if args.out else INTERIM_ROOT / args.dataset.upper()

    # Resolve the source id -> training id map once, and report it.
    mapping: dict[int, int] = {}
    print(f"\nsource : {src}")
    print(f"output : {out_root if not args.dry_run else '(dry run)'}\n")
    print("  class mapping")
    for i, name in enumerate(names):
        if wanted is not None and name.strip().lower() not in wanted:
            print(f"    {i} {name:12s} -> skipped (not in --only-classes)")
            continue
        training, reason = source_to_training(name)
        if training is None:
            print(f"    {i} {name:12s} -> dropped ({reason.split(':')[0]})")
            continue
        mapping[i] = TRAINING_CLASSES.index(training)
        print(f"    {i} {name:12s} -> {mapping[i]} {training}")
    if not mapping:
        print("\nnothing to import: no source class maps to a training class.")
        return 1

    report = Counter()
    rejected: list[dict] = []
    per_class = Counter()

    for images_dir in sorted(src.rglob("images")):
        labels_dir = images_dir.parent / "labels"
        if not labels_dir.is_dir():
            continue
        split = images_dir.parent.name
        for img in sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS):
            lbl = labels_dir / (img.stem + ".txt")
            if not lbl.exists():
                continue
            report["frames_seen"] += 1

            kept_lines, saw_unmapped = [], False
            for line in lbl.read_text(encoding="utf-8").split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                sid = int(parts[0])
                if sid in mapping:
                    kept_lines.append(" ".join([str(mapping[sid])] + parts[1:]))
                elif wanted is not None and names[sid].strip().lower() not in wanted:
                    report["boxes_other_class"] += 1
                else:
                    _t, reason = source_to_training(names[sid]) if sid < len(names) else (None, "unmapped")
                    if reason.startswith(KEEP_AS_BACKGROUND):
                        report["boxes_dropped_by_policy"] += 1
                    else:
                        report["boxes_unmapped"] += 1
                        saw_unmapped = True

            if not kept_lines:
                # Nothing we want on this frame. Importing it as background
                # would be reasonable in isolation, but this dataset supplies
                # no verified-empty frames -- its "background" is just objects
                # of classes we skipped. Asserting emptiness over them is the
                # same false lesson the other converters quarantine for.
                report["frames_no_wanted_class"] += 1
                continue
            if saw_unmapped:
                report["frames_quarantined_unmapped"] += 1
                continue

            image = cv2.imread(str(img))
            if image is None:
                report["frames_unreadable"] += 1
                continue
            if not args.no_screen:
                signals = overlay_signals(image)
                reason = screen(signals, limits)
                if reason:
                    report["frames_rejected_contaminated"] += 1
                    rejected.append({"file": img.name, "split": split, "reason": reason, **signals})
                    continue

            # Counted only now: a frame rejected by screening contributes no
            # boxes, and reporting them would overstate what was imported.
            for line in kept_lines:
                per_class[TRAINING_CLASSES[int(line.split()[0])]] += 1
            report["frames_imported"] += 1
            if not args.dry_run:
                oi, ol = out_root / split / "images", out_root / split / "labels"
                oi.mkdir(parents=True, exist_ok=True)
                ol.mkdir(parents=True, exist_ok=True)
                shutil.copy2(img, oi / img.name)
                (ol / (img.stem + ".txt")).write_text("\n".join(kept_lines) + "\n", encoding="utf-8")

    print(f"\n  {report['frames_seen']:5d} frames seen")
    print(f"  {report['frames_imported']:5d} imported")
    for name, n in per_class.most_common():
        print(f"           {name:<10s} {n} boxes")
    if report["frames_no_wanted_class"]:
        print(f"  {report['frames_no_wanted_class']:5d} skipped: none of the wanted classes present")
    if report["frames_rejected_contaminated"]:
        print(f"  {report['frames_rejected_contaminated']:5d} REJECTED as contaminated:")
        for r in Counter(x["reason"].split(" (")[0] for x in rejected).most_common():
            print(f"           {r[1]:3d}  {r[0]}")
    if report["frames_quarantined_unmapped"]:
        print(f"  {report['frames_quarantined_unmapped']:5d} quarantined: unmapped class on the frame")
    if report["boxes_unmapped"]:
        print(f"  ! {report['boxes_unmapped']} boxes with an unmapped class -- add them to SOURCE_ALIASES")

    if not args.dry_run and report["frames_imported"]:
        (out_root / "import_report.json").write_text(json.dumps({
            "source": str(src),
            "source_names": names,
            "id_map": {str(k): v for k, v in mapping.items()},
            "only_classes": args.only_classes,
            "screening": {"enabled": not args.no_screen, "limits": limits},
            "counts": dict(report),
            "boxes_per_class": dict(per_class),
            "rejected": rejected,
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {show(out_root / 'import_report.json')}")

    if not report["frames_imported"]:
        print("\nnothing imported.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
