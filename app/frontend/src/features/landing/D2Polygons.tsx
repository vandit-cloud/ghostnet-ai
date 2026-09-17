/* =============================================================================
 * The eleven ghost_net polygons annotated on D2 chip quanzhou_HN_005.
 *
 * These are the real annotations, in the chip's own 740x496 pixel space, copied
 * out of the labelme geometry -- not a redrawn approximation. The whole point
 * of the section they sit in is that eleven traced panels claim 17.4% of the
 * frame where one bounding box around the same find would claim 85%, and that
 * argument is only worth making if the shapes are the measured ones.
 *
 * Source: ghostnet-demo-src/d2_polys.svg.txt
 * ========================================================================== */
export function D2Polygons() {
  return (
    <svg
      className="chip-svg"
      viewBox="0 0 740 496"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      <path d="M171.7,476.2 L152.3,489.1 L84.9,376.5 L78.0,287.9 L135.0,119.1 L127.2,88.9 L155.3,79.4 L107.4,241.3 L94.0,305.6 L99.2,371.7 Z" />
      <path d="M81.5,34.1 L106.9,41.4 L56.0,191.2 L38.3,256.9 L24.5,284.1 L52.1,160.1 L81.5,67.3 Z" />
      <path d="M227.4,76.4 L242.5,90.2 L176.0,224.5 L152.7,303.9 L173.9,389.8 L220.9,482.7 L197.2,485.7 L136.7,326.4 L160.0,243.5 Z" />
      <path d="M275.3,96.7 L299.5,115.2 L238.2,251.7 L232.2,362.6 L292.2,452.4 L334.1,491.7 L297.4,493.5 L214.5,370.4 L220.9,252.1 L279.2,103.1 Z" />
      <path d="M340.1,122.6 L354.3,134.2 L291.7,284.9 L308.6,364.4 L363.8,452.9 L352.2,478.8 L297.8,369.1 L272.7,288.4 Z" />
      <path d="M427.3,83.7 L447.6,92.8 L357.4,271.1 L364.7,329.0 L382.4,377.3 L420.0,450.3 L389.8,440.4 L355.2,360.0 L347.9,265.1 Z" />
      <path d="M512.8,76.4 L524.0,86.3 L446.3,232.2 L426.5,280.2 L446.3,402.4 L431.6,408.0 L404.9,290.1 L457.1,180.9 Z" />
      <path d="M589.2,67.7 L600.0,79.4 L493.4,263.3 L497.3,330.7 L516.7,389.0 L496.8,380.3 L477.0,306.9 L492.5,238.3 Z" />
      <path d="M615.6,112.2 L630.7,106.2 L580.2,222.7 L556.0,278.9 L559.9,336.3 L556.9,359.2 L543.5,347.5 L543.9,258.6 Z" />
      <path d="M646.7,146.7 L659.6,138.1 L616.4,278.4 L622.5,338.9 L651.8,402.4 L666.1,424.0 L647.5,430.9 L608.2,351.8 L592.7,281.5 Z" />
      <path d="M703.7,414.9 L696.3,434.3 L656.2,344.1 L651.8,256.4 L669.1,140.3 L678.6,166.6 L667.4,264.2 L668.3,337.2 Z" />
    </svg>
  );
}
