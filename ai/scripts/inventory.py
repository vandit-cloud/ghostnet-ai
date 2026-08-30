"""Phase 0 (plan section 5): inventory the sonar data that is ACTUALLY on disk.

    python ai/scripts/inventory.py                 # scan and write the CSV
    python ai/scripts/inventory.py --verbose       # per-dataset detail

Writes ai/data/provenance/data_inventory.csv with the field list the plan
specifies. Every measured column comes from reading the files; nothing is
copied from a paper or a README.

The distinction this script exists to enforce
---------------------------------------------
`dataset_candidates.csv` records what published sources CLAIM about datasets we
might use. This script records what we HAVE. They are deliberately separate
files, because the plan's rule is "do not train before understanding what the
data actually contains" -- and the fastest way to violate it is to let a cited
image count stand in for a directory nobody has opened.

Where the two disagree, the scan wins, and the disagreement is reported.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = AI_ROOT / "data"
RAW_ROOT = DATA_ROOT / "raw"
PROVENANCE = DATA_ROOT / "provenance"
CANDIDATES = PROVENANCE / "dataset_candidates.csv"
OUT_CSV = PROVENANCE / "data_inventory.csv"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pgm"}
SONAR_LOG_EXTS = {".xtf", ".jsf", ".sdf", ".s7k", ".segy"}

# The exact field list from plan section 5.
FIELDS = [
    "dataset_id",
    "dataset_name",
    "source",
    "sonar_type",
    "format",
    "resolution",
    "classes",
    "annotation_type",
    "metadata_available",
    "gps_available",
    "license",
    "citation",
    "notes",
]


def load_candidates() -> dict[str, dict[str, str]]:
    """Published claims, keyed by dataset_id. Used only to fill columns that
    cannot be measured (licence, citation, sonar type) and to flag mismatches."""
    if not CANDIDATES.exists():
        return {}
    with CANDIDATES.open(encoding="utf-8", newline="") as fh:
        return {row["dataset_id"]: row for row in csv.DictReader(fh)}


def detect_annotation_type(root: Path) -> tuple[str, int]:
    """Infer the annotation format from what is on disk.

    Ordered by how specific the evidence is: a COCO json is unambiguous, a bare
    .txt is only a YOLO label if it sits beside images and parses like one.
    """
    xml = sum(1 for _ in root.rglob("*.xml"))
    if xml:
        return "VOC XML boxes", xml

    for js in root.rglob("*.json"):
        try:
            blob = json.loads(js.read_text(encoding="utf-8", errors="ignore")[:4000] + "}")
        except Exception:
            blob = {}
        if "annotations" in blob or "categories" in blob:
            return "COCO JSON", sum(1 for _ in root.rglob("*.json"))

    txts = [p for p in root.rglob("*.txt") if p.name.lower() not in {"readme.txt", "license.txt"}]
    yolo_like = 0
    for p in txts[:200]:
        try:
            first = p.read_text(encoding="utf-8", errors="ignore").strip().split("\n")[0].split()
        except Exception:
            continue
        # "<class> <cx> <cy> <w> <h>", all normalised to 0..1
        if len(first) >= 5 and first[0].isdigit():
            try:
                if all(0.0 <= float(v) <= 1.0 for v in first[1:5]):
                    yolo_like += 1
            except ValueError:
                pass
    if yolo_like and yolo_like >= len(txts[:200]) * 0.5:
        return "YOLO boxes", len(txts)

    masks = [p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS and "mask" in p.name.lower()]
    mask_dirs = [d for d in root.rglob("*") if d.is_dir() and d.name.lower() in {"masks", "labels", "annotations", "gt"}]
    if masks or mask_dirs:
        return "segmentation masks", len(masks)

    return "none found (classification-only?)", 0


def infer_classes(root: Path, images: list[Path]) -> str:
    """For classification-style sets the class IS the directory name.

    This is how KLSG and Marine-PULSE are distributed, so folder names are real
    evidence rather than a guess.
    """
    depths = Counter()
    for img in images[:3000]:
        rel = img.relative_to(root)
        if len(rel.parts) >= 2:
            depths[rel.parts[-2]] += 1
    if not depths:
        return "(flat directory, no class folders)"
    parts = [f"{name}:{n}" for name, n in depths.most_common(12)]
    return " / ".join(parts)


def sample_resolutions(images: list[Path], limit: int = 40) -> str:
    """Read real pixel dimensions. Resolution drives imgsz and tiling, and a
    dataset of wildly mixed sizes is a preprocessing decision, not a footnote."""
    try:
        from PIL import Image
    except ImportError:
        return "(pillow not installed)"
    seen = Counter()
    step = max(1, len(images) // limit)
    for img in images[::step][:limit]:
        try:
            with Image.open(img) as im:
                seen[f"{im.width}x{im.height}"] += 1
        except Exception:
            continue
    if not seen:
        return "unreadable"
    top = seen.most_common(3)
    tail = f" (+{len(seen) - len(top)} more sizes)" if len(seen) > len(top) else ""
    return ", ".join(f"{s}x{n}" for s, n in top) + tail


def looks_geotagged(root: Path) -> tuple[str, str]:
    """Does anything here carry navigation data?

    Two separate questions, both load-bearing for section 27 geotagging:
    metadata of any kind, and specifically GPS. A dataset without either can
    train a detector but can never validate the geotagging deliverable.
    """
    sidecars = [p for p in root.rglob("*") if p.suffix.lower() in {".csv", ".json", ".txt", ".nav", ".gpx"}]
    logs = [p for p in root.rglob("*") if p.suffix.lower() in SONAR_LOG_EXTS]
    metadata = "yes" if (sidecars or logs) else "no"

    gps = "no"
    if logs:
        gps = "likely (raw sonar logs present)"
    else:
        for p in sidecars[:60]:
            try:
                head = p.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
            except Exception:
                continue
            if any(k in head for k in ("latitude", "longitude", "lat,", "lon,", "gps", "easting")):
                gps = "yes (" + p.name + ")"
                break
    return metadata, gps


def scan(dataset_dir: Path, candidates: dict[str, dict[str, str]]) -> dict[str, str] | None:
    images = [p for p in dataset_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
    logs = [p for p in dataset_dir.rglob("*") if p.suffix.lower() in SONAR_LOG_EXTS]
    if not images and not logs:
        return None

    dataset_id = dataset_dir.name.upper()
    cand = candidates.get(dataset_id, {})
    ann_type, ann_count = detect_annotation_type(dataset_dir)
    metadata, gps = looks_geotagged(dataset_dir)

    exts = Counter(p.suffix.lower() for p in images)
    fmt = ", ".join(f"{e}:{n}" for e, n in exts.most_common(4)) or "raw logs only"

    notes = []
    claimed = cand.get("image_count", "").strip()
    if claimed.isdigit() and images:
        if abs(int(claimed) - len(images)) > max(5, int(claimed) * 0.02):
            notes.append(f"MISMATCH: {claimed} images claimed, {len(images)} found on disk")
    if logs:
        notes.append(f"{len(logs)} raw sonar log(s) present")
    if ann_count:
        notes.append(f"{ann_count} annotation file(s)")
    if cand.get("notes"):
        notes.append("claim: " + cand["notes"])
    if not cand:
        notes.append("not in dataset_candidates.csv - provenance unrecorded")

    return {
        "dataset_id": dataset_id,
        "dataset_name": cand.get("dataset_name", dataset_dir.name),
        "source": dataset_dir.parent.name,
        "sonar_type": cand.get("sonar_type", "UNKNOWN - verify before use"),
        "format": fmt,
        "resolution": sample_resolutions(images) if images else "n/a",
        "classes": infer_classes(dataset_dir, images) if images else "n/a",
        "annotation_type": ann_type,
        "metadata_available": metadata,
        "gps_available": gps,
        "license": cand.get("license", "UNKNOWN - do not use until verified"),
        "citation": cand.get("url", ""),
        "notes": "; ".join(notes),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    candidates = load_candidates()
    if not RAW_ROOT.exists():
        print("no ai/data/raw/ directory; nothing to inventory")
        return 1

    rows = []
    for bucket in sorted(p for p in RAW_ROOT.iterdir() if p.is_dir()):
        for dataset_dir in sorted(p for p in bucket.iterdir() if p.is_dir()):
            row = scan(dataset_dir, candidates)
            if row:
                rows.append(row)
                if args.verbose:
                    print("\n== " + row["dataset_id"])
                    for k in FIELDS:
                        print(f"   {k:20s} {row[k]}")

    PROVENANCE.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    if not rows:
        print("ai/data/raw/ is empty -- nothing acquired yet.")
        print("Candidate datasets and how to get them: ai/data/provenance/dataset_candidates.csv")
        print("Wrote an empty " + str(OUT_CSV.relative_to(AI_ROOT.parent)) + " (header only).")
        return 0

    print("inventoried " + str(len(rows)) + " dataset(s) -> " + str(OUT_CSV.relative_to(AI_ROOT.parent)))
    mismatches = [r for r in rows if "MISMATCH" in r["notes"]]
    unlicensed = [r for r in rows if r["license"].startswith("UNKNOWN")]
    for r in mismatches:
        print("  ! " + r["dataset_id"] + ": " + r["notes"].split(";")[0])
    for r in unlicensed:
        print("  ! " + r["dataset_id"] + ": licence unverified -- resolve before training on it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
