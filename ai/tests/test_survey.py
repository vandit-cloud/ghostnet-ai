"""Tests for detect_survey: a raw sonar file in, contract payloads out.

The tiler is the piece with no ground truth to check against, so these assert
the properties that make its OUTPUT trustworthy instead: every frame is
contract-valid, every tile is the size the detector was trained on, nadir moves
with the tile rather than staying at the waterfall's centre, and a file the
reader cannot use degrades to a warning instead of an exception.

No model and no GPU is needed. `detect()` already returns a valid empty payload
when there are no weights, which is exactly the path these exercise -- so they
run on a CI box, and they run while a training job owns the GPU.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet import survey as survey_mod  # noqa: E402
from ghostnet.config import Settings  # noqa: E402
from ghostnet.contract import validate  # noqa: E402
from ghostnet.survey import detect_survey  # noqa: E402
from ghostnet.xtf import Channel, Ping  # noqa: E402

WIDTH = 2048          # what a real EdgeTech 4200 line assembles to
SAMPLES = 1024        # per channel, so nadir sits at WIDTH / 2


def ping(n: int, *, altitude_m: float = 7.8, lat: float = -46.35, lon: float = -73.73) -> Ping:
    """A ping shaped like the real file this reader was built against."""
    return Ping(
        ping_number=n,
        time="2005-05-01T00:00:00",
        latitude=lat + n * 2.24e-5,      # ~2.5 m of northing per ping
        longitude=lon,
        heading_deg=348.5,
        altitude_m=altitude_m,
        depth_m=120.0,
        layback_m=0.0,
        seconds_per_ping=0.25,
        channels=[Channel(number=c, slant_range_m=99.8, num_samples=SAMPLES) for c in (0, 1)],
    )


@pytest.fixture
def fake_line(monkeypatch):
    """Replace the file reader so the tiler can be tested without a 200 MB fixture."""
    pings = [ping(i) for i in range(1400)]

    class Hdr:
        sonar_name = "Edgetech_4200.E"

    monkeypatch.setattr(survey_mod, "read_file_header", lambda p: Hdr())
    monkeypatch.setattr(survey_mod, "iter_pings", lambda p, **kw: iter(pings[: kw.get("limit") or None]))
    monkeypatch.setattr(
        survey_mod, "waterfall",
        lambda chunk, **kw: np.full((len(chunk), WIDTH), 90, dtype=np.uint8),
    )
    return pings


@pytest.fixture
def out(tmp_path):
    return tmp_path / "frames"


# --- the output is contract-governed, whatever the tiler does --------------

def test_every_frame_satisfies_the_output_contract(fake_line, out, tmp_path):
    r = detect_survey("line.xtf", out_dir=out, settings=Settings(weights_path=tmp_path / "none.pt"))
    assert r["frames"]
    for f in r["frames"]:
        assert validate(f) == []
        assert f["contract_version"]


def test_tiles_are_all_the_size_the_detector_was_trained_on(fake_line, out, tmp_path):
    """A 2048 px swath does not divide into 640, and the remainder must not
    ship as a thin strip -- the detector letterboxes it and loses the
    across-track detail a small object lives in."""
    import cv2

    detect_survey("line.xtf", out_dir=out, settings=Settings(weights_path=tmp_path / "none.pt"))
    written = sorted(out.glob("*.png"))
    assert written
    for p in written:
        im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        assert im.shape == (survey_mod.TILE, survey_mod.TILE)


def test_the_last_across_track_tile_ends_flush_with_the_swath(fake_line, out, tmp_path):
    detect_survey("line.xtf", out_dir=out, settings=Settings(weights_path=tmp_path / "none.pt"))
    xs = sorted({int(p.stem.split("__x")[1]) for p in out.glob("*.png")})
    assert xs[0] == 0
    assert xs[-1] == WIDTH - survey_mod.TILE      # pulled left, not a remainder


# --- geometry has to follow the tile ---------------------------------------

def test_nadir_moves_with_the_tile_instead_of_staying_at_the_swath_centre():
    """The bug this guards against is subtle and survives casual review: leave
    nadir at 1024 for every tile and a far-range object is placed as though it
    were near nadir, which is where the slant correction matters most."""
    p = ping(0)
    near = survey_mod._meta_for_tile(
        p, survey_id="s", frame_id="f", image_width=WIDTH, x_offset=0,
        nadir_row=0.0, along_track_res_m=2.5,
    )
    far = survey_mod._meta_for_tile(
        p, survey_id="s", frame_id="f", image_width=WIDTH, x_offset=1408,
        nadir_row=0.0, along_track_res_m=2.5,
    )
    assert near["nadir_col"] == WIDTH / 2
    assert far["nadir_col"] == WIDTH / 2 - 1408          # negative: nadir is off to the left
    assert far["nadir_col"] < 0


def test_range_resolution_comes_from_the_ping_not_a_default():
    meta = survey_mod._meta_for_tile(
        ping(0), survey_id="s", frame_id="f", image_width=WIDTH, x_offset=0,
        nadir_row=0.0, along_track_res_m=None,
    )
    assert meta["range_resolution_m"] == pytest.approx(99.8 / SAMPLES)
    assert meta["altitude_m"] == pytest.approx(7.8)


def test_along_track_resolution_is_measured_from_the_navigation():
    """Vessel speed is not in the file and an operator may not know it, but the
    distance between consecutive fixes is exactly the row spacing."""
    step = survey_mod._along_track_res_m([ping(i) for i in range(20)])
    assert step == pytest.approx(2.49, abs=0.15)


def test_a_wild_navigation_jump_does_not_stretch_the_whole_tile():
    """One bad fix in a 640-ping slice would drag a mean badly; the median is
    used precisely so it cannot."""
    pings = [ping(i) for i in range(20)]
    pings[10] = ping(10, lat=10.0)                       # a fix thousands of km away
    step = survey_mod._along_track_res_m(pings)
    assert step == pytest.approx(2.49, abs=0.15)


def test_no_navigation_at_all_leaves_the_row_scale_unset():
    assert survey_mod._along_track_res_m([]) is None


# --- degrade, never raise --------------------------------------------------

def test_an_unreadable_file_is_reported_not_raised(out, monkeypatch, tmp_path):
    def boom(path):
        raise OSError("not an xtf")

    monkeypatch.setattr(survey_mod, "read_file_header", boom)
    r = detect_survey("garbage.bin", out_dir=out, settings=Settings(weights_path=tmp_path / "none.pt"))
    assert r["frames"] == []
    assert any("could not read" in w for w in r["warnings"])


def test_a_file_with_no_pings_says_so(out, monkeypatch, tmp_path):
    class Hdr:
        sonar_name = "x"

    monkeypatch.setattr(survey_mod, "read_file_header", lambda p: Hdr())
    monkeypatch.setattr(survey_mod, "iter_pings", lambda p, **kw: iter([]))
    r = detect_survey("empty.xtf", out_dir=out, settings=Settings(weights_path=tmp_path / "none.pt"))
    assert r["frames"] == []
    assert any("no sonar pings" in w for w in r["warnings"])


def test_pings_missing_altitude_are_counted_and_still_scored(out, monkeypatch, tmp_path):
    """An altitude of zero removes the slant correction entirely, so those
    pings cannot be positioned -- but the frames covering them are still worth
    scoring, and the count has to be visible or silence reads as 'nothing
    there'."""
    pings = [ping(i, altitude_m=0.0 if i < 200 else 7.8) for i in range(1400)]

    class Hdr:
        sonar_name = "x"

    monkeypatch.setattr(survey_mod, "read_file_header", lambda p: Hdr())
    monkeypatch.setattr(survey_mod, "iter_pings", lambda p, **kw: iter(pings))
    monkeypatch.setattr(
        survey_mod, "waterfall",
        lambda chunk, **kw: np.full((len(chunk), WIDTH), 90, dtype=np.uint8),
    )
    r = detect_survey("line.xtf", out_dir=out, settings=Settings(weights_path=tmp_path / "none.pt"))
    assert r["pings_without_geometry"] == 200
    assert any("lack the altitude" in w for w in r["warnings"])
    assert r["frames"]


def test_a_slice_that_cannot_be_assembled_is_skipped_not_fatal(fake_line, out, monkeypatch, tmp_path):
    calls = {"n": 0}

    def flaky(chunk, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("bad channel layout")
        return np.full((len(chunk), WIDTH), 90, dtype=np.uint8)

    monkeypatch.setattr(survey_mod, "waterfall", flaky)
    r = detect_survey("line.xtf", out_dir=out, settings=Settings(weights_path=tmp_path / "none.pt"))
    assert any("could not be assembled" in w for w in r["warnings"])
    assert r["frames"]                                   # the rest of the line still ran
