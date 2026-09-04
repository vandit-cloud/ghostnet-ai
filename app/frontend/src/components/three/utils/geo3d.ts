const METERS_PER_DEGREE_LAT = 111_320;

/**
 * Small-area equirectangular tangent-plane projection (lat/lon -> local meters).
 * Standard technique for visualizing a single survey's real coordinates in a
 * local 3D scene - depth/Y is never set from this, so it makes no claim about
 * measured bathymetry (spec: never fake seafloor data).
 */
export function projectLatLon(
  originLat: number,
  originLon: number,
  lat: number,
  lon: number
): { x: number; z: number } {
  const metersPerDegreeLon = METERS_PER_DEGREE_LAT * Math.cos((originLat * Math.PI) / 180);
  return {
    x: (lon - originLon) * metersPerDegreeLon,
    z: -(lat - originLat) * METERS_PER_DEGREE_LAT,
  };
}

export interface LocalBounds {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}

export function computeBounds(points: { x: number; z: number }[]): LocalBounds | null {
  if (points.length === 0) return null;
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const p of points) {
    minX = Math.min(minX, p.x);
    maxX = Math.max(maxX, p.x);
    minZ = Math.min(minZ, p.z);
    maxZ = Math.max(maxZ, p.z);
  }
  return { minX, maxX, minZ, maxZ };
}
