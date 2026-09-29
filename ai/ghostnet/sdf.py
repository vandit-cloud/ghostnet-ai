"""Read Klein SonarPro (.sdf) side-scan files from a System 5000 V2.

    from ghostnet.sdf import read_file_header, read_survey

    hdr = read_file_header(path)
    r = read_survey(path)            # r.segments: lists of xtf.Ping rows

`read_survey` returns the same `Ping` rows the XTF reader yields, so
`survey.py` tiles an .sdf with exactly the code it tiles an .xtf with.

Written against Klein's own "SonarPro SDF File Format Specification" (sections
3.1 and 3.2.9, pageVersion 5004) and checked against a real towed survey: a
System 5000 V2 line recorded 30 Jul 2019, 50 one-minute files. Four things
the bytes decide that are easy to get wrong:

1. EACH CHANNEL IS ITS OWN VECTOR. The page header is followed by vectors of
   `[u16 count][count x u16]`, one per channel: chan1..chan10, then bathy and
   raw I/Q. Reading them as 5 blocks of `[u32 count][2 x count]` also looks
   like a sonar image, because two neighbouring beams land side by side.
   But then "port" and "starboard" are often two beams from the SAME side,
   and the image shows every feature mirrored across nadir. That mirroring
   is exactly what the first decode of this survey produced. With the right
   layout, channels 1-5 correlate with each other (0.2-0.4), 6-10 with each
   other, and the two groups at 0.02.

2. ONE PING IS FIVE ROWS. The 5000 V2 is a multibeam side-scan: channels 1-5
   are five port beams stacked along-track, 6-10 the starboard ones, and
   beams 1/6 are the most forward (spec, Table 2 note 3). `beamsToDisplay`
   (low 5 bits) names the beams that tile this ping's along-track advance at
   the current speed; the rest overlap the next ping. So each ping gives
   1-5 rows, ordered aft to fore.

3. SPEED IS m/s AND THE FISH POSITION IS LAID BACK ALREADY. Header field 34
   `speed` is metres per second (checked: 141 m of GPS track in a 60 s file at
   2.35), not knots. The towfish position is `laybackFishLat/Lon` (fields
   71/72). `fishLat/Lon` read zero in the real file. So rows carry
   `layback_m = 0`, or the layback would be applied twice.

4. SETTINGS CHANGES WRITE BRIGHT PINGS. When the operator changes range, beams,
   resolution or waveform, the next few pings are transients and the gain
   steps. Tiled as-is they are full-width bright rows, and the detector boxed
   29 of 39 alarms on them in the first evaluation. So a file is split into
   segments where the geometry changes, and inside a segment pings around a
   mode change, and pings whose mean return is a local outlier, are dropped.
   Each mode run is then scaled to the segment's median level.

Pixels are resampled to squares of `TARGET_RES_M` on both axes. Across-track
that means averaging pairs of 3.46 cm samples. Along-track the 5000 writes
rows 2-40 cm apart depending on range, speed and beam count, and tiling
native rows would stretch every object by that ratio, a shape the detector
never saw in training.

Only pageVersion 5004 is accepted. The other 5000-series layouts differ after
the side-scan vectors, and nothing here has been checked against them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

import numpy as np

from .xtf import Channel, Ping

PAGE_MARKER = 0xFFFFFFFF
SUPPORTED_PAGE_VERSIONS = {5004}
N_CHANNELS = 10                  # side-scan vectors: 1-5 port, 6-10 starboard
N_BEAMS = 5

#: Output pixel size on both axes. Twice the 3.46 cm sample spacing the 5000 V2
#: records at every range in the survey this was built against (range / samples
#: is constant from 50 m to 200 m), so across-track is a clean 2:1 average.
TARGET_RES_M = 0.069

#: errorFlags bits that mean the position in this ping cannot be trusted.
GPS_ERROR_BITS = (1 << 1) | (1 << 8)          # GPS data error, no lat/lon sentence

#: Header fields whose change alters the image width -> start a new segment.
GEOMETRY_WORDS = (5, 8)                       # numSamples, range
#: Header fields whose change brightens the next pings -> guard and relevel.
MODE_WORDS = (6, 11, 12)                      # beamsToDisplay, resMode, txWaveform
GUARD_PINGS = 3
SPIKE_MAD = 6.0
SPIKE_WINDOW = 21
#: Lines further apart than this are not interpolated between. The widest real
#: line pitch in the survey is ~0.45 m (200 m range, 2 beams); a larger gap is
#: pings that were dropped, and blending across it would invent seabed.
MAX_BLEND_M = 1.0


@dataclass(frozen=True)
class SdfHeader:
    sonar_name: str
    page_version: int
    num_samples: int
    range_m: int


@dataclass
class SdfPage:
    """One ping, decoded. `port`/`stbd` are (beams, samples), aft to fore, near-first."""

    ping_number: int
    time: datetime
    latitude: float | None
    longitude: float | None
    heading_deg: float
    altitude_m: float
    speed_mps: float
    range_m: int
    num_samples: int
    beams: tuple[int, ...]
    mode: tuple[int, ...]
    error_flags: int
    port: np.ndarray
    stbd: np.ndarray

    @property
    def geometry(self) -> tuple[int, int]:
        return (self.num_samples, self.range_m)


@dataclass
class SdfRow(Ping):
    """A resampled waterfall row. A Ping, plus whether its position is a real fix.

    The 2022 factory recording from the same maker carried lat/lon 0 with
    errorFlags 769. A zero position still parses as a number, so without this
    flag it would put a frame at 0 N 0 E rather than leave it unplaced.
    """

    has_fix: bool = True

    @property
    def has_geometry(self) -> bool:
        return self.has_fix and super().has_geometry


@dataclass
class SdfRead:
    sonar_name: str
    segments: list[list[SdfRow]]
    pings_read: int
    pings_dropped: int
    pings_without_geometry: int
    along_track_res_m: float
    warnings: list[str] = field(default_factory=list)


# --- low level ---------------------------------------------------------------

def _u32(page: bytes, word: int) -> int:
    return int.from_bytes(page[4 * word:4 * word + 4], "little")


def _f32(page: bytes, word: int) -> float:
    return float(np.frombuffer(page, "<f4", 1, 4 * word)[0])


def _f64(page: bytes, byte: int) -> float:
    return float(np.frombuffer(page, "<f8", 1, byte)[0])


def iter_raw_pages(path: str | Path, limit: int | None = None) -> Iterator[bytes]:
    """Yield each page's bytes, marker included, stopping at the first lost sync."""
    seen = 0
    with open(path, "rb") as fh:
        while limit is None or seen < limit:
            head = fh.read(8)
            if len(head) < 8:
                return
            marker, n = int.from_bytes(head[:4], "little"), int.from_bytes(head[4:], "little")
            if marker != PAGE_MARKER or n < 512:
                return
            body = fh.read(n - 4)
            if len(body) < n - 4:
                return
            seen += 1
            yield head + body


def read_file_header(path: str | Path) -> SdfHeader:
    """Identify the file from its first page. Raises ValueError for anything else."""
    page = next(iter_raw_pages(path, limit=1), None)
    if page is None:
        raise ValueError(f"{Path(path).name} does not start with an SDF page marker")
    version = _u32(page, 2)
    if version not in SUPPORTED_PAGE_VERSIONS:
        raise ValueError(
            f"SDF pageVersion {version} is not supported; only "
            f"{sorted(SUPPORTED_PAGE_VERSIONS)} (Klein System 5000 V2) has been checked"
        )
    return SdfHeader(
        sonar_name="Klein System 5000 V2",
        page_version=version,
        num_samples=_u32(page, 5),
        range_m=_u32(page, 8),
    )


def _vectors(page: bytes, header_size: int, count: int) -> list[np.ndarray] | None:
    """The first `count` `[u16 n][n x u16]` vectors after the header."""
    off = 4 + header_size
    out = []
    for _ in range(count):
        if off + 2 > len(page):
            return None
        n = int.from_bytes(page[off:off + 2], "little")
        end = off + 2 + 2 * n
        if end > len(page):
            return None
        out.append(np.frombuffer(page, "<u2", n, off + 2))
        off = end
    return out


def _position(page: bytes, error_flags: int) -> tuple[float | None, float | None]:
    """Towfish lat/lon in degrees: laid-back fish, else ship, else None."""
    if error_flags & GPS_ERROR_BITS:
        return None, None
    for lat_b, lon_b in ((300, 308), (164, 172), (148, 156)):   # layback fish, fish, ship
        lat, lon = _f64(page, lat_b), _f64(page, lon_b)
        if lat != 0.0 and lon != 0.0 and math.isfinite(lat) and math.isfinite(lon):
            lat_d, lon_d = math.degrees(lat), math.degrees(lon)
            if -90.0 <= lat_d <= 90.0 and -180.0 <= lon_d <= 180.0:
                return lat_d, lon_d
    return None, None


def parse_page(page: bytes) -> SdfPage | None:
    """Decode one page, or None when its side-scan vectors are malformed."""
    if _u32(page, 2) not in SUPPORTED_PAGE_VERSIONS:
        return None
    ns = _u32(page, 5)
    vec = _vectors(page, _u32(page, 46), N_CHANNELS)      # field 42 headerSize
    if vec is None or any(len(v) != ns for v in vec):
        return None
    mask = _u32(page, 6) & 0x1F
    beams = tuple(b for b in range(N_BEAMS) if mask >> b & 1) or tuple(range(N_BEAMS))
    aft_first = sorted(beams, reverse=True)                 # beam 1 is fore: reverse for time order
    port = np.stack([vec[b] for b in aft_first])
    stbd = np.stack([vec[N_BEAMS + b] for b in aft_first])
    err = _u32(page, 7)
    lat, lon = _position(page, err)
    y, mo, d, h, mi, s, hs = (_u32(page, w) for w in range(18, 25))
    try:
        t = datetime(y, mo, d, h, mi, s) + timedelta(seconds=hs / 100.0)
    except ValueError:
        t = datetime(1970, 1, 1)
    return SdfPage(
        ping_number=_u32(page, 4), time=t, latitude=lat, longitude=lon,
        heading_deg=_f32(page, 28), altitude_m=_f32(page, 32), speed_mps=_f32(page, 34),
        range_m=_u32(page, 8), num_samples=ns, beams=beams,
        mode=tuple(_u32(page, w) for w in MODE_WORDS), error_flags=err,
        port=port, stbd=stbd,
    )


# --- cleaning: segments, transients, levels ----------------------------------

def _split_geometry(pages: list[SdfPage]) -> list[list[SdfPage]]:
    segs: list[list[SdfPage]] = []
    for p in pages:
        if not segs or segs[-1][-1].geometry != p.geometry:
            segs.append([])
        segs[-1].append(p)
    return segs


def _keep_mask(seg: list[SdfPage]) -> np.ndarray:
    """False for transient pings: local brightness outliers and mode-change guards."""
    mean = np.array([np.concatenate([p.port.ravel(), p.stbd.ravel()]).mean() for p in seg])
    half = SPIKE_WINDOW // 2                   # rolling median, edges padded by repetition
    padded = np.pad(mean, half, mode="edge")
    local = np.median(np.lib.stride_tricks.sliding_window_view(padded, SPIKE_WINDOW), axis=1)
    res = mean - local
    spike = np.abs(res) / (np.median(np.abs(res)) + 1e-9) > SPIKE_MAD
    keep = ~np.convolve(spike, np.ones(3), "same").astype(bool)       # the spike and its neighbours
    for i in range(1, len(seg)):
        if seg[i].mode != seg[i - 1].mode:
            keep[max(0, i - GUARD_PINGS):i + GUARD_PINGS] = False
    return keep


def _mode_runs(seg: list[SdfPage]) -> list[tuple[int, int]]:
    cuts = [0] + [i for i in range(1, len(seg)) if seg[i].mode != seg[i - 1].mode] + [len(seg)]
    return list(zip(cuts[:-1], cuts[1:]))


# --- resampling to square pixels ------------------------------------------------

def _decimate(x: np.ndarray, f: int) -> np.ndarray:
    n = x.shape[-1] // f * f
    return x[..., :n].reshape(*x.shape[:-1], n // f, f).mean(-1)


def _segment_rows(seg: list[SdfPage], keep: np.ndarray, res_m: float) -> list[SdfRow]:
    """Resample one geometry segment to rows `res_m` apart, `res_m` wide."""
    samp_m = seg[0].range_m / seg[0].num_samples
    f = max(1, round(res_m / samp_m))

    # Level each mode run to the segment's median, over kept pings only.
    level = np.ones(len(seg))
    ref = []
    for a, b in _mode_runs(seg):
        vals = [np.median(np.concatenate([p.port.ravel(), p.stbd.ravel()])) for p, k in zip(seg[a:b], keep[a:b]) if k]
        if vals:
            level[a:b] = float(np.median(vals)); ref.append(level[a])
    target = float(np.median(ref)) if ref else 1.0

    # Along-track position of every kept beam-line, from speed x ping interval.
    secs = np.array([(p.time - seg[0].time).total_seconds() for p in seg])
    dt = np.diff(secs)
    dt_med = float(np.median(dt[dt > 0])) if (dt > 0).any() else 0.0
    lines, where, owner = [], [], []
    s = 0.0
    for i, p in enumerate(seg):
        step = (secs[i] - secs[i - 1]) if i and 0 < secs[i] - secs[i - 1] < 5 * dt_med else dt_med
        advance = max(p.speed_mps, 0.0) * step
        if i:
            s += advance
        if not keep[i]:
            continue
        n = len(p.beams)
        pitch = advance / n                                   # the active beams tile this ping's advance
        scale = target / level[i] if level[i] > 0 else 1.0
        for k in range(n):                                    # aft to fore
            port = _decimate(p.port[k].astype(np.float32), f) * scale
            stbd = _decimate(p.stbd[k].astype(np.float32), f) * scale
            lines.append((port, stbd)); where.append(s + (k - (n - 1) / 2) * pitch); owner.append(i)
    if len(lines) < 2 or where[-1] - where[0] <= 0:
        return []

    where_a = np.array(where)
    order = np.argsort(where_a, kind="stable")
    where_a = where_a[order]
    # A gap left by dropped pings is closed up, not filled: repeating the edge
    # line across it paints a streaked band the detector reads as structure.
    # Each row keeps its own interpolated position, so the track stays right;
    # only in-tile along-track offsets across the join are off by the gap.
    gaps = np.flatnonzero(np.diff(where_a) > MAX_BLEND_M)
    starts = np.r_[0, gaps + 1]
    ends = np.r_[gaps, len(where_a) - 1]
    grid: list[tuple[float, int]] = []            # (along-track position, last line of its run)
    for s0, e0 in zip(starts, ends):
        if where_a[e0] > where_a[s0]:
            grid.extend((float(y), int(e0)) for y in np.arange(where_a[s0], where_a[e0], res_m))
    rows: list[SdfRow] = []
    for y, run_end in grid:
        j = int(np.searchsorted(where_a, y, side="right")) - 1
        j = min(max(j, 0), run_end - 1)
        a, b = order[j], order[j + 1]
        span = where_a[j + 1] - where_a[j]
        w = min(max((y - where_a[j]) / span, 0.0), 1.0) if span > 0 else 0.0
        port = lines[a][0] * (1 - w) + lines[b][0] * w
        stbd = lines[a][1] * (1 - w) + lines[b][1] * w
        p = seg[owner[a]]
        q = seg[owner[b]]
        lat = lon = None
        if p.latitude is not None and q.latitude is not None:
            lat = p.latitude + (q.latitude - p.latitude) * w
            lon = p.longitude + (q.longitude - p.longitude) * w
        n2 = len(port)
        rows.append(SdfRow(
            ping_number=p.ping_number,
            time=p.time.isoformat(timespec="seconds"),
            latitude=lat if lat is not None else 0.0,
            longitude=lon if lon is not None else 0.0,
            heading_deg=p.heading_deg,
            altitude_m=p.altitude_m,
            depth_m=0.0,                       # the header's depth is a sensor voltage
            layback_m=0.0,                     # position is already the laid-back fish
            seconds_per_ping=res_m / p.speed_mps if p.speed_mps > 0 else 0.0,
            channels=[
                Channel(number=0, slant_range_m=float(p.range_m), num_samples=n2,
                        samples=_to_u16(port), bytes_per_sample=2, near_first=True),
                Channel(number=1, slant_range_m=float(p.range_m), num_samples=n2,
                        samples=_to_u16(stbd), bytes_per_sample=2, near_first=True),
            ],
            has_fix=lat is not None,
        ))
    return rows


def _to_u16(x: np.ndarray) -> bytes:
    return np.clip(np.rint(x), 0, 65535).astype("<u2").tobytes()


# --- public ---------------------------------------------------------------------

def read_survey(path: str | Path, max_pings: int | None = None, res_m: float = TARGET_RES_M) -> SdfRead:
    """Read, clean and resample a whole file. Raises ValueError for a non-SDF file."""
    header = read_file_header(path)
    pages, bad = [], 0
    for raw in iter_raw_pages(path, limit=max_pings):
        p = parse_page(raw)
        if p is None:
            bad += 1
        else:
            pages.append(p)
    warnings: list[str] = []
    if bad:
        warnings.append(f"{bad} SDF pages had malformed side-scan vectors and were skipped")
    if not pages:
        return SdfRead(header.sonar_name, [], bad, 0, 0, res_m, warnings)

    segments, dropped = [], 0
    geo_segments = _split_geometry(pages)
    for seg in geo_segments:
        keep = _keep_mask(seg)
        dropped += int((~keep).sum())
        rows = _segment_rows(seg, keep, res_m)
        if rows:
            segments.append(rows)
    if len(geo_segments) > 1:
        warnings.append(
            f"range or samples-per-ping changed {len(geo_segments) - 1} time(s); "
            f"the file was tiled as {len(geo_segments)} separate segments"
        )
    if dropped:
        warnings.append(
            f"{dropped} of {len(pages)} pings were dropped as settings-change transients"
        )
    no_fix = sum(1 for p in pages if p.latitude is None)
    if not any(p.speed_mps > 0 for p in pages):
        warnings.append("no ping carries a speed, so the along-track scale is unknown")
    return SdfRead(
        sonar_name=header.sonar_name,
        segments=segments,
        pings_read=len(pages) + bad,
        pings_dropped=dropped,
        pings_without_geometry=sum(1 for p in pages if p.latitude is None or p.altitude_m <= 0),
        along_track_res_m=res_m,
        warnings=warnings + ([f"{no_fix} of {len(pages)} pings carry no GPS fix"] if no_fix else []),
    )
