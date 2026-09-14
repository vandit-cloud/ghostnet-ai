import type { Config } from "tailwindcss";

/* =============================================================================
 * GhostNet-AI — "Atlantic" (UI direction v2, finalised 10 Sept 2026)
 *
 * FOUR HEXES, nothing else invented:
 *   #0F4B70 atlantic  — deep panels, sidebar, sonar water
 *   #C4F8FF sky       — tint surfaces on paper, bright ink on blue
 *   #021F94 imperial  — the one loud accent: ghost_net, primary, active nav
 *   #F5F2F3 paper     — canvas, and all text sitting on blue
 *
 * Everything else below is those four alpha-layered, then FLATTENED to a solid
 * hex. Flattening matters: Tailwind's `/40` opacity modifier only works on a
 * resolvable colour, and the existing markup leans on it heavily. An rgba()
 * token would silently drop every `border-x/70` in the app.
 *
 * THE CONSOLE INVERTS. It used to be light-on-dark (abyss canvas, cyan accent);
 * Atlantic is dark-on-light (paper canvas, imperial accent). The legacy scales
 * are therefore not deleted but REMAPPED IN REVERSE — the brightest text
 * becomes the darkest ink. That converts the long tail of ~900 colour classes
 * coherently in one edit, leaving only the places where the semantics really
 * changed (sidebar, top bar, panels, badges) to be rewritten by hand.
 * ========================================================================== */

// --- the four, and the alpha ladder flattened over paper --------------------
const ATLANTIC = "#0F4B70";
const SKY = "#C4F8FF";
const IMPERIAL = "#021F94";
const PAPER = "#F5F2F3";

/* The ink ladder, flattened over paper, with the CONTRAST RATIO each step
 * actually measures. The ladder originally followed the mockup's alphas
 * (.92/.80/.55/.32) and two of those steps do not survive the inversion: at
 * .55, ink-3 measures 2.81:1 on paper, and it is the colour of every table
 * header, timestamp and field label in the console -- 513 text nodes below AA.
 * On the old black ground the same alphas were fine; lightening the canvas
 * without re-deriving them is the trap. The two mid steps are darkened until
 * they pass, and the gap between them is kept wide enough to still read as a
 * hierarchy. ink-4 stays faint and is NON-TEXT ONLY -- rules, dashes and
 * disabled marks; anything that has to be read uses ink-3 or darker. */
const INK = "#15309C";    // imperial @ .92 — 9.76:1
const INK_2 = "#265C7D";  // atlantic @ .90 — 6.49:1, secondary copy
const INK_3 = "#3D6C8A";  // atlantic @ .80 — 5.09:1, labels and captions
const INK_4 = "#ABBDC9";  // atlantic @ .32 — 1.74:1, NON-TEXT marks only
const RULE = "#C7D1D9";   // atlantic @ .20 — the standard 1px rule
const RULE_2 = "#DEE1E6"; // atlantic @ .10 — the quiet divider inside a panel

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // ---- the palette proper, use these in new work -------------------
        paper: { DEFAULT: PAPER, deep: "#EFEBED", surround: "#DCD8DA" },
        atlantic: { DEFAULT: ATLANTIC, mid: "#0D4368", deep: "#0B3A58" },
        imperial: { DEFAULT: IMPERIAL, deep: "#01166B" },
        skytint: { DEFAULT: SKY, deep: "#A9EEF8" },
        ink: { DEFAULT: INK, 2: INK_2, 3: INK_3, 4: INK_4 },
        rule: { DEFAULT: RULE, 2: RULE_2 },

        // ---- legacy scales, remapped (see header) -------------------------
        // Surfaces: the darkest step was the page, so it becomes the paper.
        abyss: {
          950: PAPER,
          900: PAPER,
          800: "#EFEBED",
          700: "#E4E7EB",
          600: RULE,
          500: RULE_2,
        },
        // trench was the chrome (sidebar, top bar). Atlantic keeps the sidebar
        // blue, so this stays blue; the top bar is rewritten to paper by hand.
        trench: {
          950: ATLANTIC,
          900: ATLANTIC,
          800: "#12547E",
          700: "#16608F",
        },
        teal: { glass: ATLANTIC, deep: "#0C3A57" },
        /* cyan-accent was THE accent (211 uses) and imperial is its replacement.
         *
         * THE WHOLE RAMP IS LISTED, not just the keys in use. `theme.extend`
         * MERGES with Tailwind's stock palette, so any step left out keeps its
         * stock value -- and `accent-cyan-500` on the map's replay scrubber was
         * therefore still painting Tailwind's #06b6d4 on a page that has no
         * cyan in it. A remap that only covers today's call sites leaks the old
         * accent the moment someone adds a shade nobody happened to use. */
        cyan: {
          50: SKY,
          100: SKY,
          200: "#A9EEF8",
          300: "#A9EEF8",
          400: ATLANTIC,
          500: IMPERIAL,
          600: IMPERIAL,
          700: IMPERIAL,
          800: "#01166B",
          900: "#01166B",
          950: "#01166B",
          accent: IMPERIAL,
          dim: ATLANTIC,
        },
        foam: { 500: ATLANTIC, 300: SKY },
        // Inverted ink ramp: slate-50 was the brightest text on black, so it is
        // now the darkest ink on paper. 311 of the 331 slate uses are text.
        slate: {
          50: INK,
          100: INK,
          200: INK_2,
          300: INK_2,
          400: INK_3,
          500: INK_3,
          600: INK_4,
          700: RULE,
          800: RULE_2,
          900: "#EFEBED",
          950: PAPER,
        },
        /* Status colours are the ONE place this file goes past the four hexes,
         * and it is a deliberate, flagged exception. The Atlantic mockup has no
         * failure state to copy — it contains literally four colours — but the
         * console has to let an operator tell a FAILED job from a COMPLETED one
         * without reading the label. These are pulled to the same deep, low-
         * luminance register as imperial so they read as part of the system and
         * stay legible as text on paper. Shape still carries the primary signal
         * (filled / outlined / dashed); colour is the secondary cue. */
        alert: {
          critical: "#B3123C",
          high: "#AE5400",   // 4.64:1 on paper; #B85C00 measured 4.13
          medium: "#8A6A00",
          low: INK_3,
          unknown: "#5B3FA8",
        },
        /* The one "good" state the app already used. Same reasoning as `alert`,
         * and the same whole-ramp rule as cyan above: emerald-400 was left to
         * stock and was painting #34d399 -- a mint green that belongs to no
         * part of this system -- on four screens. */
        emerald: {
          50: "#E3F0EC",
          100: "#C7E1D9",
          200: "#8FC3B3",
          300: "#16705A",
          400: "#16705A",
          500: "#16705A",
          600: "#125B49",
          700: "#0E4839",
          800: "#0B3729",
          900: "#08281E",
          950: "#051912",
        },
      },
      /* Atlantic's alpha ladder, as opacity STEPS.
       * Tailwind only emits an opacity modifier whose value is in this scale:
       * `text-paper/74` with 74 missing generates no rule at all and the element
       * silently falls back to inherited colour -- which on the blue rail meant
       * ink-on-atlantic, unreadable, with nothing in the build to show for it.
       * These are the four alphas the palette actually uses. */
      opacity: {
        22: "0.22",
        32: "0.32",
        42: "0.42",
        55: "0.55",
        62: "0.62",
        74: "0.74",
      },
      /* Atlantic is editorial and square: 1px rules, flat fills, no glass and
       * no glow. Zeroing the radius scale converts every rounded-2xl in the
       * markup at once. `full` survives for genuine circles (status dots). */
      borderRadius: {
        none: "0",
        sm: "0",
        DEFAULT: "0",
        md: "0",
        lg: "0",
        xl: "0",
        "2xl": "0",
        "3xl": "0",
        full: "9999px",
      },
      /* The glow tokens are kept by NAME so nothing breaks, but a glow is the
       * opposite of this direction. They become a crisp 1px ring in the right
       * hue — the emphasis survives, the neon does not. */
      boxShadow: {
        "glow-cyan": `0 0 0 1px ${IMPERIAL}`,
        "glow-critical": "0 0 0 1px #B3123C",
        "glow-unknown": "0 0 0 1px #5B3FA8",
        panel: "none",
      },
      fontFamily: {
        // Monigue / Epoch are the licensed faces; Big Shoulders / Jost are the
        // agreed fallbacks and what next/font actually serves. Listing the real
        // names first means a machine with them installed gets them.
        sans: ["var(--font-ui)", "Epoch", "Jost", "Archivo", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Monigue", "Glinken", "Big Shoulders Display", "Oswald", "sans-serif"],
        mono: ["var(--font-mono)", "IBM Plex Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
