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


# ---------------------------------------------------------------------------
# GeoJSON export.
# ---------------------------------------------------------------------------
# These assert the properties that make a file openable on a real chart --
# axis order, ring closure, radius scale -- not the formatting.

import json as _json  # noqa: E402
import math  # noqa: E402

from ghostnet.report import (  # noqa: E402
    CIRCLE_STEPS,
    geojson_features,
    write_geojson,
)


def located(**over) -> dict:
    d = detection(latitude=20.0, longitude=70.0, position_error_m=25.0)
    d.update(over)
    return d


def roles(feats: list[dict]) -> list[str]:
    return [f["properties"]["geometry_role"] for f in feats]


def test_located_detection_emits_point_and_circle():
    feats = geojson_features([frame("f1", [located()])])
    assert roles(feats) == ["position", "uncertainty"]
    assert feats[0]["geometry"]["type"] == "Point"
    assert feats[1]["geometry"]["type"] == "Polygon"
    # Both halves must be reconcilable back to one detection.
    assert {f["properties"]["detection_id"] for f in feats} == {"D-1"}


def test_coordinates_are_lon_lat_not_lat_lon():
    """The single most common way a GeoJSON export lands in the wrong ocean."""
    feats = geojson_features([frame("f1", [located(latitude=20.0, longitude=70.0)])])
    lon, lat = feats[0]["geometry"]["coordinates"]
    assert (lon, lat) == (70.0, 20.0)


def test_error_ring_is_closed_and_matches_the_radius():
    feats = geojson_features([frame("f1", [located(position_error_m=25.0)])])
    ring = feats[1]["geometry"]["coordinates"][0]
    assert len(ring) == CIRCLE_STEPS + 1
    assert ring[0] == ring[-1], "an exterior ring must be explicitly closed"

    # Every vertex should sit ~25 m from the centre, north-south being the
    # axis with no cos(lat) term to get wrong.
    lat_span_m = (max(p[1] for p in ring) - min(p[1] for p in ring)) / 2 * 111_320
    assert 24.0 < lat_span_m < 26.0


def test_ring_is_counterclockwise():
    """RFC 7946 asks the exterior ring to follow the right-hand rule."""
    ring = geojson_features([frame("f1", [located()])])[1]["geometry"]["coordinates"][0]
    area = sum(
        (ring[i + 1][0] - ring[i][0]) * (ring[i + 1][1] + ring[i][1])
        for i in range(len(ring) - 1)
    )
    assert area < 0, "shoelace sign says clockwise; exterior rings must be CCW"


def test_circle_widens_in_longitude_at_high_latitude():
    """A degree of longitude shortens towards the poles; the ring must not."""
    def lon_span(lat):
        d = located(latitude=lat)
        ring = geojson_features([frame("f", [d])])[1]["geometry"]["coordinates"][0]
        return max(p[0] for p in ring) - min(p[0] for p in ring)
    assert lon_span(60.0) > lon_span(0.0) * 1.9


def test_detection_without_coordinates_has_null_geometry():
    d = detection(latitude=None, longitude=None, localization="none")
    feats = geojson_features([frame("f1", [d])])
    assert roles(feats) == ["unlocated"]
    assert feats[0]["geometry"] is None


def test_unlocated_can_be_dropped_for_strict_renderers():
    d = detection(latitude=None, longitude=None, localization="none")
    assert geojson_features([frame("f1", [d])], include_unlocated=False) == []


def test_clean_frames_are_not_placed_on_the_map():
    """Unlike the CSV, a frame with no detections contributes no feature."""
    assert geojson_features([frame("f1", [])]) == []


def test_zero_error_emits_a_point_but_no_degenerate_polygon():
    feats = geojson_features([frame("f1", [located(position_error_m=0.0)])])
    assert roles(feats) == ["position"]


def test_raw_score_never_reaches_the_balloon():
    """The handoff forbids showing raw_score to a user; a popup is user-facing."""
    feats = geojson_features([frame("f1", [located()])])
    assert all("raw_score" not in f["properties"] for f in feats)


def test_written_file_is_a_parseable_featurecollection_without_bom(tmp_path):
    path = write_geojson([frame("f1", [located()])], tmp_path / "s.geojson")
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "a BOM breaks strict JSON parsers"
    doc = _json.loads(raw.decode("utf-8"))
    assert doc["type"] == "FeatureCollection"
    assert len(doc["features"]) == 2
