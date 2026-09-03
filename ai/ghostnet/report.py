"""Operator-facing survey reports: CSV and GeoJSON (PS requirements 12 and
geotagged reporting).

    from ghostnet import detect
    from ghostnet.report import write_csv, write_geojson

    frames = [detect(p, meta) for p in paths]
    write_csv(frames, "survey_042.csv")          # opens in Excel
    write_geojson(frames, "survey_042.geojson")  # opens in QGIS / Google Earth

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
import json
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


# ---------------------------------------------------------------------------
# GeoJSON export (problem statement requirement: geotagged reporting).
# ---------------------------------------------------------------------------
#
# The CSV is what an operator opens in Excel. This is what they open in QGIS or
# Google Earth, and it is the only export that puts a detection on a real chart.
#
# TWO FEATURES PER DETECTION, not one.
# ------------------------------------
# A point alone is a lie of precision. `position_error_m` is a real number
# derived from GPS scatter, heading error and altitude uncertainty, and the
# integration plan already tells Member 2 "draw the error radius, not a pin" for
# exactly that reason. An export that drops the radius quietly reintroduces the
# claim the rest of the system refuses to make.
#
# So each located detection emits a Point AND a Polygon approximating its error
# circle, sharing a `detection_id` and distinguished by `geometry_role`. Two
# features rather than one GeometryCollection because GeometryCollection support
# is patchy and awkward to style: QGIS wants a geometry type per layer, and a
# styler can split these with one attribute filter.
#
# GeoJSON has no circle primitive, so the radius is polygonised -- CIRCLE_STEPS
# vertices, closed ring. 64 is well under a metre of chord error at the tens of
# metres these radii run to, and stays small enough that a survey line's worth
# of them still opens instantly.
#
# COORDINATE ORDER IS [longitude, latitude].
# ------------------------------------------
# RFC 7946, and the single most common way a GeoJSON export lands in the Gulf of
# Guinea. Everything else in this project says lat/lon in that order, so the
# swap happens here, once, and is asserted in the tests.

#: Vertices in a polygonised error circle. See the note above.
CIRCLE_STEPS: int = 64

#: WGS-84 equatorial radius, metres. Sub-metre differences between this and a
#: proper geodesic are far inside a position error measured in metres.
_EARTH_RADIUS_M: float = 6378137.0

#: Coordinate output precision. 7 decimal places is ~1 cm -- far finer than the
#: error bar, but rounding is what makes two genuinely different positions
#: compare equal, and that is a debugging trap. Same reasoning as the CSV.
_COORD_PLACES: int = 7


def _error_ring(lat: float, lon: float, radius_m: float) -> list[list[float]]:
    """A closed ring of [lon, lat] approximating a circle of `radius_m`.

    Counterclockwise, because RFC 7946 asks an exterior ring to follow the
    right-hand rule, and generating it correctly is cheaper than the class of
    bug where a renderer fills the whole world except the circle.
    """
    import math

    dlat = math.degrees(radius_m / _EARTH_RADIUS_M)
    # A degree of longitude shortens towards the poles. Clamped so a detection
    # at an implausible latitude produces a fat ring rather than a divide-by-zero.
    dlon = dlat / max(math.cos(math.radians(lat)), 1e-6)

    ring = []
    for i in range(CIRCLE_STEPS):
        theta = 2.0 * math.pi * i / CIRCLE_STEPS
        ring.append([
            round(lon + dlon * math.cos(theta), _COORD_PLACES),
            round(lat + dlat * math.sin(theta), _COORD_PLACES),
        ])
    ring.append(ring[0])  # explicitly closed; a renderer may not close it for you
    return ring


def _properties(row: dict[str, Any]) -> dict[str, Any]:
    """Popup content. Google Earth shows these in the balloon, QGIS in the
    attribute table, so empty cells are dropped rather than shown as blanks."""
    keep = (
        "survey_id", "frame_id", "detection_id", "class", "calibrated_confidence",
        "uncertainty", "review_status", "position_error_m", "localization",
        "width_m", "length_m", "dimension_status", "artificial_verification",
        "shadow_context", "notes", "model_version", "contract_version",
    )
    # raw_score is deliberately absent: the handoff forbids showing it to a
    # user, and a GeoJSON balloon is about as user-facing as it gets.
    props = {k: row[k] for k in keep if row.get(k) not in ("", None)}
    label = row.get("class") or "detection"
    conf = row.get("calibrated_confidence")
    props["name"] = f"{label} {conf}" if conf not in ("", None) else str(label)
    return props


def geojson_features(frames: Iterable[dict], include_unlocated: bool = True) -> list[dict]:
    """Contract payloads -> GeoJSON features, two per located detection.

    `include_unlocated` keeps detections that have no coordinates as features
    with `"geometry": null`. That is valid RFC 7946 and it matches the rule the
    CSV follows -- a thing we found but could not place is a fact worth
    carrying, not one to drop silently. Be aware some GIS tools skip
    null-geometry features without saying so; pass False when the consumer is a
    renderer that must not see them.
    """
    features: list[dict] = []
    for row in csv_rows(frames):
        if row.get("record_type") != "detection":
            continue  # a clean frame has nothing to place on a map
        lat, lon = row.get("latitude"), row.get("longitude")
        props = _properties(row)

        if lat in ("", None) or lon in ("", None):
            if include_unlocated:
                features.append({
                    "type": "Feature",
                    "geometry": None,
                    "properties": {**props, "geometry_role": "unlocated"},
                })
            continue

        lat, lon = float(lat), float(lon)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [
                round(lon, _COORD_PLACES), round(lat, _COORD_PLACES),
            ]},
            "properties": {**props, "geometry_role": "position"},
        })

        radius = row.get("position_error_m")
        if radius not in ("", None) and float(radius) > 0:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [
                    _error_ring(lat, lon, float(radius)),
                ]},
                "properties": {**props, "geometry_role": "uncertainty"},
            })
    return features


def write_geojson(
    frames: Sequence[dict],
    path: str | Path,
    include_unlocated: bool = True,
) -> Path:
    """Write a FeatureCollection an operator can open on a chart. Returns the path.

    Plain UTF-8 with no BOM, unlike the CSV: RFC 7946 requires UTF-8 and a BOM
    breaks strict JSON parsers. The two files disagree on this on purpose --
    one is read by Excel, the other by a JSON parser.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    collection = {
        "type": "FeatureCollection",
        "features": geojson_features(frames, include_unlocated=include_unlocated),
    }
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(collection, fh, ensure_ascii=False, indent=1)
    return path
