"""Tests for the Klein .sdf reader, against files written byte-for-byte here.

The real survey this reader was built on is private (see docs/DATA.md in the
training tree), so the fixture is a writer that follows the spec's page layout.
Every test pins one of the decisions documented in `ghostnet/sdf.py`, and the
first two pin the bug that decision replaced: reading pairs of channels as one
block, which drew every feature mirrored across nadir.
"""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet import sdf  # noqa: E402
from ghostnet.contract import validate  # noqa: E402
from ghostnet.config import Settings  # noqa: E402
from ghostnet.survey import detect_survey  # noqa: E402
from ghostnet.xtf import waterfall  # noqa: E402

NS = 400                       # samples per channel
RANGE = 14                     # m, so samples are 3.5 cm like the real unit
LAT, LON = 42.97, -70.64


def page(
    n: int,
    *,
    ns: int = NS,
    rng: int = RANGE,
    beams_mask: int = 0b11111,
    mode: tuple[int, int] = (0, 5),
    speed: float = 2.0,
    hz: float = 4.0,
    error_flags: int = 0,
    lat: float | None = LAT,
    lon: float | None = LON,
    chans: list[np.ndarray] | None = None,
    version: int = 5004,
) -> bytes:
    """One 5004 page: marker, 512-byte header, then 10 `[u16 n][n x u16]` side-scan vectors.

    Offsets are absolute within the page, as the spec numbers them: word w of
    the header (field w) sits at byte 4 * w, the marker being word 0.
    """
    h = bytearray(516)
    put = lambda word, fmt, v: struct.pack_into(fmt, h, 4 * word, v)
    put(0, "<I", 0xFFFFFFFF)
    put(2, "<I", version)
    put(4, "<I", n)
    put(5, "<I", ns)
    put(6, "<I", beams_mask)
    put(7, "<I", error_flags)
    put(8, "<I", rng)
    put(9, "<I", int(speed * 100))
    put(11, "<I", mode[0])
    put(12, "<I", mode[1])
    t = n / hz
    for w, v in zip(range(18, 25), (2019, 7, 30, 16, int(t // 60) % 60, int(t) % 60, int(t * 100) % 100)):
        put(w, "<I", v)
    put(28, "<f", 90.0)                    # heading: due east
    put(32, "<f", 5.0)                     # altitude
    put(34, "<f", speed)
    put(46, "<I", 512)                     # headerSize (field 42, after four doubles)
    d_lon = n * speed / hz / (111_320 * math.cos(math.radians(LAT)))
    if lat is not None:
        struct.pack_into("<d", h, 148, math.radians(lat))                 # ship
        struct.pack_into("<d", h, 156, math.radians(lon + d_lon))
        struct.pack_into("<d", h, 300, math.radians(lat))                 # laid-back fish, 5 m astern
        struct.pack_into("<d", h, 308, math.radians(lon + d_lon - 5 / 81_400))
    if chans is None:
        base = np.linspace(40, 10, ns).astype(np.uint16)
        base[:20] = 3                                                     # dark water column, near end
        chans = [base.copy() for _ in range(10)]
    body = b"".join(struct.pack("<H", len(c)) + c.astype("<u2").tobytes() for c in chans)
    body += struct.pack("<H", 0) * 4                                      # empty bathy vectors
    out = bytearray(h) + body
    struct.pack_into("<I", out, 4, len(out) - 4)                          # numberBytes
    return bytes(out)


def write(path: Path, pages: list[bytes]) -> Path:
    path.write_bytes(b"".join(pages))
    return path


def marked(port_col: int | None = None, stbd_col: int | None = None, beam: int | None = None) -> list[np.ndarray]:
    """Channels with a bright 10-sample target at `*_col` on beam `beam` (0-4) or all beams."""
    base = np.full(NS, 20, np.uint16)
    base[:20] = 3
    out = [base.copy() for _ in range(10)]
    for b in range(5):
        if beam is not None and b != beam:
            continue
        if port_col is not None:
            out[b][port_col:port_col + 10] = 2000
        if stbd_col is not None:
            out[5 + b][stbd_col:stbd_col + 10] = 2000
    return out


# --- identity ---------------------------------------------------------------

def test_rejects_a_file_that_is_not_sdf(tmp_path):
    p = tmp_path / "x.sdf"
    p.write_bytes(b"\x01\x02" * 400)
    with pytest.raises(ValueError):
        sdf.read_file_header(p)


def test_rejects_an_unchecked_page_version(tmp_path):
    p = write(tmp_path / "x.sdf", [page(0, version=5001)])
    with pytest.raises(ValueError, match="5001"):
        sdf.read_file_header(p)


# --- the layout: sides, beams, order -------------------------------------------

def test_a_port_target_appears_only_on_the_port_half(tmp_path):
    """The old block decode put beams 1 and 2 side by side: a port target showed on both halves."""
    p = write(tmp_path / "x.sdf", [page(i, chans=marked(port_col=200)) for i in range(40)])
    r = sdf.read_survey(p)
    # Raw decoded samples, not the stretched image: a percentile stretch lifts a
    # flat background to 255 too, which would hide a leak or fake one.
    port = np.stack([np.frombuffer(x.channels[0].samples, "<u2") for x in r.segments[0]])
    stbd = np.stack([np.frombuffer(x.channels[1].samples, "<u2") for x in r.segments[0]])
    assert port.max() > 900
    assert stbd.max() <= 20, "a port-only target leaked into starboard: mirrored decode"


def test_port_is_left_of_nadir_and_distance_is_kept(tmp_path):
    p = write(tmp_path / "x.sdf", [page(i, chans=marked(port_col=300, stbd_col=100)) for i in range(40)])
    wf = waterfall(sdf.read_survey(p).segments[0])
    half = wf.shape[1] // 2
    cols = np.flatnonzero(wf.max(0) > 200)
    left, right = cols[cols < half], cols[cols >= half]
    # samples are decimated 2:1, so sample 300 sits ~150 px out, sample 100 ~50 px out
    assert abs((half - left.mean()) - 152) < 6
    assert abs((right.mean() - half) - 52) < 6


def test_channel_vectors_are_read_as_a_linked_list():
    pg = page(0, chans=[np.full(NS, 10 * (k + 1), np.uint16) for k in range(10)])
    parsed = sdf.parse_page(pg)
    # aft first: row 0 is beam 5 (chan 5 / chan 10), the last row is beam 1
    assert [int(r[0]) for r in parsed.port] == [50, 40, 30, 20, 10]
    assert [int(r[0]) for r in parsed.stbd] == [100, 90, 80, 70, 60]


def test_only_the_beams_to_display_are_used():
    pg = page(0, beams_mask=0b00110, chans=[np.full(NS, 10 * (k + 1), np.uint16) for k in range(10)])
    parsed = sdf.parse_page(pg)
    assert [int(r[0]) for r in parsed.port] == [30, 20]          # beams 3 then 2
    assert parsed.beams == (1, 2)


def test_a_page_with_a_short_vector_is_skipped(tmp_path):
    bad = marked()
    bad[3] = bad[3][:100]
    p = write(tmp_path / "x.sdf", [page(i) for i in range(30)] + [page(30, chans=bad)])
    r = sdf.read_survey(p)
    assert r.pings_read == 31
    assert any("malformed" in w for w in r.warnings)


# --- scale ------------------------------------------------------------------------

def test_pixels_are_square(tmp_path):
    """2 m/s at 4 Hz is 0.5 m per ping; at 6.9 cm per row that is ~7.2 rows per ping."""
    p = write(tmp_path / "x.sdf", [page(i) for i in range(80)])
    r = sdf.read_survey(p)
    rows = r.segments[0]
    assert rows[0].channels[0].num_samples == NS // 2
    assert abs(len(rows) - 79 * 0.5 / sdf.TARGET_RES_M) < 8
    assert r.along_track_res_m == sdf.TARGET_RES_M


def test_speed_is_read_as_metres_per_second(tmp_path):
    slow = sdf.read_survey(write(tmp_path / "a.sdf", [page(i, speed=1.0) for i in range(60)]))
    fast = sdf.read_survey(write(tmp_path / "b.sdf", [page(i, speed=2.0) for i in range(60)]))
    assert abs(len(fast.segments[0]) / len(slow.segments[0]) - 2.0) < 0.1


# --- settings changes ----------------------------------------------------------

def test_a_range_change_starts_a_new_segment(tmp_path):
    pages = [page(i) for i in range(40)] + [page(40 + i, ns=2 * NS, rng=2 * RANGE) for i in range(40)]
    r = sdf.read_survey(write(tmp_path / "x.sdf", pages))
    assert len(r.segments) == 2
    assert r.segments[0][0].channels[0].num_samples == NS // 2
    assert r.segments[1][0].channels[0].num_samples == NS
    assert any("2 separate segments" in w for w in r.warnings)


def test_a_bright_transient_ping_is_dropped(tmp_path):
    hot = [np.full(NS, 3000, np.uint16) for _ in range(10)]
    pages = [page(i) for i in range(30)] + [page(30, chans=hot)] + [page(31 + i) for i in range(30)]
    r = sdf.read_survey(write(tmp_path / "x.sdf", pages))
    wf = waterfall(r.segments[0])
    row_mean = wf.mean(1)
    assert row_mean.max() < 3 * np.median(row_mean), "a transient ping survived as a bright row"
    assert r.pings_dropped >= 1


def test_pings_around_a_mode_change_are_dropped_and_levels_matched(tmp_path):
    loud = marked()
    loud = [c * 3 for c in loud]                              # the gain steps 3x after the change
    pages = [page(i) for i in range(40)] + [page(40 + i, mode=(1, 5), chans=loud) for i in range(40)]
    r = sdf.read_survey(write(tmp_path / "x.sdf", pages))
    assert r.pings_dropped >= 2 * sdf.GUARD_PINGS
    rows = r.segments[0]
    lvl = [np.frombuffer(x.channels[1].samples, "<u2")[30:].mean() for x in rows]
    assert max(lvl) / min(lvl) < 1.3, "the gain step survived as a brightness seam"


# --- navigation ---------------------------------------------------------------------

def test_position_is_the_laid_back_fish_in_degrees(tmp_path):
    r = sdf.read_survey(write(tmp_path / "x.sdf", [page(i) for i in range(30)]))
    row = r.segments[0][0]
    assert abs(row.latitude - LAT) < 1e-6
    assert abs(row.longitude - (LON - 5 / 81_400)) < 1e-5         # 5 m astern, not the ship
    assert row.layback_m == 0.0                                    # never applied twice
    assert row.has_geometry


def test_a_gps_error_leaves_rows_unplaced_not_at_zero(tmp_path):
    """The 2022 factory file: lat/lon 0 and errorFlags 769 must not become 0 N 0 E."""
    r = sdf.read_survey(write(tmp_path / "x.sdf", [page(i, error_flags=769, lat=None) for i in range(30)]))
    assert r.segments and not any(row.has_geometry for row in r.segments[0])
    assert r.pings_without_geometry == 30
    assert any("no GPS fix" in w for w in r.warnings)


# --- the survey entry point accepts it ----------------------------------------------

def test_detect_survey_reads_an_sdf(tmp_path):
    pages = [page(i) for i in range(200)] + [page(200 + i, ns=2 * NS, rng=2 * RANGE) for i in range(200)]
    p = write(tmp_path / "line.sdf", pages)
    r = detect_survey(p, out_dir=tmp_path / "frames", settings=Settings(weights_path=tmp_path / "none.pt"))
    assert r["sonar"] == "Klein System 5000 V2"
    assert r["pings_read"] == 400
    assert r["frames"]
    ids = [f["frame_id"] for f in r["frames"]]
    assert len(ids) == len(set(ids)), "segments reused frame ids"
    for f in r["frames"]:
        assert validate(f) == []
        assert f["frame_position"]["latitude"] == pytest.approx(LAT, abs=1e-4)


def test_detect_survey_reports_a_bad_sdf_instead_of_raising(tmp_path):
    p = tmp_path / "bad.sdf"
    p.write_bytes(b"not a sonar file" * 100)
    r = detect_survey(p, out_dir=tmp_path / "frames", settings=Settings(weights_path=tmp_path / "none.pt"))
    assert r["frames"] == []
    assert any("as SDF" in w for w in r["warnings"])
