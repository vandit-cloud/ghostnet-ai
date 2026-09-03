"""Turn a raw sonar file into detections: XTF -> waterfall -> tiles -> detect().

    from ghostnet import detect_survey
    result = detect_survey("line01.XTF", out_dir="frames/line01")

This is the function that makes the system a survey tool rather than a tile
classifier. Everything it needs already existed in pieces -- `xtf` reads the
file and derives geometry from the ping headers, `detect` scores one frame --
and this joins them.

Why that matters more than it sounds
------------------------------------
The geometry a position needs (nadir column, range resolution, altitude above
the seabed, heading) is IN THE PING HEADERS. Read from there, coordinates come
from the survey itself, so nobody has to hand-write a metadata sidecar and
nobody downstream has to supply values they do not have. Before this, every
detection from a real file came back with `localization: "none"`.

Tiles are written to disk, on purpose
-------------------------------------
Two reasons, and neither is laziness. `detect()` takes a path because that is
the frozen integration surface and widening it to accept arrays is a contract
change. And the web app needs the image files anyway -- it serves them back to
a reviewer who wants to see the frame a box was drawn on. A tile costs about
40 KB and inference costs 58 ms, so the write is not the expensive part.

Tile size follows the training data
-----------------------------------
640 px, because that is what the detector was trained on. The waterfall from a
real EdgeTech 4200 line is 2048 px wide, so a frame is cut BOTH ways -- three
and a bit across, one per 640 pings down -- and `nadir_col` is shifted by the
horizontal offset for each one. Feeding the full 2048-wide waterfall in would
let ultralytics letterbox it down to 640 and throw away three quarters of the
across-track resolution, which is exactly the detail a small object lives in.

A tile whose nadir sits outside its own bounds is normal and correct: for a
far-range tile the across-track distance is large, and `geo.pixel_to_ground_offset`
handles a column far from nadir without special-casing.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyproj import Geod

from .config import SETTINGS, Settings
from .contract import FramePosition
from .infer import detect
from .xtf import Ping, iter_pings, read_file_header, waterfall

_GEOD = Geod(ellps="WGS84")

#: Matches the detector's training tile size. Not a free parameter.
TILE = 640

#: A trailing slice shorter than this is dropped rather than scored. A very
#: short strip is mostly padding, and padding is what `dropout` flags -- so
#: scoring it produces warnings about the tiler rather than about the seabed.
MIN_ROWS = 64


def _offsets(extent: int, tile: int) -> list[int]:
    """Tile start positions covering `extent`, every tile exactly `tile` long.

    Used for BOTH axes, because the remainder problem is the same in each. A
    2048 px swath is three 640 px tiles plus 128 px, and 1,400 pings are two
    slices plus 120 rows. Shipping the remainder as a thin strip means the
    detector letterboxes it -- 5:1 across-track, and it loses exactly the
    detail a small object lives in. Dropping the remainder instead means
    silently discarding the end of a survey line.

    So the last tile is pulled back to end flush with the data. It overlaps its
    neighbour, which is the price, and `nadir_col` is derived from the offset so
    the geometry stays correct either way.

    Consequence worth knowing: an object sitting in an overlap can be reported
    from two tiles, as two detections with two ids and nearly equal positions.
    Suppressing that needs NMS in survey coordinates rather than frame
    coordinates, which is a real piece of work and not done here -- so a
    reviewer may see the same object twice near a tile seam.
    """
    if extent <= tile:
        return [0]
    starts = list(range(0, extent - tile + 1, tile))
    if starts[-1] + tile < extent:
        starts.append(extent - tile)
    return starts


def _along_track_res_m(pings: list[Ping]) -> float | None:
    """Metres of seabed per image ROW, measured from the navigation itself.

    The alternative is asking the operator for vessel speed, which they may not
    know and which changes through a turn. Consecutive ping positions already
    carry it: the geodesic distance between them IS the row spacing. The median
    is used rather than the mean because a single bad fix in a 640-ping slice
    would otherwise stretch the whole tile.

    Returns None when there is nothing to measure, which leaves along-track
    offsets switched off rather than guessed -- `geotag_pixel` already treats a
    missing row scale as "position this frame, not this pixel".
    """
    steps = []
    for a, b in zip(pings, pings[1:]):
        try:
            _, _, d = _GEOD.inv(a.longitude, a.latitude, b.longitude, b.latitude)
        except Exception:
            continue
        if math.isfinite(d) and 0.0 < d < 50.0:   # 50 m between pings is a bad fix
            steps.append(d)
    if not steps:
        return None
    steps.sort()
    return steps[len(steps) // 2]


def _meta_for_tile(
    ping: Ping,
    *,
    survey_id: str,
    frame_id: str,
    image_width: int,
    x_offset: int,
    nadir_row: float,
    along_track_res_m: float | None,
) -> dict[str, Any]:
    """Survey metadata for one tile, in the shape `detect()` reads.

    `nadir_col` is the waterfall's centre minus this tile's left edge, so a
    tile cut from the starboard end reports a nadir far to its left -- which is
    the truth, and what makes its across-track distances come out large.
    """
    chan = ping.channels[0]
    return {
        "survey_id": survey_id,
        "frame_id": frame_id,
        "latitude": ping.latitude,
        "longitude": ping.longitude,
        "heading_deg": ping.heading_deg,
        "altitude_m": ping.altitude_m,
        "layback_m": ping.layback_m,
        "nadir_col": image_width / 2.0 - x_offset,
        "range_resolution_m": chan.slant_range_m / chan.num_samples,
        "along_track_res_m": along_track_res_m,
        "nadir_row": nadir_row,
    }


@dataclass
class SurveyFrame:
    """One tile, ready to be scored or stored. Yielded by `iter_survey_frames`.

    Split out from `detect_survey` because a consumer that keeps its own
    per-frame records -- a web backend building a survey table, say -- needs the
    tiles and their geometry WITHOUT paying for inference twice: once here and
    again when its own pipeline walks those records. Same tiling code either
    way, which is the point.
    """

    frame_id: str
    image_path: Path
    #: Survey metadata in the shape `detect()` reads, ready to pass straight in.
    meta: dict[str, Any]
    #: Where the towfish was for this frame, or None if the pings covering it
    #: carried no usable navigation.
    position: FramePosition | None
    ping_offset: int


def _iter_tiles(
    pings: list[Ping],
    out_dir: Path,
    survey_id: str,
    tile: int,
    step: float | None,
    warnings: list[str],
) -> Iterator[SurveyFrame]:
    """Cut the pings into tiles, write each one, and yield it with its geometry."""
    import cv2
    import numpy as np

    for r0 in _offsets(len(pings), tile):
        chunk = pings[r0:r0 + tile]
        if len(chunk) < MIN_ROWS:
            continue
        try:
            wf = waterfall(chunk)
        except Exception as exc:
            warnings.append(
                "pings %d-%d could not be assembled into an image (%s); skipped"
                % (r0, r0 + len(chunk) - 1, type(exc).__name__)
            )
            continue
        if wf is None or getattr(wf, "size", 0) == 0:
            continue

        width = wf.shape[1]
        mid = len(chunk) // 2
        fix_ping = chunk[mid] if chunk[mid].has_geometry else next(
            (p for p in chunk if p.has_geometry), None
        )
        position = (
            FramePosition(
                latitude=fix_ping.latitude,
                longitude=fix_ping.longitude,
                heading_deg=fix_ping.heading_deg,
                timestamp=fix_ping.time or None,
            )
            if fix_ping is not None
            else None
        )

        for c0 in _offsets(width, tile):
            crop = np.ascontiguousarray(wf[:, c0:c0 + tile])
            if crop.shape[1] < MIN_ROWS:
                continue
            frame_id = "%s__p%06d__x%05d" % (survey_id, r0, c0)
            image_path = out_dir / (frame_id + ".png")
            if not cv2.imwrite(str(image_path), crop):
                warnings.append("could not write " + image_path.name + "; frame skipped")
                continue

            if fix_ping is None:
                meta: dict[str, Any] = {"survey_id": survey_id, "frame_id": frame_id}
            else:
                meta = _meta_for_tile(
                    fix_ping,
                    survey_id=survey_id,
                    frame_id=frame_id,
                    image_width=width,
                    x_offset=c0,
                    nadir_row=float(mid),
                    along_track_res_m=step,
                )

            yield SurveyFrame(
                frame_id=frame_id,
                image_path=image_path,
                meta=meta,
                position=position,
                ping_offset=r0,
            )


def iter_survey_frames(
    xtf_path: str | Path,
    out_dir: str | Path,
    survey_id: str | None = None,
    tile: int = TILE,
    max_pings: int | None = None,
) -> Iterator[SurveyFrame]:
    """Tile a sonar file into frames WITHOUT scoring them.

    For a consumer that stores frames first and runs detection through its own
    pipeline afterwards. `detect_survey` is the same walk with `detect()` applied
    to each frame, so neither can drift from the other.

    Raises whatever the reader raises on an unusable file -- unlike
    `detect_survey`, which swallows it into a warning. A caller building
    database rows wants to know the file was bad before it commits any.
    """
    xtf_path = Path(xtf_path)
    out_dir = Path(out_dir)
    survey_id = survey_id or xtf_path.stem
    header = read_file_header(xtf_path)
    pings = list(iter_pings(xtf_path, header=header, with_samples=True, limit=max_pings))
    if not pings:
        return
    step = _along_track_res_m([p for p in pings if p.has_geometry] or pings)
    out_dir.mkdir(parents=True, exist_ok=True)
    yield from _iter_tiles(pings, out_dir, survey_id, tile, step, [])


def detect_survey(
    xtf_path: str | Path,
    out_dir: str | Path,
    survey_id: str | None = None,
    tile: int = TILE,
    max_pings: int | None = None,
    settings: Settings = SETTINGS,
) -> dict[str, Any]:
    """Read a sonar file, cut it into frames, and score every frame.

    Args:
        xtf_path: a .xtf side-scan file.
        out_dir:  where the frame images are written. Created if absent.
        survey_id: defaults to the file's stem.
        tile: frame size in pixels. Leave at 640 unless the model changed.
        max_pings: stop after this many pings. Useful for a quick look at a
            200 MB line without reading all of it.
        settings: inference settings override.

    Returns a dict:
        survey_id, source, sonar, pings_read, pings_without_geometry,
        frames_written, along_track_res_m, frames (a list of payloads, each one
        matching contracts/ai-output.schema.json), warnings (survey-level).

    Only `frames[i]` is contract-governed. The envelope around it is this
    function's own shape, not a contract change, and it is here because "how
    much of this line could actually be positioned" is a survey-level question
    that no single frame can answer.

    Never raises for a file it cannot use: an unreadable or non-XTF file comes
    back as an empty frame list with the reason in `warnings`, the same way
    `detect()` handles a frame it cannot read.
    """
    import cv2
    import numpy as np

    xtf_path = Path(xtf_path)
    out_dir = Path(out_dir)
    survey_id = survey_id or xtf_path.stem
    out: dict[str, Any] = {
        "survey_id": survey_id,
        "source": xtf_path.name,
        "sonar": None,
        "pings_read": 0,
        "pings_without_geometry": 0,
        "frames_written": 0,
        "along_track_res_m": None,
        "frames": [],
        "warnings": [],
    }

    try:
        header = read_file_header(xtf_path)
        out["sonar"] = header.sonar_name
        pings = list(iter_pings(xtf_path, header=header, with_samples=True, limit=max_pings))
    except Exception as exc:
        out["warnings"].append(
            "could not read " + xtf_path.name + " as XTF (" + type(exc).__name__
            + "); no frames produced"
        )
        return out

    out["pings_read"] = len(pings)
    if not pings:
        out["warnings"].append("no sonar pings found in " + xtf_path.name)
        return out

    usable = [p for p in pings if p.has_geometry]
    out["pings_without_geometry"] = len(pings) - len(usable)
    if out["pings_without_geometry"]:
        # Worth saying out loud: these frames still get scored, they just come
        # back without coordinates. Silence here reads as "the model found
        # nothing there", which is a different and much worse claim.
        out["warnings"].append(
            "%d of %d pings lack the altitude or range needed for a position; "
            "frames covering them are scored but not placed"
            % (out["pings_without_geometry"], len(pings))
        )

    step = _along_track_res_m(usable or pings)
    out["along_track_res_m"] = round(step, 4) if step else None

    out_dir.mkdir(parents=True, exist_ok=True)

    for frame in _iter_tiles(pings, out_dir, survey_id, tile, step, out["warnings"]):
        out["frames_written"] += 1
        payload = detect(frame.image_path, frame.meta, settings)

        # The frame's OWN position, which is not the same thing as any
        # detection's. This is what draws the survey track, and it is known
        # even for a tile the detector found nothing on -- so the track is
        # continuous rather than existing only where there happened to be
        # debris.
        if frame.position is not None:
            payload["frame_position"] = frame.position.to_dict()

        out["frames"].append(payload)

    placed = sum(
        1 for f in out["frames"] for d in f["detections"] if d.get("latitude") is not None
    )
    total = sum(len(f["detections"]) for f in out["frames"])
    if total and not placed:
        # The failure this whole module exists to prevent, so it is stated
        # rather than left to be inferred from a map with no pins on it.
        out["warnings"].append(
            "%d detections were found but none could be positioned; check that the "
            "file carries altitude and a navigation fix" % total
        )
    return out
