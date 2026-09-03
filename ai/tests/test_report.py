"""CSV report tests (problem statement requirement 12).

The point of a report is that a stored row can be reconciled later against the
JSON, the navigation log, or the dive that acted on it. So these assert the
properties that make that possible, not the formatting.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.report import COLUMNS, csv_rows, write_csv  # noqa: E402


def frame(frame_id: str, detections: list[dict], warnings: list[str] | None = None) -> dict:
    return {
        "survey_id": "S1", "frame_id": frame_id, "detections": detections,
        "provenance": {"model_version": "gv5-yolo11s"},
        "warnings": warnings or [], "contract_version": "1.0.0",
    }


def detection(**over) -> dict:
    d = {
        "detection_id": "D-1", "class": "debris", "raw_score": 0.5,
        "calibrated_confidence": 0.30000000000000004, "uncertainty": "medium",
        "bbox": [1, 2, 3, 4], "mask": None, "latitude": None, "longitude": None,
        "position_error_m": None, "localization": "none",
        "dimensions": {"width": None, "length": None, "status": "unavailable"},
        "review_status": "pending", "model_version": "gv5-yolo11s",
        "evidence_summary": {"artificial_verification": "positive",
                             "shadow_context": "absent", "notes": ""},
    }
    d.update(over)
    return d


def test_a_clean_frame_still_produces_a_row():
    """Three rows must not be ambiguous between 'three anomalies in 500 frames'
    and 'we only processed three frames'."""
    rows = csv_rows([frame("f1", []), frame("f2", [detection()])])
    assert [r["record_type"] for r in rows] == ["frame_clear", "detection"]
    assert [r["frame_id"] for r in rows] == ["f1", "f2"]


def test_missing_values_are_blank_not_the_string_none():
    """'None' in a spreadsheet sorts and filters as text and silently poisons
    any numeric column."""
    rows = csv_rows([frame("f1", [detection()])])
    assert rows[0]["latitude"] == ""
    assert rows[0]["width_m"] == ""
    assert "None" not in set(map(str, rows[0].values()))


def test_confidence_is_rounded_for_display():
    rows = csv_rows([frame("f1", [detection()])])
    assert rows[0]["calibrated_confidence"] == 0.3


def test_coordinates_keep_full_precision():
    """Rounding a coordinate makes two distinct positions compare equal."""
    rows = csv_rows([frame("f1", [detection(latitude=18.921872770228,
                                            longitude=72.834693748499)])])
    assert rows[0]["latitude"] == 18.921872770228


def test_frame_order_is_preserved(tmp_path):
    """A survey record that reorders itself cannot be reconciled with the JSON."""
    frames = [frame(f"f{i}", [detection(calibrated_confidence=i / 10)]) for i in range(5)]
    rows = csv_rows(frames)
    assert [r["frame_id"] for r in rows] == [f"f{i}" for i in range(5)]


def test_written_file_has_a_bom_and_no_blank_rows(tmp_path):
    """Excel on Windows needs the BOM; newline='' stops every other row being
    empty. Both failures are silent, so they are asserted here."""
    p = write_csv([frame("f1", [detection()]), frame("f2", [])], tmp_path / "r.csv")
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM; Excel will mangle non-ASCII"
    assert b"\r\r\n" not in raw, "doubled carriage returns; blank row between every record"

    with open(p, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert list(rows[0].keys()) == list(COLUMNS)


def test_every_column_is_populated_or_deliberately_blank():
    """A typo in a key name shows up as a column that is always empty."""
    rows = csv_rows([frame("f1", [detection(latitude=1.0, longitude=2.0,
                                            position_error_m=3.0, localization="frame-level")],
                           warnings=["something"])])
    unexpected = {c for c in COLUMNS if c not in rows[0]}
    assert not unexpected, unexpected
