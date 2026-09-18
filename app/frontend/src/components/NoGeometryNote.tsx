/* =============================================================================
 * Why the Geospatial Details and Sonar Quality panels are empty.
 *
 * They are not broken, and the values are not missing by accident. Both panels
 * are derived quantities, and both need the SAME four numbers, which live in a
 * .xtf file's ping headers and nowhere else:
 *
 *     nadir_col            the column directly beneath the towfish
 *     range_resolution_m   metres per PIXEL (not the swath width)
 *     altitude_m           towfish height ABOVE THE SEABED (not water depth)
 *     heading_deg          the tow direction
 *
 * ghostnet treats those four as all-or-nothing (see GEOMETRY_FIELDS in
 * app/services/ghostnet_adapter.py): with all four plus a lat/lon fix it
 * returns a position and metric dimensions; with any one absent it returns
 * neither, and says why in `warnings`. That refusal is the correct behaviour
 * and the adapter's docstring argues it at length -- a wrong altitude does not
 * degrade a position, it corrupts it, and "a plausible map that is lying" is
 * worse than an empty one for the operator who has to dispatch a boat.
 *
 * A .png or .jpg frame carries none of the four. So an image upload ALWAYS
 * produces exactly this state, and before this component the UI expressed that
 * as eight rows reading "Unavailable" with no indication of whether the survey
 * was misconfigured, the model had failed, or the data simply could not support
 * the answer. It was the third one every time.
 * ========================================================================== */

export function NoGeometryNote({ kind }: { kind: "geospatial" | "dimensions" }) {
  const what =
    kind === "geospatial"
      ? "This detection has no position"
      : "This detection has no metric size";

  const why =
    kind === "geospatial"
      ? "Placing a box on the map needs the towfish's altitude, heading, nadir column and range resolution, alongside a lat/lon fix."
      : "Converting a box measured in pixels into metres needs the range resolution — metres per pixel — from the sonar.";

  return (
    <div className="mt-3 border-t border-abyss-700 pt-3">
      <p className="text-sm text-slate-400">
        <span className="font-medium text-slate-300">{what}.</span> {why} Those
        values come from a survey&apos;s ping headers, which{" "}
        <span className="font-medium text-slate-300">
          .png and .jpg uploads do not carry
        </span>
        .
      </p>
      <p className="mt-2 text-sm text-slate-400">
        Re-ingest this survey as <span className="font-mono text-xs">.xtf</span>{" "}
        and both panels populate automatically. The model reports nothing here
        rather than estimating — an invented position would look identical to a
        measured one on the map.
      </p>
    </div>
  );
}
