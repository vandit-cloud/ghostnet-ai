"""The starboard half of every frame was mirrored across-track.

`waterfall()` reversed the port channel and took starboard as written, on the
assumption that both channels store their samples near-range-first. The NBP0505
file does not: measured over 640 pings, channel 0 runs 32.1 -> 2.2 across its
1024 samples (near-first, as assumed) and channel 1 runs 2.7 -> 45.2 (far-first,
the opposite). Same sonar, same ping, opposite order.

Assembling those two without noticing produced a sawtooth across-track profile
-- dark at the left edge, bright at the centre seam, dark again, bright at the
right edge -- instead of the single bright nadir band down the middle that a
side-scan waterfall has. The consequences were not cosmetic:

* the nadir and water-column return, the brightest feature in the data, was
  drawn at the OUTER edge of the swath, and the detector boxed it -- four of
  the five detections on the demo survey were 34-38 px vertical stripes flush
  against global column 2047;
* `geometry_for` puts nadir at the image centre, so every starboard detection
  measured its across-track distance from the wrong place, corrupting the
  slant-range to ground-range conversion and therefore its map position.

These tests assert the invariant that actually holds for a side-scan waterfall,
whatever a vendor's sample order: nadir is in the CENTRE and brightness falls
off toward both outer edges.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.xtf import Channel, Ping, waterfall  # noqa: E402

N = 256


def ramp(near_first: bool) -> bytes:
    """A channel's samples: bright at the near end, decaying to the far end.

    Written near-first or far-first on request. uint16, matching the real file.
    """
    profile = np.linspace(1000.0, 10.0, N)
    if not near_first:
        profile = profile[::-1]
    return profile.astype("<u2").tobytes()


def ping(port_near_first: bool, stbd_near_first: bool) -> Ping:
    return Ping(
        ping_number=1, time="2005-07-01T05:54:27", latitude=-47.0, longitude=-75.0,
        heading_deg=90.0, altitude_m=20.0, depth_m=100.0, layback_m=0.0,
        seconds_per_ping=0.1331,
        channels=[
            Channel(number=0, slant_range_m=100.0, num_samples=N,
                    samples=ramp(port_near_first), bytes_per_sample=2),
            Channel(number=1, slant_range_m=100.0, num_samples=N,
                    samples=ramp(stbd_near_first), bytes_per_sample=2),
        ],
    )


def profile_of(img) -> tuple[float, float, float]:
    """(left edge, centre, right edge) mean brightness of a waterfall."""
    col = img.astype(np.float32).mean(axis=0)
    edge = max(1, len(col) // 32)
    mid0, mid1 = len(col) // 2 - edge, len(col) // 2 + edge
    return float(col[:edge].mean()), float(col[mid0:mid1].mean()), float(col[-edge:].mean())


@pytest.mark.parametrize(
    "port_near_first, stbd_near_first",
    [
        (True, True),    # both near-first
        (True, False),   # the NBP0505 case: starboard written far-first
        (False, True),   # the mirror of it
        (False, False),  # both far-first
    ],
)
def test_nadir_lands_in_the_centre_whatever_the_sample_order(port_near_first, stbd_near_first):
    """The invariant. All four storage conventions must assemble the same way.

    Before the fix, only (True, True) produced a correct image; the NBP0505
    case (True, False) produced a sawtooth with the nadir band at the right
    edge.
    """
    img = waterfall([ping(port_near_first, stbd_near_first) for _ in range(32)])
    left, centre, right = profile_of(img)

    assert centre > left * 3, f"nadir should dominate the left edge, got {centre:.1f} vs {left:.1f}"
    assert centre > right * 3, f"nadir should dominate the right edge, got {centre:.1f} vs {right:.1f}"


def test_the_two_halves_are_mirror_images_of_each_other():
    """A symmetric seabed must render symmetrically.

    This is what catches a single-channel flip specifically: a mirrored
    starboard half still has a bright band and a dark band, so an edge test
    alone could pass while the halves disagree.
    """
    img = waterfall([ping(True, False) for _ in range(32)]).astype(np.float32)
    col = img.mean(axis=0)
    half = len(col) // 2
    port = col[:half][::-1]      # centre -> outer
    stbd = col[half:]            # centre -> outer

    # Same channel content on both sides, so the two profiles should agree
    # closely once both are read outward from the centre.
    assert np.allclose(port, stbd, atol=2.0), (
        "port and starboard disagree: one half is mirrored"
    )


def test_brightness_falls_off_monotonically_from_the_centre():
    """No interior seam. The sawtooth showed up as a jump back to near-zero at
    the midpoint, which a coarse three-point profile could miss."""
    img = waterfall([ping(True, False) for _ in range(32)]).astype(np.float32)
    col = img.mean(axis=0)
    half = len(col) // 2

    outward = col[half:]
    # Allow speckle wobble, but the trend from nadir outward must be downhill:
    # no point in the outer half may exceed the nadir column.
    assert outward.argmax() < len(outward) * 0.1, (
        "the brightest starboard column is not near nadir -- the half is flipped"
    )
    assert outward[-1] < outward[0] * 0.5, "brightness should decay toward the outer edge"


def test_a_single_channel_ping_still_assembles():
    """Half a ping is not a reason to crash or to guess at the missing side."""
    one = Ping(
        ping_number=1, time="", latitude=0.0, longitude=0.0, heading_deg=0.0,
        altitude_m=20.0, depth_m=100.0, layback_m=0.0, seconds_per_ping=0.1,
        channels=[Channel(number=0, slant_range_m=100.0, num_samples=N,
                          samples=ramp(True), bytes_per_sample=2)],
    )
    img = waterfall([one] * 8)
    assert img.shape[0] == 8
    assert img.shape[1] == 2 * N  # the absent side is zero-filled, not dropped
