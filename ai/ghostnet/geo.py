"""Sonar geometry: slant range -> ground range -> WGS84 position.

This module exists because both master plans omit it. Grep confirms zero
mentions of 'nadir', 'water column' or 'ground range' anywhere in them, and
§27 never spells out the across-track offset. Without the conversions below,
every reported latitude/longitude is wrong by an amount that varies with
altitude -- largest near nadir, negligible at far range -- which silently
breaks the geotagging deliverable even when detection metrics look excellent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pyproj import Geod

# WGS84. Using a proper ellipsoid rather than flat trigonometry matters:
# a degree of longitude shrinks by cos(latitude), ~3.5% off India's coast.
_GEOD = Geod(ellps="WGS84")


@dataclass
class SonarGeometry:
    """Per-frame acquisition parameters needed to place a pixel on the earth.

    All distances in metres, angles in degrees.
    """

    nadir_col: float            # image column directly beneath the towfish
    range_resolution_m: float   # metres of SLANT range per pixel, across-track
    altitude_m: float           # towfish height above the seabed
    heading_deg: float          # vessel/towfish course over ground, 0 = north
    layback_m: float = 0.0      # horizontal tow-cable offset behind the GPS antenna
    along_track_res_m: float | None = None  # metres per pixel row, if known


def ground_range_from_slant(slant_range_m: float, altitude_m: float) -> float | None:
    """Convert slant range to horizontal ground range.

    The sonar measures the hypotenuse from towfish to target; the map needs the
    horizontal leg. Returns None inside the water column, where the geometry has
    no solution and any 'position' would be invented.
    """
    if slant_range_m <= altitude_m:
        return None
    return math.sqrt(slant_range_m**2 - altitude_m**2)


def water_column_width_px(geom: SonarGeometry) -> float:
    """Half-width, in pixels, of the unusable water-column band around nadir."""
    if geom.range_resolution_m <= 0:
        return 0.0
    return geom.altitude_m / geom.range_resolution_m


def pixel_to_ground_offset(col: float, geom: SonarGeometry) -> tuple[float | None, int]:
    """Across-track ground distance for an image column.

    Returns (ground_range_m, side) where side is -1 for port, +1 for starboard,
    and ground_range_m is None if the column falls inside the water column.
    """
    delta_px = col - geom.nadir_col
    side = -1 if delta_px < 0 else 1
    slant_m = abs(delta_px) * geom.range_resolution_m
    return ground_range_from_slant(slant_m, geom.altitude_m), side


def geotag_pixel(
    col: float,
    row: float,
    fish_lat: float,
    fish_lon: float,
    geom: SonarGeometry,
    nadir_row: float | None = None,
) -> tuple[float, float] | None:
    """Place an image pixel on the WGS84 ellipsoid.

    Across-track: perpendicular to heading, port = heading - 90, starboard = +90.
    Along-track:  offset from the frame's reference row, plus layback applied
    astern (heading + 180), because the towfish trails the GPS antenna.
    """
    ground_m, side = pixel_to_ground_offset(col, geom)
    if ground_m is None:
        return None

    lon, lat = fish_lon, fish_lat

    # 1. layback: the fish is behind the antenna, along the reciprocal heading
    if geom.layback_m:
        lon, lat, _ = _GEOD.fwd(lon, lat, (geom.heading_deg + 180.0) % 360.0, geom.layback_m)

    # 2. along-track, only when we know the row scale
    if geom.along_track_res_m and nadir_row is not None:
        along_m = (row - nadir_row) * geom.along_track_res_m
        if along_m:
            az = geom.heading_deg if along_m > 0 else (geom.heading_deg + 180.0) % 360.0
            lon, lat, _ = _GEOD.fwd(lon, lat, az % 360.0, abs(along_m))

    # 3. across-track, perpendicular to heading
    across_az = (geom.heading_deg + side * 90.0) % 360.0
    lon, lat, _ = _GEOD.fwd(lon, lat, across_az, ground_m)
    return lat, lon


def position_error_m(
    geom: SonarGeometry,
    gps_error_m: float = 3.0,
    heading_error_deg: float = 2.0,
    altitude_error_m: float = 0.5,
    ground_range_m: float = 0.0,
) -> float:
    """A defensible error radius rather than a claim of exact position (B4).

    Combines GPS scatter, heading error swung through the across-track lever
    arm, and altitude uncertainty propagated through the slant->ground step.
    Root-sum-square, because the sources are independent.
    """
    heading_term = ground_range_m * math.radians(heading_error_deg)
    slant_m = math.hypot(ground_range_m, geom.altitude_m)
    altitude_term = (
        altitude_error_m * geom.altitude_m / ground_range_m if ground_range_m > 1e-6 else altitude_error_m
    )
    layback_term = 0.10 * geom.layback_m  # cable geometry is rarely better than ~10%
    _ = slant_m
    return math.sqrt(gps_error_m**2 + heading_term**2 + altitude_term**2 + layback_term**2)
