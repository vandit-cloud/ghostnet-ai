"""Turn a raw sonar file into detections: XTF/SDF -> waterfall -> tiles -> detect().

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

Tiles overlap
-------------
Only when Settings.tile_overlap > 0 (off by default; see config.py for the
measurement). Then a seam never cuts an object
with no tile seeing the whole of it; across-track, one tile is centred on
nadir so the water column never sits on a tile border (see `_across_offsets`
for why that matters). The duplicates overlap creates are merged in survey
coordinates by `ghostnet.merge`. Measured in ai/experiments/tile-overlap.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyproj import Geod

from .config import SETTINGS, Settings
from .contract import FramePosition
from .infer import detect
from .merge import frame_id_for, merge_survey_frames
from . import sdf
from .xtf import Ping, iter_pings, read_file_header, waterfall

_GEOD = Geod(ellps="WGS84")

#: Matches the detector's training tile size. Not a free parameter.
TILE = 640

#: A trailing slice shorter than this is dropped rather than scored. A very
#: short strip is mostly padding, and padding is what `dropout` flags -- so
#: scoring it produces warnings about the tiler rather than about the seabed.
MIN_ROWS = 64


def _stride(tile: int, overlap: float) -> int:
    """Pixels between tile starts for an overlap fraction in [0, 0.9].

    Clamped rather than validated: an overlap of 1.0 would make the stride 0
    and the tiler loop forever, and a negative one would leave gaps -- neither
    is a setting anyone means, and a survey run is the wrong place to raise.
    """
    overlap = min(max(float(overlap or 0.0), 0.0), 0.9)
    return max(1, int(round(tile * (1.0 - overlap))))


def _offsets(extent: int, tile: int, overlap: float = 0.0) -> list[int]:
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

    `overlap` is the fraction of a tile shared with its neighbour, and it is
    what stops a seam from cutting an object in half with nobody seeing the
    whole of it. At 0.25 (stride 480) anything up to 160 px across appears
    WHOLE in at least one tile. The duplicates that creates -- one object
    reported from two tiles -- are merged afterwards in survey coordinates by
    `ghostnet.merge`, which is what makes the overlap affordable.

    With overlap, the tiles are spread EVENLY between the two flush ends
    instead of stepping by the stride and pulling only the last one back:
    same tile count, but every seam gets the same (>= requested) overlap
    rather than one skinny seam and one fat one. At 0 the old tiling is
    reproduced exactly, so GHOSTNET_TILE_OVERLAP=0 is a true rollback.
    """
    if extent <= tile:
        return [0]
    if not overlap or overlap <= 0:
        starts = list(range(0, extent - tile + 1, tile))
        if starts[-1] + tile < extent:
            starts.append(extent - tile)
        return starts
    return _spread(0, extent - tile, _stride(tile, overlap))


def _spread(first: int, last: int, stride: int) -> list[int]:
    """Starts from `first` to `last` inclusive, evenly spaced, no gap wider than `stride`."""
    if last <= first:
        return [first]
    n = math.ceil((last - first) / stride) + 1
    return [first + round(i * (last - first) / (n - 1)) for i in range(n)]


def _across_offsets(
    width: int,
    tile: int,
    overlap: float,
    water_column_px: float | None = None,
) -> list[int]:
    """Across-track tile starts: one tile centred on nadir, each side tiled
    separately, and the water column kept OFF every other tile's border.

    Why across-track is not just `_offsets` again
    ---------------------------------------------
    The first overlap run on the demo line (6,039 pings, 2048 px) tiled both
    axes with plain 25 % overlap, at x = 0/480/960/1408. Nadir sits at 1024, so
    the dark water-column band down the middle of a waterfall landed 64 px from
    the left border of one tile and 96 px from the right border of another --
    and the detector reported it, twice, as 147-165 px by full-height
    `debris` (calibrated 0.39 and 0.41). Two of the run's three detections were
    that band. The old tiling never showed it: nadir sat at column 384 of a
    single tile, well away from any border, and nothing fired. A dark band
    flush with a border is the same image cue as the `is_edge_sliver`
    artefact, just too wide for that rule's 8 % thickness limit.

    So the centre tile is placed on nadir, where the band is mid-tile as it
    always was, and the port and starboard sides are tiled independently with
    their inner ends stopping short of the water column. Nothing lives in the
    water column, so a seam beside it cuts nothing; the overlap that matters is
    over seabed, and each side still gets >= the requested overlap with the
    centre tile and between its own tiles.

    `water_column_px` is the band's half-width (altitude / range resolution,
    ~80 px on the demo line); unknown altitude falls back to a tenth of a side.

    What it costs: on a 2048 px swath this is 5 tiles across at 25 % (was 4 at
    0 %), and still 5 at 50 % -- each side is short enough that two tiles
    already overlap by 368 px. The water column also caps the overlap beside it -- the centre tile
    and its neighbour share 208 px there on the demo line, which meets 25 %
    (160 px) but not 50 % (320 px). An object would have to sit within ~110 px
    of nadir AND be over 208 px across to be cut, and the strip next to the
    water column is the least reliable seabed on the line anyway.
    """
    if not overlap or overlap <= 0 or width <= tile:
        return _offsets(width, tile, 0.0)
    stride = _stride(tile, overlap)
    nadir = width / 2.0
    c = int(round(min(max(nadir - tile / 2.0, 0), width - tile)))
    margin = tile * 0.05            # keep a band edge off the border, not merely outside it
    if not water_column_px or water_column_px <= 0:
        # Towing height is conventionally 10-20 % of range, so a tenth of a
        # side's width is a conservative guess at the band, and a too-wide
        # guess only costs a little seabed overlap beside nadir.
        water_column_px = 0.10 * nadir
    port_end = nadir - water_column_px - margin
    stbd_start = nadir + water_column_px + margin
    # The side tiles must still reach the centre tile with seabed to spare,
    # and must not end beyond it -- clamp both ways.
    port_end = int(round(min(max(port_end, c + 1), c + tile)))
    stbd_start = int(round(min(max(stbd_start, c), c + tile - 1)))

    starts = {c}
    if c > 0:
        starts.update(_spread(0, max(port_end - tile, 0), stride))
    if c + tile < width:
        starts.update(_spread(min(stbd_start, width - tile), width - tile, stride))
    return sorted(starts)


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


@dataclass
class _SonarRead:
    """What either reader hands the tiler: pings split into independent segments."""

    sonar: str | None
    segments: list[list[Ping]]
    pings_read: int
    pings_without_geometry: int
    #: Set by a reader that resampled to a known row spacing; None to measure it.
    along_track_res_m: float | None
    warnings: list[str]


def _read_sonar(path: Path, max_pings: int | None) -> _SonarRead:
    """Dispatch on extension. Raises on a file the reader cannot use.

    An .xtf is one segment of native pings. An .sdf (Klein 5000 V2) comes back
    as several segments, split where range changed, already resampled to square
    pixels and cleaned of settings-change transients -- see `ghostnet.sdf`.
    """
    if path.suffix.lower() == ".sdf":
        r = sdf.read_survey(path, max_pings=max_pings)
        return _SonarRead(r.sonar_name, r.segments, r.pings_read, r.pings_without_geometry,
                          r.along_track_res_m, list(r.warnings))
    header = read_file_header(path)
    pings = list(iter_pings(path, header=header, with_samples=True, limit=max_pings))
    return _SonarRead(header.sonar_name, [pings] if pings else [], len(pings),
                      sum(1 for p in pings if not p.has_geometry), None, [])


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
    #: This tile's top-left in SURVEY pixels: first ping row in the file, and
    #: first column of the assembled waterfall. With overlapping tiles these
    #: are what put two sightings of one object into the same coordinates so
    #: `ghostnet.merge` can tell they are one object.
    ping_offset: int
    col_offset: int = 0


def _iter_tiles(
    pings: list[Ping],
    out_dir: Path,
    survey_id: str,
    tile: int,
    step: float | None,
    warnings: list[str],
    ping_base: int = 0,
    overlap: float = 0.0,
) -> Iterator[SurveyFrame]:
    """Cut the pings into tiles, write each one, and yield it with its geometry.

    `ping_base` is this segment's first row within the whole file, so frame ids
    stay unique when a file is tiled as several segments.
    """
    import cv2
    import numpy as np

    for r0 in _offsets(len(pings), tile, overlap):
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

        water_px = None
        if fix_ping is not None:
            chan = fix_ping.channels[0]
            res = chan.slant_range_m / chan.num_samples if chan.num_samples else 0
            if res > 0 and fix_ping.altitude_m and fix_ping.altitude_m > 0:
                water_px = fix_ping.altitude_m / res
        for c0 in _across_offsets(width, tile, overlap, water_px):
            crop = np.ascontiguousarray(wf[:, c0:c0 + tile])
            if crop.shape[1] < MIN_ROWS:
                continue
            frame_id = frame_id_for(survey_id, ping_base + r0, c0)
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
                ping_offset=ping_base + r0,
                col_offset=c0,
            )


def iter_survey_frames(
    xtf_path: str | Path,
    out_dir: str | Path,
    survey_id: str | None = None,
    tile: int = TILE,
    max_pings: int | None = None,
    overlap: float | None = None,
) -> Iterator[SurveyFrame]:
    """Tile a sonar file into frames WITHOUT scoring them.

    `overlap` defaults to `SETTINGS.tile_overlap`. A consumer that scores these
    frames itself must merge the resulting seam duplicates itself too; see
    `ghostnet.merge` (the web backend does it as it persists).

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
    overlap = SETTINGS.tile_overlap if overlap is None else overlap
    read = _read_sonar(xtf_path, max_pings)
    if not read.segments:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    base = 0
    for pings in read.segments:
        step = read.along_track_res_m or _along_track_res_m([p for p in pings if p.has_geometry] or pings)
        yield from _iter_tiles(pings, out_dir, survey_id, tile, step, [], ping_base=base, overlap=overlap)
        base += len(pings)


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
        xtf_path: a .xtf side-scan file, or a Klein 5000 V2 .sdf.
        out_dir:  where the frame images are written. Created if absent.
        survey_id: defaults to the file's stem.
        tile: frame size in pixels. Leave at 640 unless the model changed.
        max_pings: stop after this many pings. Useful for a quick look at a
            200 MB line without reading all of it.
        settings: inference settings override.

    Returns a dict:
        survey_id, source, sonar, pings_read, pings_without_geometry,
        frames_written, along_track_res_m, tile_overlap,
        seam_duplicates_merged, frames (a list of payloads, each one matching
        contracts/ai-output.schema.json), warnings (survey-level).

    Tiles overlap by `settings.tile_overlap`, and an object seen from two
    tiles is reported ONCE: `ghostnet.merge` keeps the best sighting and
    names the others in its notes, after every frame has been scored.

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
        "tile_overlap": settings.tile_overlap,
        "seam_duplicates_merged": 0,
        "frames": [],
        "warnings": [],
    }

    fmt = "SDF" if xtf_path.suffix.lower() == ".sdf" else "XTF"
    try:
        read = _read_sonar(xtf_path, max_pings)
    except Exception as exc:
        out["warnings"].append(
            "could not read " + xtf_path.name + " as " + fmt + " (" + type(exc).__name__
            + "); no frames produced"
        )
        return out

    out["sonar"] = read.sonar
    out["pings_read"] = read.pings_read
    out["warnings"].extend(read.warnings)
    if not read.segments:
        out["warnings"].append("no sonar pings found in " + xtf_path.name)
        return out

    out["pings_without_geometry"] = read.pings_without_geometry
    if out["pings_without_geometry"]:
        # Worth saying out loud: these frames still get scored, they just come
        # back without coordinates. Silence here reads as "the model found
        # nothing there", which is a different and much worse claim.
        out["warnings"].append(
            "%d of %d pings lack the altitude or range needed for a position; "
            "frames covering them are scored but not placed"
            % (out["pings_without_geometry"], read.pings_read)
        )

    steps = [
        read.along_track_res_m or _along_track_res_m([p for p in pings if p.has_geometry] or pings)
        for pings in read.segments
    ]
    known = [s for s in steps if s]
    out["along_track_res_m"] = round(known[0], 4) if known else None

    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list = []
    base = 0
    for pings, step in zip(read.segments, steps):
        frames.append(_iter_tiles(pings, out_dir, survey_id, tile, step, out["warnings"],
                                  ping_base=base, overlap=settings.tile_overlap))
        base += len(pings)

    offsets: list[tuple[int, int]] = []
    for frame in itertools.chain.from_iterable(frames):
        out["frames_written"] += 1
        offsets.append((frame.ping_offset, frame.col_offset))
        payload = detect(frame.image_path, frame.meta, settings)

        # The frame's OWN position, which is not the same thing as any
        # detection's. This is what draws the survey track, and it is known
        # even for a tile the detector found nothing on -- so the track is
        # continuous rather than existing only where there happened to be
        # debris.
        if frame.position is not None:
            payload["frame_position"] = frame.position.to_dict()

        out["frames"].append(payload)

    # Overlapping tiles see one object twice; say how many were folded
    # together, because a count that drops between two runs with no
    # explanation looks like lost recall.
    if settings.seam_merge and settings.tile_overlap > 0:
        merged = merge_survey_frames(out["frames"], offsets, settings)
        out["seam_duplicates_merged"] = merged
        if merged:
            out["warnings"].append(
                "%d duplicate detection(s) of the same object in overlapping tiles were "
                "merged into the highest-scoring sighting; each survivor's notes name "
                "what it absorbed" % merged
            )

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
