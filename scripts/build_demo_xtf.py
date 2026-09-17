"""Build one uploadable .xtf per object class from the curated showcase frames.

    .venv/Scripts/python.exe scripts/build_demo_xtf.py

Writes demo/xtf/<class>.xtf. Each file is a real XTF container -- our own
reader parses it, and so does the app's upload path -- carrying the sonar
frames in demo/showcase/frames/<class>/ as ping samples, plus navigation along
a synthetic track.

Why a container and not the PNGs
--------------------------------
Uploading a PNG makes one frame and no track. Uploading an XTF exercises the
path the problem statement actually describes: a sonar log goes in, the reader
splits it into frames, the pipeline scores each one, and the detections land on
a map because the ping headers carried navigation. That is the demo worth
giving, and it needs a file you can drag into the browser.

What is real and what is not
----------------------------
REAL: every sample in these files is pixel data from a real side-scan frame in
a public dataset's held-out split. The detections the app produces from them
are produced live by the model, from these bytes, through the ordinary
pipeline.

SYNTHETIC: the container and its navigation. The pings never existed as pings;
they are a faithful re-encoding of imagery that arrived as PNG/JPEG, given a
track so the geolocation half of the system has something to work on. Said
plainly in demo/xtf/README.md, and these files are named `*_demo_fixture.xtf`
so nobody mistakes one for a recording.

The across-track brightness profile, and why it is not cosmetic
--------------------------------------------------------------
`xtf.waterfall()` decides which way round each channel's samples are stored by
comparing the mean amplitude at its two ends: the brighter end is the near end,
because side-scan return falls off with range. That is measured rather than
assumed for good reason (see F1 in docs/KNOWN_ISSUES.md).

It also means a file whose frames are UNIFORMLY bright edge to edge has no
detectable orientation, and the reader may mirror half of every frame. So these
files carry a real across-track gain profile: bright at nadir, falling toward
both outer edges. That is what genuine side-scan looks like, it is what makes
the round trip exact, and `verify()` below asserts the round trip rather than
trusting any of this reasoning.
"""

from __future__ import annotations

import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "ai"))

import cv2  # noqa: E402
from ghostnet.xtf import iter_pings, read_file_header, waterfall  # noqa: E402

SHOWCASE = REPO / "demo" / "showcase" / "frames"
OUT_DIR = REPO / "demo" / "xtf"

TILE = 640                 # must match ghostnet.survey.TILE
SAMPLES_PER_CHANNEL = TILE // 2      # port + starboard == one 640 px waterfall
PINGS_PER_FRAME = TILE               # so each frame becomes exactly one tile
BYTES_PER_SAMPLE = 2                 # what _solve_bytes_per_sample tries first

PING_HEADER_BYTES = 256
CHAN_HEADER_BYTES = 64
MAGIC = 0xFACE
HEADER_TYPE_SONAR = 0

SLANT_RANGE_M = 60.0
ALTITUDE_M = 6.0            # keeps the water-column zone to ~32 px a side
DEPTH_M = 34.0
HEADING_DEG = 55.0
SECONDS_PER_PING = 0.1331

#: Across-track gain, and it has to do a real job rather than look plausible.
#:
#: `waterfall()` works out which way round a channel is stored by comparing the
#: mean amplitude of its innermost 10% of samples against its outermost 10%.
#: A gentle quadratic vignette (edge gain 0.40) was NOT enough: on the first
#: wreck frame the image's own right edge was brighter than its centre, the
#: comparison came out backwards, and the reader mirrored the entire starboard
#: half -- port round-tripped at corr 0.998 while starboard managed 0.034.
#:
#: So the falloff is steep and confined to the outer swath: a sixth-power law
#: leaves the central 60% essentially untouched (gain > 0.98 out to |x|=0.5)
#: and collapses hard at the rim, plus a narrow nadir brightening at the
#: centre. Both are things real side-scan does. `build()` asserts the outcome
#: per channel rather than trusting the shape.
EDGE_GAIN = 0.55
FALLOFF_POWER = 4
NADIR_BOOST = 0.20
NADIR_WIDTH = 0.03

TRACKS = {
    "wrecks":     (9.0620, 79.2140),
    "aircraft":   (9.1480, 79.3260),
    "debris":     (9.2310, 79.4380),
    "ghost_gear": (9.3140, 79.5500),
}
STEP_DEG = (0.000045, 0.000065)      # per ping; ~7 m, a plausible ping spacing


def file_header(n_channels: int = 2) -> bytes:
    b = bytearray(1024)
    b[0] = 123                                    # FileFormat: the magic the reader checks
    b[1] = 1                                      # SystemType
    b[2:10] = b"GhostNet"                         # RecordingProgram
    b[18:34] = b"DEMO-FIXTURE\x00\x00\x00\x00"    # SonarName -- says what it is
    struct.pack_into("<HH", b, 164, 3, n_channels)  # nav units = degrees
    return bytes(b)


def sonar_record(ping_no: int, when: datetime, lat: float, lon: float,
                 port: np.ndarray, stbd: np.ndarray) -> bytes:
    n = len(port)
    total = PING_HEADER_BYTES + 2 * (CHAN_HEADER_BYTES + n * BYTES_PER_SAMPLE)
    body = bytearray(total)

    struct.pack_into("<HBBH", body, 0, MAGIC, HEADER_TYPE_SONAR, 0, 2)
    struct.pack_into("<I", body, 10, total)
    struct.pack_into("<H", body, 14, when.year)
    struct.pack_into("<5B", body, 16, when.month, when.day, when.hour, when.minute, when.second)
    struct.pack_into("<I", body, 28, ping_no)
    struct.pack_into("<d", body, 160, lat)
    struct.pack_into("<d", body, 168, lon)
    struct.pack_into("<f", body, 184, 0.0)            # layback
    struct.pack_into("<f", body, 192, DEPTH_M)
    struct.pack_into("<f", body, 196, ALTITUDE_M)
    struct.pack_into("<f", body, 212, HEADING_DEG)

    off = PING_HEADER_BYTES
    for number, data in ((0, port), (1, stbd)):
        struct.pack_into("<H", body, off, number)
        struct.pack_into("<f", body, off + 4, SLANT_RANGE_M)
        struct.pack_into("<f", body, off + 20, SECONDS_PER_PING)
        struct.pack_into("<I", body, off + 42, n)
        start = off + CHAN_HEADER_BYTES
        body[start:start + n * BYTES_PER_SAMPLE] = data.astype("<u2").tobytes()
        off = start + n * BYTES_PER_SAMPLE
    return bytes(body)


def across_track_gain(width: int) -> np.ndarray:
    """1.0 across the seabed, collapsing at the outer swath, bright at nadir."""
    x = (np.arange(width) - (width - 1) / 2.0) / ((width - 1) / 2.0)
    falloff = 1.0 - (1.0 - EDGE_GAIN) * np.abs(x) ** FALLOFF_POWER
    nadir = 1.0 + NADIR_BOOST * np.exp(-((x / NADIR_WIDTH) ** 2))
    return falloff * nadir


def frame_to_waterfall(path: Path) -> np.ndarray:
    """One source image -> a TILE x TILE waterfall block, nadir down the middle."""
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise SystemExit(f"could not read {path}")
    img = cv2.resize(img, (TILE, PINGS_PER_FRAME), interpolation=cv2.INTER_AREA)
    block = img.astype(np.float32)

    # Flatten the source frame's OWN across-track brightness trend before
    # imposing ours, so the profile the reader measures is the one we chose
    # rather than a fight between the two.
    #
    # Without this the construction is at the mercy of the picture: the first
    # wreck frame is roughly eight times brighter at its right rim than at its
    # centre, which beat a quadratic vignette AND a sixth-power falloff, and
    # the reader mirrored the whole starboard half. Different frames lose
    # differently, which is the worst kind of bug -- it would have shipped
    # working for three classes and mirrored for the fourth.
    #
    # This is a per-column gain, so it rescales columns without moving
    # anything: local contrast, shapes and shadows are untouched, which is why
    # the detector still sees what it saw. Real sonar processing applies
    # exactly this correction (TVG and beam-pattern), so the frames come out
    # more like sonar rather than less.
    column_trend = cv2.GaussianBlur(block.mean(axis=0)[None, :], (31, 1), 0)[0]
    block = block / np.maximum(column_trend, 1e-3) * float(column_trend.mean())

    block = block * across_track_gain(TILE)[None, :]
    # Scale into the uint16 range the container carries. The relative structure
    # is what the detector reads, so the absolute scale is free -- and leaving
    # headroom below 65535 keeps the brightest returns from clipping flat.
    return np.clip(block * 200.0, 0, 60000)


def _assert_orientation_is_detectable(records: list[bytes], class_key: str) -> None:
    """Both channels must read as near-range-first, or half of every frame mirrors.

    Checked here, on the bytes about to be written, because the failure is
    silent downstream: the file still parses, still tiles, and still yields
    detections -- on a mirrored image.
    """
    from ghostnet.xtf import _samples_are_near_first

    n_frames = len(records) // PINGS_PER_FRAME
    for frame_index in range(n_frames):
      block_records = records[frame_index * PINGS_PER_FRAME:(frame_index + 1) * PINGS_PER_FRAME]
      for number in (0, 1):
        stack = []
        for rec in block_records:
            off = PING_HEADER_BYTES + number * (CHAN_HEADER_BYTES + SAMPLES_PER_CHANNEL * BYTES_PER_SAMPLE)
            start = off + CHAN_HEADER_BYTES
            stack.append(np.frombuffer(
                rec[start:start + SAMPLES_PER_CHANNEL * BYTES_PER_SAMPLE], dtype="<u2"
            ).astype(np.float32))
        mean_profile = np.mean(stack, axis=0)
        inner = mean_profile[:SAMPLES_PER_CHANNEL // 10].mean()
        outer = mean_profile[-SAMPLES_PER_CHANNEL // 10:].mean()
        if not _samples_are_near_first(mean_profile):
            raise SystemExit(
                f"{class_key} frame {frame_index} channel {number}: nadir end ({inner:.0f}) "
                f"is not brighter than the outer end ({outer:.0f}), so waterfall() will "
                f"mirror this half. Steepen FALLOFF_POWER or lower EDGE_GAIN."
            )


def build(class_key: str) -> Path:
    frames = sorted(p for p in (SHOWCASE / class_key).iterdir() if p.is_file())
    if not frames:
        raise SystemExit(f"no staged frames in {SHOWCASE / class_key}")

    lat, lon = TRACKS[class_key]
    when = datetime(2026, 9, 5, 6, 0, 0, tzinfo=timezone.utc)
    records = [file_header()]
    ping_no = 0

    for frame in frames:
        block = frame_to_waterfall(frame)
        for row in block:
            # port is the left half REVERSED, so its near end (nadir) is the
            # sample the reader meets first. Starboard runs nadir -> outward
            # already. This is the exact inverse of waterfall()'s assembly.
            port = row[:SAMPLES_PER_CHANNEL][::-1]
            stbd = row[SAMPLES_PER_CHANNEL:]
            records.append(sonar_record(ping_no, when, lat, lon, port, stbd))
            ping_no += 1
            lat += STEP_DEG[0]
            lon += STEP_DEG[1]
            when += timedelta(seconds=SECONDS_PER_PING)

    _assert_orientation_is_detectable(records[1:], class_key)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{class_key}_demo_fixture.xtf"
    out.write_bytes(b"".join(records))
    return out


def verify(path: Path, class_key: str) -> None:
    """Read the file back through the real reader and check the round trip.

    Asserted rather than reasoned about, because the one thing that would break
    this silently -- waterfall() deciding a channel is stored the other way
    round and mirroring half of every frame -- produces a file that still
    parses, still tiles, and still yields detections. It would just yield them
    on a mirrored image.
    """
    header = read_file_header(path)
    pings = list(iter_pings(path, header=header, with_samples=True))
    assert header.bytes_per_sample == BYTES_PER_SAMPLE, header.bytes_per_sample
    assert len(pings) == PINGS_PER_FRAME * len(
        [p for p in (SHOWCASE / class_key).iterdir() if p.is_file()]
    ), len(pings)

    # normalise=True on purpose. waterfall() casts to uint8 on the way out
    # whatever this flag says, so raw 16-bit amplitudes would wrap round and
    # the comparison below would fail on a file that is perfectly fine.
    wf = waterfall(pings[:PINGS_PER_FRAME], normalise=True)
    assert wf.shape == (PINGS_PER_FRAME, TILE), wf.shape

    intended = frame_to_waterfall(sorted(
        p for p in (SHOWCASE / class_key).iterdir() if p.is_file())[0])
    # Both are the same array modulo the uint8 cast waterfall() ends with, so
    # compare their shapes after normalising each to 0..1.
    # Apply waterfall()'s own 2-98 percentile stretch to the intended block
    # before comparing. That stretch CLIPS, so comparing a stretched image
    # against an unstretched one scores a perfectly good round trip at 0.81
    # and looks like a bug. Isolate the question actually being asked: did the
    # samples come back in the right order.
    def stretch(img: np.ndarray) -> np.ndarray:
        lo, hi = np.percentile(img[img > 0], (2, 98)) if (img > 0).any() else (0.0, 1.0)
        if hi <= lo:
            hi = lo + 1.0
        return np.clip((img - lo) / (hi - lo), 0, 1)

    a = stretch(intended)
    b = wf.astype(np.float32) / 255.0
    corr = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
    mirrored = float(np.corrcoef(a.ravel(), b[:, ::-1].ravel())[0, 1])
    assert corr > 0.98, (
        f"{path.name}: round trip lost the image (corr={corr:.3f}, "
        f"mirrored={mirrored:.3f}) -- a channel was probably flipped"
    )
    print(f"    round trip corr={corr:.4f} (mirrored would be {mirrored:.3f})")


def main() -> None:
    for key in TRACKS:
        out = build(key)
        size_mb = out.stat().st_size / 1e6
        print(f"{key:12s} -> {out.name}  {size_mb:.1f} MB")
        verify(out, key)


if __name__ == "__main__":
    main()
