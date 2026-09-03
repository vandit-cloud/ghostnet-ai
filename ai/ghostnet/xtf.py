"""Read eXtended Triton Format (.xtf) side-scan files.

Problem statement requirement 8: parse the sonar's own metadata, so a position
comes from the survey rather than from a hand-written sidecar.

    from ghostnet.xtf import read_file_header, iter_pings, geometry_for

    hdr = read_file_header(path)
    for ping in iter_pings(path, limit=500):
        geom = geometry_for(ping, image_width=2048)

Written against a real file rather than the spec alone: NBP050501B.XTF, an
EdgeTech 4200 recorded by Isis on the 2005 Nathaniel B. Palmer cruise in the
Chilean fjords. Every layout decision below was checked against those bytes,
and three of them contradict what the format documentation implies.

Three things the spec will not tell you
---------------------------------------
1. `NumChansToFollow` IS NOT THE NUMBER OF CHANNELS IN THE RECORD. This file
   declares 4 (PORT_LOW, STBD_LOW, PORT_HI, STBD_HI) and every sonar record
   carries 2. Trusting it walks the reader off the end of the record and into
   garbage that still parses as plausible numbers. Channels are therefore
   consumed until the record's declared byte count runs out, and a record whose
   channels do not land exactly on its end is rejected rather than guessed at.

2. BYTES PER SAMPLE has to be derived. The per-channel field in the file header
   reads 0 here. It is instead solved for by walking one record with each
   candidate width and keeping the one that lands exactly on the record
   boundary -- 2 bytes for this file, and the wrong choice overshoots by three
   orders of magnitude, which is what makes the check reliable.

3. NAV UNITS ARE NOT ALWAYS DEGREES. NavUnits 3 means degrees, 0 means metres
   in some projected grid the file does not name. This reader refuses a metres
   file rather than treating easting as longitude, which would put a survey in
   the Gulf of Guinea.

What is deliberately not smoothed over
--------------------------------------
Real files have holes. In this one the FIRST ping records altitude 0.00 while
the other 19,998 carry a real height (up to 14.62 m). An altitude of zero is
not a small error: `ground_range_from_slant` degenerates to ground == slant,
which silently removes the slant correction this project exists to apply, and
is worst near nadir where an operator most trusts the position.

So `geometry_for` returns None when a ping lacks what the geometry needs,
rather than substituting a default. The caller reports a frame without
coordinates, which is already how the rest of the package behaves when
navigation is missing.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .geo import SonarGeometry

XTF_FILE_HEADER_BYTES = 1024
PACKET_HEADER_BYTES = 14
PING_HEADER_BYTES = 256
CHAN_HEADER_BYTES = 64
MAGIC = 0xFACE
HEADER_TYPE_SONAR = 0

#: NavUnits values. Anything else is refused rather than interpreted.
NAV_DEGREES = 3


@dataclass(frozen=True)
class XtfHeader:
    sonar_name: str
    recording_program: str
    nav_units: int
    declared_channels: int
    bytes_per_sample: int

    @property
    def nav_is_degrees(self) -> bool:
        return self.nav_units == NAV_DEGREES


@dataclass
class Channel:
    number: int
    slant_range_m: float
    num_samples: int
    samples: bytes | None = None


@dataclass
class Ping:
    ping_number: int
    time: str
    latitude: float
    longitude: float
    heading_deg: float
    altitude_m: float
    depth_m: float
    layback_m: float
    seconds_per_ping: float
    channels: list[Channel]

    @property
    def has_geometry(self) -> bool:
        """Whether this ping carries what a position actually needs.

        Altitude is the field that goes missing in practice, and a zero there
        is not a near-miss: it removes the slant correction entirely.
        """
        return (
            self.altitude_m > 0.0
            and bool(self.channels)
            and self.channels[0].slant_range_m > 0.0
            and self.channels[0].num_samples > 0
        )


def _solve_bytes_per_sample(record: bytes) -> int | None:
    """Find the sample width that makes one record's channels land exactly.

    Returns None when no candidate fits, which means the record is malformed
    or the layout assumption is wrong -- either way, guessing is worse.
    """
    declared = len(record)
    for width in (2, 1, 4):
        off = PING_HEADER_BYTES
        while off + CHAN_HEADER_BYTES <= declared:
            n_samples = struct.unpack_from("<I", record, off + 42)[0]
            off += CHAN_HEADER_BYTES + n_samples * width
            if off == declared:
                return width
            if off > declared:
                break
    return None


def read_file_header(path: str | Path) -> XtfHeader:
    with open(path, "rb") as fh:
        head = fh.read(XTF_FILE_HEADER_BYTES)
        if len(head) < XTF_FILE_HEADER_BYTES:
            raise ValueError("file is shorter than an XTF header")
        if head[0] != 123:
            raise ValueError(f"not an XTF file: FileFormat byte is {head[0]}, expected 123")

        recording = head[2:10].decode("ascii", "replace").strip("\x00 ")
        sonar = head[18:34].decode("ascii", "replace").strip("\x00 ")
        nav_units, n_chan = struct.unpack_from("<HH", head, 164)

        width = None
        for _ in range(8):                      # a few records in, in case of notes
            hdr = fh.read(PACKET_HEADER_BYTES)
            if len(hdr) < PACKET_HEADER_BYTES:
                break
            magic, htype = struct.unpack_from("<HB", hdr, 0)
            n_bytes = struct.unpack_from("<I", hdr, 10)[0]
            if magic != MAGIC or n_bytes < PACKET_HEADER_BYTES:
                break
            body = fh.read(n_bytes - PACKET_HEADER_BYTES)
            if htype == HEADER_TYPE_SONAR:
                width = _solve_bytes_per_sample(hdr + body)
                if width:
                    break
    if width is None:
        raise ValueError("could not determine bytes per sample from any sonar record")
    return XtfHeader(sonar, recording, nav_units, n_chan, width)


def _parse_ping(record: bytes, bytes_per_sample: int, with_samples: bool) -> Ping | None:
    if len(record) < PING_HEADER_BYTES:
        return None
    year, = struct.unpack_from("<H", record, 14)
    month, day, hour, minute, second = struct.unpack_from("<5B", record, 16)
    ping_number, = struct.unpack_from("<I", record, 28)
    lat, = struct.unpack_from("<d", record, 160)
    lon, = struct.unpack_from("<d", record, 168)
    layback, = struct.unpack_from("<f", record, 184)
    depth, = struct.unpack_from("<f", record, 192)
    altitude, = struct.unpack_from("<f", record, 196)
    heading, = struct.unpack_from("<f", record, 212)

    channels: list[Channel] = []
    seconds_per_ping = 0.0
    off = PING_HEADER_BYTES
    # Consume channels until the record runs out -- NumChansToFollow lies.
    while off + CHAN_HEADER_BYTES <= len(record):
        number, = struct.unpack_from("<H", record, off)
        slant, = struct.unpack_from("<f", record, off + 4)
        spp, = struct.unpack_from("<f", record, off + 20)
        n_samples, = struct.unpack_from("<I", record, off + 42)
        data_at = off + CHAN_HEADER_BYTES
        data_end = data_at + n_samples * bytes_per_sample
        if data_end > len(record):
            return None                          # malformed; never half-read a ping
        channels.append(Channel(
            number=number, slant_range_m=slant, num_samples=n_samples,
            samples=record[data_at:data_end] if with_samples else None,
        ))
        seconds_per_ping = spp or seconds_per_ping
        off = data_end
    if off != len(record):
        return None                              # channels did not land exactly

    return Ping(
        ping_number=ping_number,
        time=f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}",
        latitude=lat, longitude=lon, heading_deg=heading,
        altitude_m=altitude, depth_m=depth, layback_m=layback,
        seconds_per_ping=seconds_per_ping, channels=channels,
    )


def iter_pings(
    path: str | Path,
    header: XtfHeader | None = None,
    with_samples: bool = False,
    limit: int | None = None,
) -> Iterator[Ping]:
    """Yield sonar pings in file order, skipping non-sonar packets."""
    header = header or read_file_header(path)
    seen = 0
    with open(path, "rb") as fh:
        fh.seek(XTF_FILE_HEADER_BYTES)
        while limit is None or seen < limit:
            hdr = fh.read(PACKET_HEADER_BYTES)
            if len(hdr) < PACKET_HEADER_BYTES:
                return
            magic, htype = struct.unpack_from("<HB", hdr, 0)
            n_bytes = struct.unpack_from("<I", hdr, 10)[0]
            if magic != MAGIC or n_bytes < PACKET_HEADER_BYTES:
                return                            # lost sync; stop rather than hunt
            body = fh.read(n_bytes - PACKET_HEADER_BYTES)
            if len(body) < n_bytes - PACKET_HEADER_BYTES:
                return
            if htype != HEADER_TYPE_SONAR:
                continue
            ping = _parse_ping(hdr + body, header.bytes_per_sample, with_samples)
            if ping is not None:
                seen += 1
                yield ping


def geometry_for(ping: Ping, image_width: int, along_track_res_m: float | None = None) -> SonarGeometry | None:
    """Build SonarGeometry for a ping, or None when the ping cannot support one.

    `image_width` is the width of the assembled waterfall, so nadir sits at its
    centre for a port+starboard image.
    """
    if not ping.has_geometry:
        return None
    chan = ping.channels[0]
    return SonarGeometry(
        nadir_col=image_width / 2.0,
        range_resolution_m=chan.slant_range_m / chan.num_samples,
        altitude_m=ping.altitude_m,
        heading_deg=ping.heading_deg,
        layback_m=ping.layback_m,
        along_track_res_m=along_track_res_m,
    )


def waterfall(pings: list[Ping], normalise: bool = True):
    """Assemble port+starboard channels into a conventional waterfall image.

    Returns a uint8 array, one row per ping, nadir down the centre: port
    reversed on the left, starboard on the right. That orientation is what
    `geometry_for(..., image_width)` assumes when it puts nadir at the middle.

    Normalisation is per-image percentile stretch, not per-row. Per-row
    equalisation is tempting because it flattens the across-track gain ramp,
    but it also erases the very thing this project measures: a row containing
    a bright target gets scaled down until the target looks like seabed, and a
    dropout row of pure noise gets stretched until it looks like data.
    """
    import numpy as np

    if not pings:
        return np.zeros((0, 0), np.uint8)

    rows = []
    for ping in pings:
        port = stbd = None
        for chan in ping.channels:
            if chan.samples is None:
                continue
            data = np.frombuffer(chan.samples, dtype="<u2").astype(np.float32)
            # Even channel numbers are port, odd starboard, in every EdgeTech
            # file seen here. Falling back on order rather than trusting a
            # name string that this file stores with leading control bytes.
            if chan.number % 2 == 0 and port is None:
                port = data
            elif stbd is None:
                stbd = data
        if port is None and stbd is None:
            continue
        width = max(len(port) if port is not None else 0, len(stbd) if stbd is not None else 0)
        if port is None:
            port = np.zeros(width, np.float32)
        if stbd is None:
            stbd = np.zeros(width, np.float32)
        rows.append(np.concatenate([port[::-1], stbd]))

    if not rows:
        return np.zeros((0, 0), np.uint8)

    width = max(len(r) for r in rows)
    img = np.zeros((len(rows), width), np.float32)
    for i, r in enumerate(rows):
        img[i, : len(r)] = r

    if normalise:
        lo, hi = np.percentile(img[img > 0], (2, 98)) if (img > 0).any() else (0.0, 1.0)
        if hi <= lo:
            hi = lo + 1.0
        img = np.clip((img - lo) / (hi - lo), 0, 1) * 255.0
    return img.astype(np.uint8)
