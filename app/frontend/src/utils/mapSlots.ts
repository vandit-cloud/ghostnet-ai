/* =============================================================================
 * Where things are allowed to sit on top of a map.
 *
 * A Leaflet map has four corners and two sets of tenants competing for them:
 * Leaflet's own controls (zoom, scale bar, attribution) and whatever the page
 * wants to overlay (a legend, a counter, a replay button). Neither side knows
 * about the other, so without a shared convention both land on the same
 * coordinates and the one with the higher z-index silently hides the other --
 * which is exactly what happened: the survey counter covered the cursor
 * read-out, and the Legend button covered the scale bar. Nothing errors, the
 * hidden control just stops existing as far as the operator is concerned, and
 * a scale bar you cannot see on a map you are judging distances on is worse
 * than no scale bar, because you do not know it is missing.
 *
 * So the corners are assigned once, here, and every map in the app uses these
 * constants rather than its own `absolute bottom-3 left-3`.
 *
 * LEAFLET OWNS (do not overlap; it positions these itself):
 *   bottom-left   scale bar          ~0-26px up from the bottom
 *   bottom-right  attribution        ~0-20px up from the bottom
 *
 * MapView OWNS:
 *   top-left      cursor read-out    12-56px down from the top
 *   top-right     north arrow, and the basemap switcher below it
 *
 * CALLERS GET the three slots below, which clear all of the above. They are
 * plain strings in their own module -- not exported from MapView -- because
 * every consumer imports MapView through `dynamic(..., { ssr: false })` to keep
 * Leaflet out of the server bundle, and a static import of a constant from
 * that same module would drag Leaflet back into the page chunk and quietly
 * undo it.
 * ========================================================================== */

/** Below MapView's cursor read-out. */
export const MAP_SLOT_TOP_LEFT = "absolute left-3 top-16 z-[1000]";

/** Above Leaflet's scale bar. */
export const MAP_SLOT_BOTTOM_LEFT = "absolute left-3 bottom-9 z-[1000]";

/** Above Leaflet's attribution strip. */
export const MAP_SLOT_BOTTOM_RIGHT = "absolute right-3 bottom-9 z-[1000]";
