"""Geotagging tests -- the deliverable that had none.

Geolocation is one of four named deliverables and, until this file, the only
one with no automated coverage. It is also the one whose failures are hardest
to notice: a wrong position is still a number, still plots on a map, and still
looks like a result. A detector that misses a wreck is obviously broken; a
geotagger that puts it 40 m to port is not.

So these assert PHYSICS rather than stored values -- directions, monotonicity,
and the cases where the honest answer is None. A regression test pinned to a
lat/lon that was never independently checked would only guarantee the same
answer forever, right or wrong.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from ghostnet.geo import (  # noqa: E402
    SonarGeometry, geotag_pixel, ground_range_from_slant,
    pixel_to_ground_offset, position_error_m,
)

LAT, LON = 18.9220, 72.8347          # off Mumbai, as in the example metadata


def geom(**over) -> SonarGeometry:
    kw = dict(nadir_col=500.0, range_resolution_m=0.05, altitude_m=3.0,
              heading_deg=0.0, layback_m=0.0, along_track_res_m=0.05)
    kw.update(over)
    return SonarGeometry(**kw)


# --- slant to ground -------------------------------------------------------

def test_water_column_has_no_solution():
    """Inside the water column there is no seabed return, so there is no
    position. Returning a number here would be inventing one."""
    assert ground_range_from_slant(2.0, altitude_m=3.0) is None
    assert ground_range_from_slant(3.0, altitude_m=3.0) is None


def test_ground_range_is_the_horizontal_leg():
    # 3-4-5 triangle: slant 5, altitude 3 -> ground 4.
    assert ground_range_from_slant(5.0, 3.0) == pytest.approx(4.0)


def test_slant_correction_matters_most_near_nadir():
    """The reason this module exists: ignoring it is worst close in, which is
    exactly where an operator assumes the position is best."""
    g = geom()
    near, _ = pixel_to_ground_offset(g.nadir_col + 100, g)     # slant 5 m
    far, _ = pixel_to_ground_offset(g.nadir_col + 2000, g)     # slant 100 m
    assert (100 * g.range_resolution_m - near) / near > 0.20   # >20% error near
    assert (2000 * g.range_resolution_m - far) / far < 0.01    # <1% error far


def test_side_is_port_or_starboard_about_nadir():
    g = geom()
    assert pixel_to_ground_offset(g.nadir_col - 500, g)[1] == -1
    assert pixel_to_ground_offset(g.nadir_col + 500, g)[1] == +1


# --- placing a pixel -------------------------------------------------------

def test_starboard_target_lands_east_when_heading_north():
    """Heading 000, starboard is due east: longitude increases, latitude does
    not move. This is the test that catches a sign flip."""
    g = geom(heading_deg=0.0, along_track_res_m=None)
    lat, lon = geotag_pixel(g.nadir_col + 1000, 0, LAT, LON, g)
    assert lon > LON
    assert lat == pytest.approx(LAT, abs=1e-6)


def test_port_target_lands_west_when_heading_north():
    g = geom(heading_deg=0.0, along_track_res_m=None)
    lat, lon = geotag_pixel(g.nadir_col - 1000, 0, LAT, LON, g)
    assert lon < LON
    assert lat == pytest.approx(LAT, abs=1e-6)


def test_heading_rotates_the_across_track_offset():
    """Same pixel, vessel steaming east: starboard is now due south."""
    g = geom(heading_deg=90.0, along_track_res_m=None)
    lat, lon = geotag_pixel(g.nadir_col + 1000, 0, LAT, LON, g)
    assert lat < LAT
    assert lon == pytest.approx(LON, abs=1e-6)


def test_layback_places_the_fish_astern():
    """The towfish trails the GPS antenna, so heading north the fish is SOUTH
    of the fix. Getting this backwards doubles the error instead of removing
    it."""
    g = geom(heading_deg=0.0, layback_m=50.0, along_track_res_m=None)
    lat, _ = geotag_pixel(g.nadir_col + 1000, 0, LAT, LON, g)
    assert lat < LAT


def test_along_track_row_offset_follows_heading():
    g = geom(heading_deg=0.0)
    ahead, _ = geotag_pixel(g.nadir_col + 1000, 400, LAT, LON, g, nadir_row=0)
    behind, _ = geotag_pixel(g.nadir_col + 1000, -400, LAT, LON, g, nadir_row=0)
    assert ahead > LAT > behind


def test_no_position_inside_the_water_column():
    g = geom()
    assert geotag_pixel(g.nadir_col + 10, 0, LAT, LON, g) is None


def test_distance_matches_the_computed_ground_range():
    """End to end: the placed point should sit at the ground range the geometry
    says, not the slant range."""
    from pyproj import Geod

    g = geom(heading_deg=0.0, along_track_res_m=None)
    col = g.nadir_col + 2000
    ground_m, _ = pixel_to_ground_offset(col, g)
    lat, lon = geotag_pixel(col, 0, LAT, LON, g)
    _, _, dist = Geod(ellps="WGS84").inv(LON, LAT, lon, lat)
    assert dist == pytest.approx(ground_m, rel=1e-6)


# --- the error radius ------------------------------------------------------

def test_error_grows_with_range_through_the_heading_lever():
    """A heading error swings a bigger arc further out, so a far detection is
    less well placed than a near one."""
    g = geom()
    assert position_error_m(g, ground_range_m=100.0) > position_error_m(g, ground_range_m=10.0)


def test_error_never_undercuts_gps_alone():
    """Whatever else is uncertain, the fix itself still is."""
    g = geom()
    assert position_error_m(g, gps_error_m=3.0, ground_range_m=0.0) >= 3.0


def test_layback_adds_uncertainty():
    """Cable geometry is never exactly known, so towing more cable is worse."""
    assert position_error_m(geom(layback_m=100.0), ground_range_m=50.0) > \
           position_error_m(geom(layback_m=0.0), ground_range_m=50.0)


def test_error_is_metres_not_degrees():
    """A guard against the classic unit slip -- 3 m must not become 3 degrees."""
    assert 1.0 < position_error_m(geom(), ground_range_m=30.0) < 100.0


def test_heading_error_term_is_radians():
    """2 degrees at 100 m is ~3.5 m, not 200 m. Feeding degrees straight into
    the arc length is a 57x overstatement and looks plausible in isolation."""
    g = geom()
    only_heading = math.sqrt(
        max(position_error_m(g, gps_error_m=0.0, altitude_error_m=0.0,
                             ground_range_m=100.0) ** 2, 0.0)
    )
    assert only_heading == pytest.approx(100.0 * math.radians(2.0), rel=0.05)
