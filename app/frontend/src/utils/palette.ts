/* =============================================================================
 * The Atlantic palette, for the places Tailwind cannot reach.
 *
 * Most of the console is coloured through utility classes and tailwind.config.ts
 * is the single source of truth for those. But Leaflet builds its markers from
 * HTML strings, three.js wants numbers, and SVG gradients want literal hex --
 * none of which a class can touch. Those used to hold hard-coded values
 * (#22d3ee and friends), which is how a retheme leaves a trail of the old
 * accent behind in exactly the places people look hardest: the map pins, the
 * chart line, the vessel.
 *
 * These constants are the same four hexes and the same derived ladder as
 * tailwind.config.ts and globals.css. If one of the three changes, all three
 * change.
 * ========================================================================== */

export const ATLANTIC = "#0F4B70";
export const SKY = "#C4F8FF";
export const IMPERIAL = "#021F94";
export const PAPER = "#F5F2F3";

/** The alpha ladder, flattened over paper. The mid steps are darkened from
 *  the mockup's alphas so they clear WCAG AA on the light canvas -- see the
 *  note in tailwind.config.ts. INK_4 is for marks, never for text. */
export const INK = "#15309C";
export const INK_2 = "#265C7D";
export const INK_3 = "#3D6C8A";
export const INK_4 = "#ABBDC9";
export const RULE = "#C7D1D9";

/** three.js wants numbers, not strings. */
export const ATLANTIC_HEX = 0x0f4b70;
export const SKY_HEX = 0xc4f8ff;
export const IMPERIAL_HEX = 0x021f94;
export const PAPER_HEX = 0xf5f2f3;

/**
 * Priority and status colours.
 *
 * These are the one part of the system that goes beyond the four hexes, and it
 * is deliberate: the Atlantic mockup contains four colours and no failure
 * state, but an operator has to be able to tell a critical detection from a low
 * one on a map without reading every label. They are pulled to the same deep,
 * low-luminance register as imperial so they read as part of the palette, and
 * they are dark enough to sit on the paper ground the console now uses -- the
 * previous set (#f87171, #facc15) was tuned for a black background and is
 * close to illegible on paper.
 */
export const ALERT = {
  critical: "#B3123C",
  high: "#AE5400",
  medium: "#8A6A00",
  low: INK_3,
  unknown: "#5B3FA8",
} as const;

export type AlertKey = keyof typeof ALERT;
