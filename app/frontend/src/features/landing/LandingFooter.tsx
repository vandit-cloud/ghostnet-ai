/* The closing CTA band and the footer.
 *
 * Several links below point at work that is real but not yet public — the
 * repository is private until the submission, and the technical PDF is
 * generated from docs/. They are left as "#" rather than pointed at a 404,
 * which is what the demo does and is the honest state of them. The links that
 * DO resolve — the console, the review queue, the map — are wired. */

const PRODUCT = [
  ["Detections", "#detection"],
  ["Outputs", "#outputs"],
  ["Survey console", "/app/dashboard"],
  ["Review queue", "/app/review"],
  // The reference lists GeoJSON export here, and the 05 spec table two
  // screens above still promises "GeoJSON polygons and CSV". Dropping it from
  // the footer to gain a link that resolves was the wrong trade; exports live
  // on the reports screen, so it can be both.
  ["GeoJSON export", "/app/reports"],
];

const METHOD = [
  ["Pipeline", "#method"],
  ["Evidence", "#evidence"],
  ["Specification", "#spec"],
  ["Calibration", "#outputs"],
  ["Known limits", "#evidence"],
];

const PROJECT = [
  ["Repository", "#"],
  ["Technical PDF", "#"],
  ["Dataset notes", "#"],
  ["Changelog", "#"],
  ["Team", "#"],
];

const CONTACT = [
  ["Enquiries", "#"],
  ["Report a find", "#"],
  ["Data partnerships", "#"],
  ["Press", "#"],
];

function Column({ title, links }: { title: string; links: string[][] }) {
  return (
    <div>
      <h4>{title}</h4>
      <ul>
        {links.map(([label, href]) => (
          <li key={label}>
            <a href={href}>{label}</a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CtaBand() {
  return (
    <section className="cta-band">
      <div className="kicker" style={{ color: "var(--onblue-2)" }}>
        Smart India Hackathon · 18 September 2026
      </div>
      <h2 className="h2">Open the console</h2>
      <p className="lede" style={{ color: "var(--onblue)" }}>
        Three deliverables, all public: the running demo, the repository behind it, and the
        technical write-up that shows the working.
      </p>
      <div className="row">
        <a className="btn btn-sky" href="/app/dashboard">
          <span>Live demo</span>
        </a>
        <a
          className="btn"
          style={{
            background: "transparent",
            color: "var(--paper)",
            borderColor: "rgba(245,242,243,.45)",
          }}
          href="#"
        >
          <span>Public repository</span>
        </a>
        <a
          className="btn"
          style={{
            background: "transparent",
            color: "var(--paper)",
            borderColor: "rgba(245,242,243,.45)",
          }}
          href="#"
        >
          <span>Technical PDF</span>
        </a>
      </div>
    </section>
  );
}

export function LandingFooter() {
  return (
    <footer className="foot">
      <div className="foot-grid">
        <div className="foot-brand">
          <div className="logo">
            Ghost<i>Net</i>-AI
          </div>
          <p>
            Finding abandoned fishing gear on the seabed from side-scan sonar, and refusing to
            pretend a machine can sign it off.
          </p>
          <span className="badge">Problem statement SIH26057</span>
        </div>
        <Column title="Product" links={PRODUCT} />
        <Column title="Method" links={METHOD} />
        <Column title="Project" links={PROJECT} />
        <Column title="Contact" links={CONTACT} />
      </div>

      <p className="disclaimer">
        <b>On the numbers.</b> Every figure on this page is measured from the current build, not
        projected. Detections are <b>review_only</b>: they are candidate findings with an honest
        position error, not confirmed locations of gear, and they are not a navigational product.
        Prior-art comparison refers to published work by the Microsoft AI for Good Lab and WWF
        Germany (September 2025); we reproduced its central finding independently and are in
        correspondence with its authors — this is not an endorsement or a partnership.
      </p>

      <div className="foot-base">
        <span>GhostNet-AI · SIH26057 · contract v1.2.0</span>
        <span>All detections review_only</span>
        <span className="sp">
          <a href="#">Privacy</a>
        </span>
        <span>
          <a href="#">Terms</a>
        </span>
        <span>
          <a href="#">Accessibility</a>
        </span>
        <span>
          <a href="#hero">Back to top ↑</a>
        </span>
      </div>
    </footer>
  );
}
