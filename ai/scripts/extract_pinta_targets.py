"""Extract sonar snippets and target metadata from BSH/PINTA target reports.

    python ai/scripts/extract_pinta_targets.py --dry-run
    python ai/scripts/extract_pinta_targets.py

Reads  ai/data/raw/N-09_SSS_*/02_targets/*.pdf
Writes ai/data/interim/PINTA-N09/{images/*.png, targets.jsonl, extract_report.json}

What these reports are
----------------------
BSH's Preliminary Investigation of Sites (PINTA) publishes side-scan results
for German North Sea wind-farm sites. Each sub-area ships a target report: one
row per sonar contact, carrying a 431x431 waterfall snippet plus position, the
source .jsf file and ping number, tow geometry, and measured object dimensions.
563 targets across N-09-01..04. They are WATERFALL crops, which is the geometry
this project trains on -- unlike the site's GeoTIFF mosaic, which is
geo-rectified and slant-range corrected.

The reason this script exists rather than a plain image dump
-------------------------------------------------------------
Every snippet has the answer drawn on it: a blue circle over the target, on
561 of 563. Imported raw, that is a label leak -- the model learns the circle.
`_screening.overlay_signals` did not catch it, because its four signals are
fractions of frame and a 25x25 marker is 0.0014 of a 431x431 snippet against
an `off_hue` limit of 0.040. Measured: 0 of 47 breached. The `marker_paint`
signal was added for this and is asserted on every frame written below.

So the marker is removed. It is also, being a cold hue no sonar palette
contains, a free localisation label -- the one thing these reports do not
state in text. Detect it, record it, then paint it out.

Note that the four sub-areas are not one source. N-09-01/02 (446 targets,
2021, "BSH-*.pdf") are greyscale; N-09-03/04 (117 targets, 2023,
"TargetReport-*.pdf") use an amber palette and additionally burn the target ID
in as text beside the circle. Both are handled: the detector is hue-based so
the palette does not matter, and removal inpaints EVERY cold-hue blob rather
than the largest, which is what takes the ID text with it. Inpainting only the
circle left 117 frames still flagged, which is how the ID was noticed.

Three honesty constraints, enforced here rather than remembered
----------------------------------------------------------------
1. NO BOX IS EMITTED. The marker gives a POINT. Turning it into a YOLO box
   needs metres-per-pixel, and each snippet carries its own range scale that
   is only readable by OCR'ing the axis ticks. `Target Width/Length` from the
   report text is recorded in METRES, unconverted. Inventing a box from an
   assumed scale would be fabricating ground truth, which is the failure
   `import_classification.py` refuses to commit for classification positives.

2. INPAINTED PIXELS ARE SYNTHETIC. The circle sits ON the target, so removing
   it reconstructs pixels that were never measured. Every record carries
   `inpainted_px` and the mask is saved, so no downstream reader has to take
   it on trust. --keep-marker skips inpainting for inspection.

3. CLASSIFICATIONS ARE THE SURVEYOR'S, HEDGED AS THEY WROTE THEM. 446 of 563
   targets have a blank Classification1, and most that are filled end in "?"
   ("Objekt?", "Seil?", "Wrack?"). They are copied verbatim, German intact,
   never normalised into a confident label. Mapping them to training classes
   is a separate, human decision -- see taxonomy.py for where that belongs.

Licence
-------
RESOLVED 2026-09-22 -- cleared for training. The earlier "no terms-of-use text
was found on pinta.bsh.de" was a scraping failure, not an absence: the portal
is JSF and redirects through `jsessionid`, so a saved page keeps the nav link
but not the page. The terms are at https://pinta.bsh.de -> Impressum /
Rechtliche Hinweise. Training a detector is *Drittverwendung*, which the clause
permits subject to two conditions -- cite per the usual conventions, and
disclose modifications when publishing. Both are satisfied: the citation is in
docs/DATA.md, and every record written here carries `inpainted_px` with the
mask saved alongside. What BSH disclaims is verification, not permission.

Two limits still bind. PINTA data may NOT be sublicensed onward, so it cannot
go to GhostNetZero. And BSH's linking policy asks for `https://pinta.bsh.de`
with the area named in text -- not a deep link to /N-*. The quoted clause and
the required citation string are in docs/DATA.md, "BSH / PINTA N-09".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _screening import DEFAULT_LIMITS, cold_mask, marker_blob, overlay_signals  # noqa: E402

RAW_ROOT = AI_ROOT / "data" / "raw"
OUT_ROOT = AI_ROOT / "data" / "interim" / "PINTA-N09"

TARGET_ID_RE = re.compile(r"^N-09-\d\d-\d{3,4}$")
#: Rows pair an image with a target id by vertical position; measured offset is
#: ~1.5 pt, so anything inside this is the same row and anything outside is a
#: pairing bug worth failing on.
ROW_TOLERANCE_PT = 25.0

FIELDS = {
    "sonar_time": r"Sonar Time at Target:\s*(.+)",
    "source_jsf": r"Acoustic Source File:\s*(.+?)(?:\s*●|\n)",
    "ping_number": r"Ping Number:\s*(\d+)",
    "range_to_target_m": r"Range to target:\s*([\d.]+)",
    "fish_height_m": r"Fish Height:\s*([\d.]+)",
    "heading_deg": r"Heading:\s*([\d.]+)",
    "water_depth_m": r"Water Depth:\s*([\d.]+)",
    "line_name": r"Line Name:\s*(.+)",
    "target_width_m": r"Target Width:\s*([\d.]+)",
    "target_height_m": r"Target Height:\s*([\d.]+)",
    "target_length_m": r"Target Length:\s*([\d.]+)",
    "target_shadow_m": r"Target Shadow:\s*([\d.]+)",
    "classification1": r"Classification1:\s*(.*)",
    "classification2": r"Classification2:\s*(.*)",
    "description": r"Description:\s*(.*)",
}
LATLON_RE = re.compile(
    r"(\d+)°\s*([\d.]+)'\s*([NS])\s+(\d+)°\s*([\d.]+)'\s*([EW])\s*\(WGS84\)"
)


def dms_to_deg(deg: str, minutes: str, hemi: str) -> float:
    v = float(deg) + float(minutes) / 60.0
    return -v if hemi in ("S", "W") else v


def parse_block(text: str) -> dict:
    """Pull the report's fields out of one target's text block, verbatim."""
    out: dict[str, object] = {}
    for key, pattern in FIELDS.items():
        m = re.search(pattern, text)
        if not m:
            continue
        raw = m.group(1).strip()
        # A blank field is followed on the next line by the next bullet; the
        # greedy '.*' picks that up, so treat a bullet as empty.
        if raw.startswith("●") or not raw:
            out[key] = None
            continue
        out[key] = float(raw) if key.endswith(("_m", "_deg")) else raw
    m = LATLON_RE.search(text)
    if m:
        out["lat_wgs84"] = round(dms_to_deg(m.group(1), m.group(2), m.group(3)), 8)
        out["lon_wgs84"] = round(dms_to_deg(m.group(4), m.group(5), m.group(6)), 8)
    return out


def content_extent(grey: np.ndarray, floor: int = 30) -> tuple[int, int]:
    """Right/bottom edge of the sonar area, excluding the black ruler strips.

    Measured rather than hard-coded: the strips are 392..430 on almost every
    snippet, but a handful run to 410. Falls back to the full frame if the
    detected area is implausibly small, so a surprise crops nothing.
    """
    cols = np.nonzero(grey.mean(axis=0) >= floor)[0]
    rows = np.nonzero(grey.mean(axis=1) >= floor)[0]
    w = int(cols.max()) + 1 if len(cols) else grey.shape[1]
    h = int(rows.max()) + 1 if len(rows) else grey.shape[0]
    if w < 0.8 * grey.shape[1] or h < 0.8 * grey.shape[0]:
        return grey.shape[1], grey.shape[0]
    return w, h


def find_marker(bgr: np.ndarray) -> tuple[np.ndarray, dict] | tuple[None, None]:
    """Locate the annotation circle, via the shared cold-hue detector.

    Deliberately the SAME function `_screening` thresholds on, so the guard and
    the remover can never disagree about what a marker is. A private copy here
    would let the extractor clean something screening still rejects, or worse,
    pass something it never looked at.
    """
    area, mask, centroid = marker_blob(bgr)
    if not area or mask is None or centroid is None:
        return None, None
    ys, xs = np.nonzero(mask)
    return mask, {
        "marker_px": int(area),
        "marker_bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        "marker_centroid_xy": [round(centroid[0], 2), round(centroid[1], 2)],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract PINTA target snippets and metadata.")
    ap.add_argument("--raw", default=str(RAW_ROOT))
    ap.add_argument("--out", default=str(OUT_ROOT))
    ap.add_argument("--keep-marker", action="store_true",
                    help="do not inpaint; for inspecting what was detected")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        import fitz
    except ImportError:
        print("! PyMuPDF (fitz) is required: pip install pymupdf")
        return 1

    pdfs = sorted(Path(args.raw).glob("N-09_SSS_*/02_targets/*.pdf"))
    if not pdfs:
        print(f"! no target reports under {args.raw}/N-09_SSS_*/02_targets/")
        return 1

    out_root = Path(args.out)
    images_dir = out_root / "images"
    masks_dir = out_root / "masks"
    records: list[dict] = []
    stats = Counter()
    unpaired: list[str] = []

    for pdf_path in pdfs:
        doc = fitz.open(pdf_path)
        sub_area = re.search(r"N-09-\d\d", pdf_path.stem + pdf_path.parent.parent.name)
        sub_area = sub_area.group(0) if sub_area else pdf_path.stem

        for page in doc:
            images = sorted(page.get_image_info(xrefs=True), key=lambda i: i["bbox"][1])
            words = [w for w in page.get_text("words") if TARGET_ID_RE.match(w[4])]
            words.sort(key=lambda w: w[1])
            page_text = page.get_text()

            # Pair by row. Anything that does not pair is reported, never guessed.
            used = set()
            for w in words:
                tid, ty = w[4], w[1]
                best, best_d = None, ROW_TOLERANCE_PT
                for k, info in enumerate(images):
                    if k in used:
                        continue
                    d = abs(info["bbox"][1] - ty)
                    if d < best_d:
                        best, best_d = k, d
                if best is None:
                    unpaired.append(f"{sub_area}/{tid} (no image within {ROW_TOLERANCE_PT}pt)")
                    stats["unpaired_target"] += 1
                    continue
                used.add(best)

                # Text block for this target: from its id to the next id.
                start = page_text.find(tid)
                nxt = [page_text.find(x[4], start + 1) for x in words if x[4] != tid]
                nxt = [n for n in nxt if n > start]
                block = page_text[start:min(nxt) if nxt else len(page_text)]

                raw_img = doc.extract_image(images[best]["xref"])
                bgr = cv2.imdecode(np.frombuffer(raw_img["image"], np.uint8), cv2.IMREAD_COLOR)
                if bgr is None:
                    stats["undecodable"] += 1
                    continue

                mask, marker = find_marker(bgr)
                rec = {"target_id": tid, "sub_area": sub_area,
                       "source_pdf": pdf_path.name, "page": page.number + 1}
                rec.update(parse_block(block))

                if mask is None:
                    stats["no_marker"] += 1
                    rec["marker_px"] = 0
                else:
                    rec.update(marker)
                    stats["with_marker"] += 1

                grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                w_c, h_c = content_extent(grey)
                rec["crop_wh"] = [w_c, h_c]
                rec["original_wh"] = [bgr.shape[1], bgr.shape[0]]

                out_img = bgr
                if mask is not None and not args.keep_marker:
                    # ALL cold-hue paint, not just the circle: N-09-03/04 print
                    # the target ID beside it in the same blue, and leaving that
                    # is the same label leak in a different shape.
                    full = cold_mask(bgr)
                    dilated = cv2.dilate(full, np.ones((3, 3), np.uint8), iterations=2)
                    out_img = cv2.inpaint(bgr, dilated, 3, cv2.INPAINT_TELEA)
                    rec["inpainted_px"] = int(dilated.sum())
                    rec["inpainted_blobs_px"] = int(full.sum())
                    rec["inpainted"] = True
                else:
                    rec["inpainted"] = False

                out_img = out_img[:h_c, :w_c]
                if mask is not None:
                    cx, cy = rec["marker_centroid_xy"]
                    rec["marker_centroid_norm"] = [round(cx / w_c, 5), round(cy / h_c, 5)]
                    rec["marker_inside_crop"] = bool(cx < w_c and cy < h_c)

                # The guard this data motivated, asserted on the output.
                sig = overlay_signals(out_img)
                rec["marker_paint_after"] = sig["marker_paint"]
                if sig["marker_paint"] > DEFAULT_LIMITS["marker_paint"]:
                    stats["still_painted"] += 1
                    rec["clean"] = False
                else:
                    rec["clean"] = True

                if not args.dry_run:
                    images_dir.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(images_dir / f"{tid}.png"), out_img)
                    if mask is not None:
                        masks_dir.mkdir(parents=True, exist_ok=True)
                        cv2.imwrite(str(masks_dir / f"{tid}.png"), (mask[:h_c, :w_c] * 255))
                records.append(rec)
                stats["targets"] += 1

            for k, info in enumerate(images):
                if k not in used:
                    stats["unpaired_image"] += 1
        doc.close()

    print(f"  {stats['targets']} targets extracted from {len(pdfs)} reports")
    print(f"    with marker      {stats['with_marker']}")
    print(f"    no marker found  {stats['no_marker']}")
    print(f"    still painted    {stats['still_painted']}  (should be 0)")
    print(f"    unpaired target  {stats['unpaired_target']}   unpaired image {stats['unpaired_image']}")
    classified = sum(1 for r in records if r.get("classification1"))
    print(f"    classification1 non-blank: {classified} of {stats['targets']}")
    if unpaired:
        print("\n  UNPAIRED (not written):")
        for u in unpaired[:10]:
            print(f"    {u}")

    if args.dry_run:
        print("\n  --dry-run: nothing written.")
        return 0

    out_root.mkdir(parents=True, exist_ok=True)
    with (out_root / "targets.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    cls = Counter(r.get("classification1") or "(blank)" for r in records)
    (out_root / "extract_report.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "BSH PINTA, site N-9.1, area N-09 sub-areas 01-04",
        "licence": ("RESOLVED 2026-09-22 -- BSH Impressum/Rechtliche Hinweise "
                    "permits Drittverwendung subject to citation and disclosure "
                    "of modifications; both satisfied. Cleared for training. "
                    "NOT sublicensable onward. See docs/DATA.md, 'BSH / PINTA N-09'."),
        "reports": [p.name for p in pdfs],
        "counts": dict(stats),
        "classification1_values": dict(cls.most_common()),
        "unpaired": unpaired,
        "geometry": "waterfall crops, not mosaic",
        "no_boxes_emitted": "marker gives a point; metres-per-pixel is not recoverable from text",
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  wrote {out_root / 'targets.jsonl'}")
    print(f"        {images_dir}  ({stats['targets']} png)")
    print("\n  NOT cleared for training: licence unresolved (docs/DATA.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
