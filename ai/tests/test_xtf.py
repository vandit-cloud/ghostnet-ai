"""XTF reader tests (problem statement requirement 8).

The real file this was written against is 200 MB and gitignored, so these build
XTF bytes by hand. That is deliberate beyond convenience: a synthetic file can
be made to contain the exact malformations that matter, and the three that
matter here are all cases where a wrong reader still returns confident numbers.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.xtf import (  # noqa: E402
    _solve_bytes_per_sample, geometry_for, iter_pings, read_file_header,
)

N_SAMPLES = 16
BYTES_PER_SAMPLE = 2


def file_header(nav_units: int = 3, declared_channels: int = 4) -> bytes:
    b = bytearray(1024)
    b[0] = 123                                   # FileFormat
    b[1] = 1                                     # SystemType
    b[2:10] = b"Isis\x00\x00\x00\x00"
    b[18:34] = b"Edgetech_4200.E\x00"
    struct.pack_into("<HH", b, 164, nav_units, declared_channels)
    return bytes(b)


def sonar_record(*, lat: float, lon: float, heading: float, altitude: float,
                 n_channels: int = 2, declared_chans_to_follow: int = 4,
                 slant: float = 100.0) -> bytes:
    body = bytearray(256 + n_channels * (64 + N_SAMPLES * BYTES_PER_SAMPLE))
    total = len(body)
    struct.pack_into("<HBBH", body, 0, 0xFACE, 0, 0, declared_chans_to_follow)
    struct.pack_into("<I", body, 10, total)
    struct.pack_into("<H", body, 14, 2005)
    struct.pack_into("<5B", body, 16, 7, 1, 5, 54, 27)
    struct.pack_into("<I", body, 28, 42)         # PingNumber
    struct.pack_into("<d", body, 160, lat)
    struct.pack_into("<d", body, 168, lon)
    struct.pack_into("<f", body, 184, 0.0)       # layback
    struct.pack_into("<f", body, 192, 16.0)      # depth
    struct.pack_into("<f", body, 196, altitude)
    struct.pack_into("<f", body, 212, heading)

    off = 256
    for c in range(n_channels):
        struct.pack_into("<H", body, off, c)
        struct.pack_into("<f", body, off + 4, slant)
        struct.pack_into("<f", body, off + 20, 0.1331)   # seconds per ping
        struct.pack_into("<I", body, off + 42, N_SAMPLES)
        off += 64 + N_SAMPLES * BYTES_PER_SAMPLE
    return bytes(body)


def write_xtf(tmp_path: Path, records: list[bytes], **hdr) -> Path:
    p = tmp_path / "synthetic.xtf"
    p.write_bytes(file_header(**hdr) + b"".join(records))
    return p


# --- the file header -------------------------------------------------------

def test_rejects_a_file_that_is_not_xtf(tmp_path):
    p = tmp_path / "not.xtf"
    p.write_bytes(b"\x00" * 2048)
    with pytest.raises(ValueError, match="not an XTF file"):
        read_file_header(p)


def test_reads_sonar_identity_and_nav_units(tmp_path):
    p = write_xtf(tmp_path, [sonar_record(lat=-46.3, lon=-73.7, heading=349.3, altitude=12.0)])
    h = read_file_header(p)
    assert h.sonar_name == "Edgetech_4200.E"
    assert h.recording_program == "Isis"
    assert h.nav_is_degrees


def test_bytes_per_sample_is_solved_not_trusted(tmp_path):
    """The per-channel field reads 0 in the real file, so the width is derived
    by finding the one that lands exactly on the record boundary."""
    rec = sonar_record(lat=0.0, lon=0.0, heading=0.0, altitude=10.0)
    assert _solve_bytes_per_sample(rec) == BYTES_PER_SAMPLE
    assert read_file_header(write_xtf(tmp_path, [rec])).bytes_per_sample == BYTES_PER_SAMPLE


# --- the trap that motivated the reader ------------------------------------

def test_num_chans_to_follow_is_not_believed(tmp_path):
    """The real file declares 4 channels per record and carries 2. Trusting the
    field reads past the record into whatever follows -- which still unpacks
    into plausible floats, so nothing downstream would notice."""
    rec = sonar_record(lat=-46.3, lon=-73.7, heading=10.0, altitude=12.0,
                       n_channels=2, declared_chans_to_follow=4)
    p = write_xtf(tmp_path, [rec, rec])
    pings = list(iter_pings(p, with_samples=True))
    assert len(pings) == 2
    assert all(len(ping.channels) == 2 for ping in pings)


def test_a_record_whose_channels_overrun_is_dropped(tmp_path):
    """Better to lose a ping than to emit one built from adjacent bytes.

    A GOOD record leads, so the file header can still solve the sample width --
    otherwise this would be testing the unrelated case of a file whose very
    first record is unreadable, where refusing the whole file is correct.
    """
    good = sonar_record(lat=-46.3, lon=-73.7, heading=10.0, altitude=12.0)
    bad = bytearray(sonar_record(lat=0.0, lon=0.0, heading=0.0, altitude=10.0))
    struct.pack_into("<I", bad, 256 + 42, 9999)      # claim far more samples
    p = write_xtf(tmp_path, [good, bytes(bad), good])
    pings = list(iter_pings(p))
    assert len(pings) == 2
    assert all(ping.latitude == pytest.approx(-46.3) for ping in pings)


def test_a_file_whose_first_record_is_unreadable_is_refused(tmp_path):
    """The other half of the case above: with nothing parseable to measure
    against, the sample width cannot be solved and guessing one would produce a
    whole file of plausible nonsense."""
    bad = bytearray(sonar_record(lat=0.0, lon=0.0, heading=0.0, altitude=10.0))
    struct.pack_into("<I", bad, 256 + 42, 9999)
    with pytest.raises(ValueError, match="bytes per sample"):
        read_file_header(write_xtf(tmp_path, [bytes(bad)]))


def test_navigation_in_metres_is_flagged_not_reinterpreted(tmp_path):
    """NavUnits 0 means a projected grid the file does not name. Reading easting
    as longitude would silently relocate the survey."""
    p = write_xtf(tmp_path, [sonar_record(lat=0.0, lon=0.0, heading=0.0, altitude=10.0)],
                  nav_units=0)
    assert read_file_header(p).nav_is_degrees is False


# --- geometry --------------------------------------------------------------

def test_ping_without_altitude_yields_no_geometry(tmp_path):
    """The first ping of the real file records altitude 0.00. Substituting a
    default there removes the slant correction silently, and it is worst near
    nadir where an operator most trusts the position."""
    p = write_xtf(tmp_path, [sonar_record(lat=-46.3, lon=-73.7, heading=0.0, altitude=0.0)])
    ping = next(iter(iter_pings(p)))
    assert ping.has_geometry is False
    assert geometry_for(ping, image_width=2048) is None


def test_geometry_is_built_from_the_pings_own_numbers(tmp_path):
    p = write_xtf(tmp_path, [sonar_record(lat=-46.3, lon=-73.7, heading=349.3,
                                          altitude=12.0, slant=100.0)])
    ping = next(iter(iter_pings(p)))
    geom = geometry_for(ping, image_width=2048)
    assert geom is not None
    assert geom.altitude_m == pytest.approx(12.0)
    assert geom.heading_deg == pytest.approx(349.3, abs=1e-3)
    assert geom.nadir_col == 1024.0                       # centre of the waterfall
    assert geom.range_resolution_m == pytest.approx(100.0 / N_SAMPLES)


def test_nav_and_time_survive_the_round_trip(tmp_path):
    p = write_xtf(tmp_path, [sonar_record(lat=-46.352302, lon=-73.732185,
                                          heading=349.3, altitude=12.0)])
    ping = next(iter(iter_pings(p)))
    assert ping.latitude == pytest.approx(-46.352302)
    assert ping.longitude == pytest.approx(-73.732185)
    assert ping.time == "2005-07-01T05:54:27"


def test_non_sonar_packets_are_skipped(tmp_path):
    note = bytearray(64)
    struct.pack_into("<HBBH", note, 0, 0xFACE, 1, 0, 0)   # HeaderType 1 = note
    struct.pack_into("<I", note, 10, len(note))
    rec = sonar_record(lat=0.0, lon=0.0, heading=0.0, altitude=10.0)
    p = write_xtf(tmp_path, [bytes(note), rec, bytes(note), rec])
    assert len(list(iter_pings(p))) == 2


def test_reader_stops_cleanly_on_lost_sync(tmp_path):
    """Truncation and corruption are normal for survey files pulled off a
    vessel. Stopping beats scanning forward for the next plausible magic."""
    rec = sonar_record(lat=0.0, lon=0.0, heading=0.0, altitude=10.0)
    p = tmp_path / "truncated.xtf"
    p.write_bytes(file_header() + rec + b"\xff" * 40)
    assert len(list(iter_pings(p))) == 1


def test_sample_width_is_carried_on_every_channel(tmp_path):
    """waterfall() decodes `samples` and must not assume 16-bit. Hardcoding it
    would render an 8-bit file as garbage that still looks like a sonar image
    -- wrong, but not obviously wrong."""
    p = write_xtf(tmp_path, [sonar_record(lat=-46.3, lon=-73.7, heading=0.0, altitude=12.0)])
    header = read_file_header(p)
    ping = next(iter(iter_pings(p, header, with_samples=True)))
    assert all(c.bytes_per_sample == header.bytes_per_sample for c in ping.channels)
    assert all(len(c.samples) == c.num_samples * c.bytes_per_sample for c in ping.channels)
