"""CSV anomaly reports (problem statement requirement 12).

    from ghostnet import detect
    from ghostnet.report import write_csv

    frames = [detect(p, meta) for p in paths]
    write_csv(frames, "survey_042.csv")

The JSON payload is the contract and stays authoritative; this is the form an
operator opens in Excel, sorts, and hands to whoever does the recovery dive.

Three decisions that are easy to get wrong
------------------------------------------
1. CLEAN FRAMES GET A ROW. A file containing three rows is ambiguous in the
   worst possible way: it could mean "three anomalies across 500 frames" or
   "we only managed to process three frames". In survey work the difference
   between "we looked and it was clear" and "we never looked" is the whole
   point, so every frame appears, and `record_type` says which kind of row it
   is. Filtering to record_type == "detection" gets the anomaly list back.

2. UTF-8 WITH BOM, and newline="". Excel on Windows reads a BOM-less UTF-8 CSV
   as cp1252 and mangles any non-ASCII; without newline="" the csv module and
   Windows each add a carriage return and every other row comes out blank.
   Both are silent, and both are the reason this writes files rather than
   telling callers to use csv.writer themselves.

3. FRAME ORDER, not confidence order. This is a record of a survey, and a
   record that reorders itself is hard to reconcile against the JSON or the
   navigation log. Sorting by confidence is one click in any spreadsheet;
   recovering the original order is not.

Nothing here rounds a coordinate. Latitude at six decimal places is ~0.1 m,
and the position error the model reports is metres to tens of metres -- so
truncating would throw away less than the error bar, but it would also make
two positions that differ compare equal, and that is a debugging trap nobody
needs. Confidences ARE rounded, to four places, because a float repr like
0.30000000000000004 in a report shown to an operator looks broken.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Sequence

#: Column order is the wire format for anyone who scripts against these files.
#: Append, never reorder or rename.
COLUMNS: tuple[str, ...] = (
    "record_type",
    "survey_id",
    "frame_id",
    "detection_id",
    "class",
    "calibrated_confidence",
    "raw_score",
    "uncertainty",
    "review_status",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
    "latitude",
    "longitude",
    "position_error_m",
    "localization",
    "width_m",
    "length_m",
    "dimension_status",
    "artificial_verification",
    "shadow_context",
    "notes",
    "frame_warnings",
    "model_version",
    "contract_version",
)


def _num(v: Any, places: int | None = None) -> Any:
    """None becomes an empty cell, never the string 'None'."""
    if v is None:
        return ""
    if places is not None and isinstance(v, (int, float)):
        return round(float(v), places)
    return v


def csv_rows(frames: Iterable[dict]) -> list[dict[str, Any]]:
    """Flatten contract payloads into one row per detection, plus one row per
    frame that produced none."""
    rows: list[dict[str, Any]] = []
    for frame in frames:
        warnings = "; ".join(frame.get("warnings", []) or [])
        base = {
            "survey_id": frame.get("survey_id", ""),
            "frame_id": frame.get("frame_id", ""),
            "frame_warnings": warnings,
            "contract_version": frame.get("contract_version", ""),
            "model_version": (frame.get("provenance") or {}).get("model_version", ""),
        }

        detections = frame.get("detections") or []
        if not detections:
            rows.append({**{c: "" for c in COLUMNS}, **base, "record_type": "frame_clear"})
            continue

        for d in detections:
            bbox = list(d.get("bbox") or [])
            bbox += [None] * (4 - len(bbox))
            dims = d.get("dimensions") or {}
            ev = d.get("evidence_summary") or {}
            rows.append({
                **{c: "" for c in COLUMNS},
                **base,
                "record_type": "detection",
                "detection_id": d.get("detection_id", ""),
                "class": d.get("class", ""),
                "calibrated_confidence": _num(d.get("calibrated_confidence"), 4),
                "raw_score": _num(d.get("raw_score"), 4),
                "uncertainty": d.get("uncertainty", ""),
                "review_status": d.get("review_status", ""),
                "bbox_x": _num(bbox[0]), "bbox_y": _num(bbox[1]),
                "bbox_w": _num(bbox[2]), "bbox_h": _num(bbox[3]),
                "latitude": _num(d.get("latitude")),
                "longitude": _num(d.get("longitude")),
                "position_error_m": _num(d.get("position_error_m"), 2),
                "localization": d.get("localization", ""),
                "width_m": _num(dims.get("width"), 2),
                "length_m": _num(dims.get("length"), 2),
                "dimension_status": dims.get("status", ""),
                "artificial_verification": ev.get("artificial_verification", ""),
                "shadow_context": ev.get("shadow_context", ""),
                "notes": ev.get("notes", ""),
            })
    return rows


def write_csv(frames: Sequence[dict], path: str | Path) -> Path:
    """Write a survey report. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = csv_rows(frames)
    # utf-8-sig and newline="" are load-bearing on Windows -- see the module
    # docstring. Both failures are silent.
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path
