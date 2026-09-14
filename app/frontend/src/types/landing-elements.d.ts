/* =============================================================================
 * `<k>` and `<v>` — the key/value pair used throughout the landing page.
 *
 * These are not HTML elements. The landing design uses them as a two-part
 * inline unit (a mono uppercase label against an imperial value) in the
 * detection readout, the card footers and the spec table, and the ported
 * stylesheet targets them BY TAG. Browsers render an unknown tag as an
 * ordinary inline box and style it happily, which is why the demo could use
 * them; TypeScript is the only thing that objects.
 *
 * Declaring them here rather than rewriting them as <span className="k"> keeps
 * the markup and the generated CSS in step. scripts/port_landing_css.py copies
 * those selectors straight from the demo, so a rename here would be undone by
 * the next port.
 * ========================================================================== */
declare namespace JSX {
  interface IntrinsicElements {
    k: React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>;
    v: React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>;
  }
}
