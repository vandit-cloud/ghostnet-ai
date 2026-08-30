"""Convert Pascal VOC XML annotations to YOLO format.

    python ai/scripts/voc_to_yolo.py --dataset SCTD
    python ai/scripts/voc_to_yolo.py --dataset SCTD --dry-run       # report only
    python ai/scripts/voc_to_yolo.py --dataset SCTD --collapse artificial

Reads  ai/data/raw/**/<DATASET>/
Writes ai/data/interim/<DATASET>/{images,labels}/ plus a conversion report.

Splitting is NOT done here. This produces one flat converted set; the
leakage-safe train/val/test split (plan section 12) is a separate step working
on ai/data/processed/, because a split must be decided on survey or site
boundaries, which is a judgement the converter has no way to make.

What this guards against
------------------------
Format conversion looks trivial and is where silent, unrecoverable label
corruption happens. Specifically:

  * The <size> element in VOC XML is frequently WRONG -- copied from a template,
    or left over after images were resized. YOLO coordinates are normalised by
    image size, so a wrong size silently scales every box on that image. The
    converter reads the real dimensions from the image itself and reports any
    disagreement rather than trusting the XML.
  * Boxes that fall outside the image, have zero area, or arrive with xmax and
    xmin swapped. All three appear in real annotation sets.
  * Images with no annotation. These are not failures -- an empty label file is
    how YOLO expresses "background", which is exactly what the hard-negative
    strategy needs. Skipping them would throw away the negatives.

Every drop is counted and reported. Nothing is discarded silently.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.taxonomy import (  # noqa: E402
    COLLAPSE_MAPS,
    TRAINING_CLASSES,
    source_to_training,
)

RAW_ROOT = AI_ROOT / "data" / "raw"
INTERIM_ROOT = AI_ROOT / "data" / "interim"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def show(path: Path) -> str:
    """Repo-relative when possible, absolute otherwise.

    --out may legitimately point outside the repo (a scratch disk, a bigger
    drive). Assuming otherwise crashed the run at the very last step, after
    all the conversion work was already done.
    """
    try:
        return str(path.relative_to(AI_ROOT.parent))
    except ValueError:
        return str(path)


@dataclass
class Report:
    """Everything the operator needs to trust, or distrust, the conversion."""

    xml_files: int = 0
    images_written: int = 0
    labels_written: int = 0
    boxes_kept: int = 0
    empty_labels: int = 0                      # background images: wanted, not failures
    per_class: Counter = field(default_factory=Counter)
    dropped_excluded: Counter = field(default_factory=Counter)
    dropped_unmapped: Counter = field(default_factory=Counter)
    dropped_difficult: int = 0
    dropped_degenerate: int = 0
    clamped: int = 0
    size_mismatches: list[str] = field(default_factory=list)
    missing_images: list[str] = field(default_factory=list)
    unparseable: list[str] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "xml_files": self.xml_files,
            "images_written": self.images_written,
            "labels_written": self.labels_written,
            "boxes_kept": self.boxes_kept,
            "empty_labels_background_images": self.empty_labels,
            "per_class": dict(self.per_class),
            "dropped_excluded": dict(self.dropped_excluded),
            "dropped_unmapped": dict(self.dropped_unmapped),
            "dropped_difficult": self.dropped_difficult,
            "dropped_degenerate_boxes": self.dropped_degenerate,
            "clamped_boxes": self.clamped,
            "size_mismatches": self.size_mismatches[:50],
            "missing_images": self.missing_images[:50],
            "unparseable_xml": self.unparseable[:50],
            "quarantined_unmapped_only": self.quarantined[:50],
        }


def find_dataset(name: str) -> Path | None:
    for bucket in RAW_ROOT.iterdir() if RAW_ROOT.exists() else []:
        if not bucket.is_dir():
            continue
        candidate = bucket / name
        if candidate.is_dir():
            return candidate
        for child in bucket.iterdir():
            if child.is_dir() and child.name.lower() == name.lower():
                return child
    return None


def index_images(root: Path) -> dict[str, Path]:
    """Map filename stem -> image path.

    An index rather than a per-XML search: VOC layouts vary wildly, and the XML
    is not always beside its image.
    """
    index: dict[str, Path] = {}
    for p in root.rglob("*"):
        if p.suffix.lower() in IMAGE_EXTS:
            index.setdefault(p.stem, p)
    return index


def real_image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return None


def convert_box(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    width: int,
    height: int,
    report: Report,
) -> tuple[float, float, float, float] | None:
    """VOC corner pixels -> YOLO normalised centre/size. None if unusable.

    Note the width convention: `xmax - xmin`, not `xmax - xmin + 1`. Original
    Pascal VOC coordinates are 1-based and inclusive, which argues for the +1,
    but virtually every modern dataset distributed "in VOC format" -- SCTD
    included -- exports 0-based exclusive corners from a labelling tool. On a
    640-pixel-wide image the difference is 0.16% of a box edge; picking the
    wrong convention for the actual data is a far larger error than either.
    """
    if xmax < xmin:
        xmin, xmax = xmax, xmin
    if ymax < ymin:
        ymin, ymax = ymax, ymin

    cxmin, cymin = max(0.0, xmin), max(0.0, ymin)
    cxmax, cymax = min(float(width), xmax), min(float(height), ymax)
    if (cxmin, cymin, cxmax, cymax) != (xmin, ymin, xmax, ymax):
        report.clamped += 1

    bw, bh = cxmax - cxmin, cymax - cymin
    if bw <= 1.0 or bh <= 1.0:      # a box under two pixels is noise, not an object
        report.dropped_degenerate += 1
        return None

    cx = (cxmin + cxmax) / 2.0 / width
    cy = (cymin + cymax) / 2.0 / height
    nw, nh = bw / width, bh / height
    if not all(0.0 <= v <= 1.0 for v in (cx, cy, nw, nh)):
        report.dropped_degenerate += 1
        return None
    return cx, cy, nw, nh


def parse_annotation(
    xml_path: Path,
    image_path: Path,
    collapse: dict[str, str] | None,
    class_to_id: dict[str, int],
    keep_difficult: bool,
    report: Report,
) -> tuple[list[str], bool] | None:
    """Return (label lines, saw_unmapped) for one XML, or None if unparseable.

    `saw_unmapped` matters more than it looks. An image whose only object is
    an unrecognised class would otherwise be written as an empty label -- and
    an empty label is not 'no annotation', it is a positive assertion that the
    image contains nothing. That trains the detector to ignore a real
    artificial object. The caller quarantines those images instead.
    """
    saw_unmapped = False
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError as exc:
        report.unparseable.append(f"{xml_path.name}: {exc}")
        return None

    real = real_image_size(image_path)
    declared = None
    size_el = root.find("size")
    if size_el is not None:
        try:
            declared = (int(float(size_el.findtext("width", "0"))), int(float(size_el.findtext("height", "0"))))
        except ValueError:
            declared = None

    # The real image wins. A wrong <size> silently rescales every box on it.
    if real is None:
        if not declared or declared[0] <= 0 or declared[1] <= 0:
            report.unparseable.append(f"{xml_path.name}: no usable image size")
            return None
        width, height = declared
    else:
        width, height = real
        if declared and declared != real and declared != (0, 0):
            report.size_mismatches.append(
                f"{xml_path.name}: XML says {declared[0]}x{declared[1]}, image is {width}x{height}"
            )

    lines: list[str] = []
    for obj in root.findall("object"):
        raw_name = (obj.findtext("name") or "").strip()
        if not keep_difficult and (obj.findtext("difficult") or "0").strip() == "1":
            report.dropped_difficult += 1
            continue

        training_class, reason = source_to_training(raw_name)
        if training_class is None:
            if reason.startswith("excluded"):
                # A deliberate policy drop. Treating the region as background
                # is intended: we do not want the model finding these at all.
                report.dropped_excluded[raw_name or "(blank)"] += 1
            else:
                report.dropped_unmapped[raw_name or "(blank)"] += 1
                saw_unmapped = True
            continue

        if collapse:
            training_class = collapse.get(training_class, training_class)
        # Ids come from the ACTIVE class list, which --collapse replaces. Using
        # the default table here reported every collapsed box as 'unmapped'.
        if training_class not in class_to_id:
            report.dropped_unmapped[training_class] += 1
            saw_unmapped = True
            continue

        box = obj.find("bndbox")
        if box is None:
            report.dropped_degenerate += 1
            continue
        try:
            coords = [float(box.findtext(k, "nan")) for k in ("xmin", "ymin", "xmax", "ymax")]
        except ValueError:
            report.dropped_degenerate += 1
            continue
        if any(c != c for c in coords):  # NaN
            report.dropped_degenerate += 1
            continue

        yolo = convert_box(*coords, width, height, report)
        if yolo is None:
            continue

        cls_id = class_to_id[training_class]
        lines.append(f"{cls_id} " + " ".join(f"{v:.6f}" for v in yolo))
        report.per_class[training_class] += 1
        report.boxes_kept += 1

    return lines, saw_unmapped


def write_data_yaml(out_dir: Path, class_names: tuple[str, ...]) -> Path:
    """Ultralytics dataset descriptor.

    Points at this flat set so the conversion can be trained on immediately for
    a smoke test. The real training run uses the split produced downstream.
    """
    path = out_dir / "data.yaml"
    body = [
        "# Generated by ai/scripts/voc_to_yolo.py -- do not edit by hand.",
        "# Flat, unsplit set: use it for a smoke test, not for reported metrics.",
        f"path: {out_dir.as_posix()}",
        "train: images",
        "val: images",
        "",
        f"nc: {len(class_names)}",
        "names:",
        *[f"  {i}: {n}" for i, n in enumerate(class_names)],
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert VOC XML annotations to YOLO format.")
    ap.add_argument("--dataset", required=True, help="dataset folder name under ai/data/raw/**, e.g. SCTD")
    ap.add_argument("--out", default=None, help="output dir (default ai/data/interim/<DATASET>)")
    ap.add_argument("--collapse", choices=sorted(COLLAPSE_MAPS), default=None,
                    help="collapse training classes, e.g. 'artificial' for the binary framing")
    ap.add_argument("--keep-difficult", action="store_true", help="keep objects flagged difficult")
    ap.add_argument("--no-copy-images", action="store_true", help="write labels only")
    ap.add_argument("--dry-run", action="store_true", help="report what would happen; write nothing")
    args = ap.parse_args()

    src = find_dataset(args.dataset)
    if src is None:
        print(f"dataset '{args.dataset}' not found under ai/data/raw/")
        print("Download it first -- see docs/DOWNLOAD_GUIDE.md")
        return 1

    xmls = sorted(src.rglob("*.xml"))
    if not xmls:
        print(f"no .xml annotations found in {src}")
        print("If this dataset ships masks or folder-name classes, it needs a different converter.")
        return 1

    collapse = COLLAPSE_MAPS.get(args.collapse) if args.collapse else None
    class_names = tuple(dict.fromkeys(collapse.values())) if collapse else TRAINING_CLASSES
    class_to_id = {name: i for i, name in enumerate(class_names)}

    out_dir = Path(args.out) if args.out else INTERIM_ROOT / args.dataset.upper()
    img_out, lbl_out = out_dir / "images", out_dir / "labels"
    if not args.dry_run:
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

    images = index_images(src)
    report = Report()

    for xml_path in xmls:
        report.xml_files += 1
        image_path = images.get(xml_path.stem)
        if image_path is None:
            # fall back to the <filename> element before giving up
            try:
                declared_name = (ET.parse(xml_path).getroot().findtext("filename") or "").strip()
            except ET.ParseError:
                declared_name = ""
            if declared_name:
                image_path = images.get(Path(declared_name).stem)
        if image_path is None:
            report.missing_images.append(xml_path.name)
            continue

        parsed = parse_annotation(
            xml_path, image_path, collapse, class_to_id, args.keep_difficult, report
        )
        if parsed is None:
            continue
        lines, saw_unmapped = parsed
        if not lines and saw_unmapped:
            # Losing one image is cheap. Teaching the detector that a real
            # artificial object is background is not.
            report.quarantined.append(image_path.name)
            continue
        if not lines:
            # Kept on purpose: an empty label file means "background", and
            # background images are exactly what the hard-negative plan wants.
            report.empty_labels += 1

        if not args.dry_run:
            (lbl_out / (image_path.stem + ".txt")).write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
            if not args.no_copy_images:
                target = img_out / image_path.name
                if not target.exists():
                    shutil.copy2(image_path, target)
                report.images_written += 1
        report.labels_written += 1

    # ---- report ----------------------------------------------------------
    print(f"\nsource : {src}")
    print(f"output : {out_dir if not args.dry_run else '(dry run, nothing written)'}")
    print(f"classes: {', '.join(f'{i}={n}' for i, n in enumerate(class_names))}\n")
    print(f"  {report.xml_files:6d} xml files")
    print(f"  {report.labels_written:6d} labels written")
    print(f"  {report.boxes_kept:6d} boxes kept")
    for name, n in report.per_class.most_common():
        print(f"           {name:<12s} {n}")
    if report.empty_labels:
        print(f"  {report.empty_labels:6d} background images (empty label = intentional negative)")

    problems = False
    if report.dropped_excluded:
        print("\n  excluded by policy (ghostnet/taxonomy.py EXCLUDED_SOURCES):")
        for name, n in report.dropped_excluded.most_common():
            print(f"           {name:<12s} {n}")
    if report.quarantined:
        problems = True
        print()
        print(f"  ! {len(report.quarantined)} image(s) QUARANTINED -- every object on them was an")
        print("    unmapped class. Writing an empty label would have taught the model")
        print("    that a real object is background. Map the class and re-run.")
    if report.dropped_unmapped:
        problems = True
        print("\n  ! UNMAPPED class names -- add them to SOURCE_ALIASES or they are lost:")
        for name, n in report.dropped_unmapped.most_common():
            print(f"           {name:<12s} {n}")
    if report.dropped_difficult:
        print(f"\n  {report.dropped_difficult} object(s) skipped as 'difficult' (--keep-difficult to include)")
    if report.dropped_degenerate:
        print(f"  {report.dropped_degenerate} degenerate box(es) dropped (zero area, NaN, or off-image)")
    if report.clamped:
        print(f"  {report.clamped} box(es) clamped to the image bounds")
    if report.size_mismatches:
        problems = True
        print(f"\n  ! {len(report.size_mismatches)} XML size mismatch(es) -- real image size used:")
        for m in report.size_mismatches[:5]:
            print("           " + m)
    if report.missing_images:
        problems = True
        print(f"\n  ! {len(report.missing_images)} xml with no matching image:")
        for m in report.missing_images[:5]:
            print("           " + m)
    if report.unparseable:
        problems = True
        print(f"\n  ! {len(report.unparseable)} unparseable xml:")
        for m in report.unparseable[:5]:
            print("           " + m)

    if not args.dry_run:
        yaml_path = write_data_yaml(out_dir, class_names)
        (out_dir / "conversion_report.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )
        print(f"\nwrote {show(yaml_path)}")
        print(f"wrote {show(out_dir / 'conversion_report.json')}")

    if report.boxes_kept == 0:
        print("\nNO BOXES WERE PRODUCED. Check the class names above against SOURCE_ALIASES.")
        return 1
    print("\nreview the warnings above before training." if problems else "\nclean conversion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
