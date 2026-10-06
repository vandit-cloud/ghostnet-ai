"""Overlapping tiles and the seam merge.

Three things have to hold for overlap to be worth its cost:

  * the tiling still covers every ping and every column with full-size tiles,
    and every seam really is overlapped by at least what was asked for;
  * two tiles that both contain an object place it at the SAME position --
    otherwise the overlap creates two pins a few metres apart, which no merge
    in pixel space would ever notice;
  * the merge folds sightings of one object and nothing else: not two classes,
    not two objects side by side, not two boxes the detector kept in one frame.

No model and no GPU: tiling is pure arithmetic, and the end-to-end test swaps
`detect` for a fake that "sees" a planted object in whichever tile holds it.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet import merge  # noqa: E402
from ghostnet import survey as survey_mod  # noqa: E402
from ghostnet.config import Settings  # noqa: E402
from ghostnet.contract import validate  # noqa: E402
from ghostnet.geo import geotag_pixel  # noqa: E402
from ghostnet.infer import _geometry_from_meta  # noqa: E402
from ghostnet.xtf import Channel, Ping  # noqa: E402

TILE = survey_mod.TILE
WIDTH = 2048
SAMPLES = 1024
SETTINGS = Settings(weights_path=Path("none.pt"))


def ping(n: int) -> Ping:
    """Heading 000 and moving due north, so the along-track axis the geometry
    assumes is the one the navigation actually travels."""
    return Ping(
        ping_number=n,
        time="2005-05-01T00:00:00",
        latitude=-46.35 + n * 2.24e-5,
        longitude=-73.73,
        heading_deg=0.0,
        altitude_m=7.8,
        depth_m=120.0,
        layback_m=0.0,
        seconds_per_ping=0.25,
        channels=[Channel(number=c, slant_range_m=99.8, num_samples=SAMPLES) for c in (0, 1)],
    )


def seams(starts: list[int]) -> list[int]:
    """Overlap, in pixels, between each pair of consecutive tiles."""
    return [a + TILE - b for a, b in zip(starts, starts[1:])]


# --- offsets ----------------------------------------------------------------

def test_zero_overlap_reproduces_the_old_tiling_exactly():
    """GHOSTNET_TILE_OVERLAP=0 is advertised as a rollback, so it has to be one."""
    assert survey_mod._offsets(2048, TILE, 0.0) == [0, 640, 1280, 1408]
    assert survey_mod._offsets(1400, TILE, 0.0) == [0, 640, 760]
    assert survey_mod._across_offsets(2048, TILE, 0.0, 80) == [0, 640, 1280, 1408]


@pytest.mark.parametrize("extent", [641, 1400, 2048, 6039])
@pytest.mark.parametrize("overlap", [0.25, 0.5])
def test_overlapped_tiles_cover_everything_and_every_seam_overlaps(extent, overlap):
    starts = survey_mod._offsets(extent, TILE, overlap)
    assert starts[0] == 0 and starts[-1] == extent - TILE          # flush both ends
    assert all(s + TILE <= extent for s in starts)                  # no short tile
    assert min(seams(starts)) >= TILE * overlap - 1                 # rounding only


def test_overlap_is_clamped_rather_than_looping_forever():
    assert survey_mod._offsets(2048, TILE, 1.0)                      # stride would be 0
    assert survey_mod._offsets(2048, TILE, -0.3) == survey_mod._offsets(2048, TILE, 0.0)


def test_a_swath_no_wider_than_a_tile_is_one_tile():
    assert survey_mod._offsets(640, TILE, 0.25) == [0]
    assert survey_mod._across_offsets(600, TILE, 0.25, 50) == [0]


def test_the_water_column_sits_mid_tile_and_on_no_other_tile():
    """The first overlap run put the dark nadir band 64 px from one tile's
    border and 96 px from another's, and the detector called it debris in
    both. On the low-floor demo run that layout produced 8 water-column
    detections against 2 for this one (ai/experiments/tile-overlap)."""
    water = 80
    starts = survey_mod._across_offsets(WIDTH, TILE, 0.25, water)
    nadir = WIDTH / 2
    holding = [s for s in starts if s < nadir + water and s + TILE > nadir - water]
    assert len(holding) == 1                                         # only the centre tile
    c = holding[0]
    assert nadir - water - c >= 0.2 * TILE and c + TILE - (nadir + water) >= 0.2 * TILE
    assert starts[0] == 0 and starts[-1] == WIDTH - TILE
    assert min(seams(starts)) >= TILE * 0.25                         # 160 px everywhere


def test_unknown_altitude_still_keeps_the_band_off_the_side_tiles():
    starts = survey_mod._across_offsets(WIDTH, TILE, 0.25, None)
    nadir = WIDTH / 2
    assert sum(1 for s in starts if s < nadir + 80 and s + TILE > nadir - 80) == 1


# --- geometry across overlapping tiles ---------------------------------------

def _tiles(monkeypatch, tmp_path, n_pings=1400, overlap=0.25):
    monkeypatch.setattr(
        survey_mod, "waterfall", lambda chunk, **kw: np.full((len(chunk), WIDTH), 90, dtype=np.uint8)
    )
    pings = [ping(i) for i in range(n_pings)]
    step = survey_mod._along_track_res_m(pings)
    return list(survey_mod._iter_tiles(pings, tmp_path, "s", TILE, step, [], overlap=overlap))


def _place(frame, survey_row, survey_col):
    geom = _geometry_from_meta(frame.meta)
    return geotag_pixel(
        survey_col - frame.col_offset,
        survey_row - frame.ping_offset,
        frame.meta["latitude"],
        frame.meta["longitude"],
        geom,
        nadir_row=frame.meta["nadir_row"],
    )


def _metres(a, b):
    from pyproj import Geod

    return Geod(ellps="WGS84").inv(a[1], a[0], b[1], b[0])[2]


@pytest.mark.parametrize("survey_px", [(700, 400), (700, 1700), (500, 300), (900, 1250)])
def test_every_tile_that_holds_an_object_puts_it_in_the_same_place(monkeypatch, tmp_path, survey_px):
    """Each tile has its OWN fix ping, nadir row and nadir column, all derived
    from its offsets. If any of the three were off, overlapping tiles would
    place one object at two positions and the map would show two pins."""
    row, col = survey_px
    frames = [f for f in _tiles(monkeypatch, tmp_path)
              if f.ping_offset <= row < f.ping_offset + TILE and f.col_offset <= col < f.col_offset + TILE]
    assert len(frames) >= 2, "the point should sit in an overlap"
    spots = [_place(f, row, col) for f in frames]
    assert all(s is not None for s in spots)
    for s in spots[1:]:
        assert _metres(spots[0], s) < 0.5        # 2.5 m pings; this is rounding


def test_frames_carry_their_survey_offsets_and_ids_encode_them(monkeypatch, tmp_path):
    for f in _tiles(monkeypatch, tmp_path):
        assert merge.frame_offsets(f.frame_id) == (f.ping_offset, f.col_offset)
        assert f.meta["nadir_col"] == WIDTH / 2 - f.col_offset


# --- the merge rule ------------------------------------------------------------

def det(cls="debris", conf=0.5, bbox=(100, 100, 40, 40), notes="", did=None):
    return {
        "detection_id": did or "D-%08X" % (abs(hash((cls, conf, tuple(bbox), notes))) % 16**8),
        "class": cls,
        "raw_score": conf,
        "calibrated_confidence": conf,
        "uncertainty": "medium",
        "bbox": list(bbox),
        "mask": None,
        "review_only": cls == "ghost_net",
        "latitude": None,
        "longitude": None,
        "position_error_m": None,
        "localization": "none",
        "dimensions": {"width": None, "length": None, "status": "unavailable"},
        "model_version": "test",
        "evidence_summary": {"artificial_verification": "positive", "shadow_context": "x", "notes": notes},
    }


def frame(fid, *dets):
    return {"survey_id": "s", "frame_id": fid, "detections": list(dets), "warnings": [],
            "provenance": {}, "contract_version": "1.3.0", "frame_position": None}


# Two tiles 480 px apart across-track: survey column = col_offset + x.
A, B = "s__p000000__x00000", "s__p000000__x00480"
OFFS = [(0, 0), (0, 480)]


def test_one_object_seen_from_two_tiles_becomes_one_detection_keeping_the_best():
    frames = [frame(A, det(conf=0.41, bbox=(560, 200, 40, 40), did="D-AAAAAAAA")),
              frame(B, det(conf=0.55, bbox=(81, 202, 40, 38), did="D-BBBBBBBB"))]
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 1
    assert frames[0]["detections"] == []
    kept = frames[1]["detections"][0]
    assert kept["detection_id"] == "D-BBBBBBBB"
    # never silent: the survivor names what it absorbed, the loser's frame says where it went
    assert "D-AAAAAAAA" in kept["evidence_summary"]["notes"]
    assert any("D-AAAAAAAA" in w and "D-BBBBBBBB" in w for w in frames[0]["warnings"])
    for f in frames:
        assert validate(f) == []


def test_a_clipped_sighting_inside_the_whole_one_is_merged():
    """Tile A cuts the object at its right border and sees 30 px of it; tile B
    sees all 120. IoU is 0.25 -- below threshold -- but the clipped box lies
    entirely inside the whole one."""
    frames = [frame(A, det(conf=0.33, bbox=(610, 200, 30, 40))),
              frame(B, det(conf=0.47, bbox=(130, 200, 120, 40)))]
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 1
    assert len(frames[1]["detections"]) == 1


def test_different_classes_in_the_same_place_are_both_kept():
    frames = [frame(A, det(cls="debris", bbox=(560, 200, 40, 40))),
              frame(B, det(cls="ghost_net", bbox=(80, 200, 40, 40)))]
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 0
    assert sum(len(f["detections"]) for f in frames) == 2


def test_different_detector_classes_under_one_contract_class_are_both_kept():
    """A wreck and an aircraft both report as debris; one tile calling it each
    is a disagreement for a reviewer, not a duplicate to hide."""
    frames = [frame(A, det(bbox=(560, 200, 40, 40), notes="detector class: wreck")),
              frame(B, det(bbox=(80, 200, 40, 40), notes="detector class: plane"))]
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 0


def test_same_class_far_apart_is_not_merged():
    frames = [frame(A, det(bbox=(500, 200, 40, 40))),
              frame(B, det(bbox=(80, 300, 40, 40)))]          # survey (560, 300): 100 px away
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 0


def test_neighbouring_pots_just_over_the_centre_distance_stay_two():
    """A rival pipeline merges at 50 px. Pots in a string sit closer than that,
    and merging two real pots is a lost detection."""
    frames = [frame(A, det(bbox=(560, 200, 16, 16))),
              frame(B, det(bbox=(80 + 30, 200, 16, 16)))]     # 30 px apart, not touching
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 0


def test_two_boxes_in_one_frame_are_never_merged_with_each_other():
    frames = [frame(A, det(bbox=(100, 100, 40, 40)), det(bbox=(105, 102, 40, 40)))]
    assert merge.merge_survey_frames(frames, [(0, 0)], SETTINGS) == 0
    assert len(frames[0]["detections"]) == 2


def test_a_survivor_absorbs_at_most_one_sighting_per_frame():
    """Two overlapping pot boxes the detector kept apart in tile B must not
    both vanish into tile A's sighting -- that would be a second NMS."""
    frames = [frame(A, det(conf=0.6, bbox=(560, 200, 40, 40))),
              frame(B, det(conf=0.4, bbox=(80, 200, 40, 40)), det(conf=0.35, bbox=(85, 205, 30, 30)))]
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 1
    assert len(frames[0]["detections"]) == 1 and len(frames[1]["detections"]) == 1


def test_a_survivor_keeps_its_own_mask_unchanged():
    m = [[565, 205], [595, 205], [595, 235]]
    a = det(cls="ghost_net", conf=0.9, bbox=(560, 200, 40, 40))
    a["mask"] = m
    b = det(cls="ghost_net", conf=0.8, bbox=(80, 200, 40, 40))
    b["mask"] = [[85, 205], [115, 205], [115, 235]]
    frames = [frame(A, a), frame(B, b)]
    assert merge.merge_survey_frames(frames, OFFS, SETTINGS) == 1
    assert frames[0]["detections"][0]["mask"] == m


def test_a_tie_goes_to_the_sighting_further_from_its_tile_border():
    frames = [frame(A, det(conf=0.5, bbox=(598, 200, 40, 40), did="D-EDGE0000")),
              frame(B, det(conf=0.5, bbox=(118, 200, 40, 40), did="D-INNER000"))]
    merge.merge_survey_frames(frames, OFFS, SETTINGS)
    assert [d["detection_id"] for f in frames for d in f["detections"]] == ["D-INNER000"]


def test_the_incremental_index_ends_where_the_batch_merge_does():
    """The web backend decides each detection as it arrives, in frame order;
    whatever the order, the survivor must be the best sighting."""
    def s(frame_key, score, box):
        return merge.Sighting(ref=frame_key, frame_key=frame_key, cls="debris", det_cls="debris",
                              score=score, box=box)

    idx = merge.SeamIndex(SETTINGS)
    first, loser = idx.offer(s("A", 0.4, (560, 200, 600, 240)))
    assert loser is None
    survivor, loser = idx.offer(s("B", 0.6, (561, 201, 601, 241)))
    assert survivor.frame_key == "B" and loser.frame_key == "A"
    survivor, loser = idx.offer(s("C", 0.5, (559, 199, 599, 239)))
    assert survivor.frame_key == "B" and loser.frame_key == "C"
    assert sorted(x.frame_key for x in survivor.absorbed) == ["A", "C"]


def test_frame_offsets_ignore_frames_the_tiler_did_not_name():
    assert merge.frame_offsets("upload_0001") is None
    assert merge.frame_offsets(None) is None
    assert merge.frame_offsets("line__p000450__x01408") == (450, 1408)


# --- end to end ------------------------------------------------------------------

def test_detect_survey_reports_a_planted_object_once(monkeypatch, tmp_path):
    """An object at survey (row 700, col 560) lies in two row-tiles and two
    column-tiles at 25 % overlap -- four sightings. One detection must come
    out, with the other three named."""
    pings = [ping(i) for i in range(1400)]

    class Hdr:
        sonar_name = "x"

    monkeypatch.setattr(survey_mod, "read_file_header", lambda p: Hdr())
    monkeypatch.setattr(survey_mod, "iter_pings", lambda p, **kw: iter(pings))
    monkeypatch.setattr(
        survey_mod, "waterfall", lambda chunk, **kw: np.full((len(chunk), WIDTH), 90, dtype=np.uint8)
    )
    obj = (700, 560, 40, 40)                      # row, col, h, w in survey pixels

    def fake_detect(image_path, meta, settings):
        r0, c0 = merge.frame_offsets(meta["frame_id"])
        payload = frame(meta["frame_id"])
        r, c, h, w = obj
        if r0 <= r and r + h <= r0 + TILE and c0 <= c and c + w <= c0 + TILE:
            # confidence varies with position in the tile, as a real detector's does
            payload["detections"].append(
                det(conf=round(0.4 + (c - c0) / 10000, 4), bbox=(c - c0, r - r0, w, h)))
        return payload

    monkeypatch.setattr(survey_mod, "detect", fake_detect)
    s = replace(SETTINGS, tile_overlap=0.25)
    r = survey_mod.detect_survey("line.xtf", out_dir=tmp_path / "f", settings=s)
    found = [d for f in r["frames"] for d in f["detections"]]
    assert len(found) == 1
    assert r["seam_duplicates_merged"] >= 1
    assert any("merged" in w for w in r["warnings"])
    assert found[0]["calibrated_confidence"] == max(
        0.4 + (560 - c0) / 10000 for c0 in survey_mod._across_offsets(WIDTH, TILE, 0.25, 7.8 / (99.8 / SAMPLES))
        if c0 <= 560 and 600 <= c0 + TILE
    )

    off = survey_mod.detect_survey("line.xtf", out_dir=tmp_path / "g", settings=replace(s, seam_merge=False))
    assert sum(len(f["detections"]) for f in off["frames"]) > 1
    assert off["seam_duplicates_merged"] == 0


def test_overlap_is_off_by_default_and_the_environment_can_turn_it_on(monkeypatch):
    monkeypatch.delenv("GHOSTNET_TILE_OVERLAP", raising=False)
    assert Settings(weights_path=Path("x")).tile_overlap == 0.0
    monkeypatch.setenv("GHOSTNET_TILE_OVERLAP", "0.25")
    assert Settings(weights_path=Path("x")).tile_overlap == 0.25
    monkeypatch.setenv("GHOSTNET_TILE_OVERLAP", "a quarter")      # a typo must not stop the server
    assert Settings(weights_path=Path("x")).tile_overlap == 0.0


def test_zero_overlap_is_the_original_tiling():
    from ghostnet.survey import _across_offsets, _offsets
    assert _across_offsets(2048, 640, 0.0) == [0, 640, 1280, 1408]
    assert _offsets(6039, 640, 0.0)[:3] == [0, 640, 1280]
