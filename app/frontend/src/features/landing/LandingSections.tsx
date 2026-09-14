import Image from "next/image";

import { D2Polygons } from "./D2Polygons";

/* =============================================================================
 * Everything below the hero. These are server components: static copy, with no
 * reason to ship any of it to the client.
 *
 * ON THE NUMBERS. Every figure here is measured from the current build and has
 * a source in the repository -- 0.525 net recall and the 7.0% / 56.5% area pair
 * from docs/D2_SEGMENTATION_SUMMARY.md, the 73 chips and 425 polygons from the
 * D2 build report, the 62 real images from docs/DATA.md. If one of those
 * changes, it changes here too. Nothing on this page is projected.
 * ========================================================================== */

export function DetectionSection() {
  return (
    <section className="band grain" id="detection">
      <div className="kicker">01 — A detection, in full</div>
      <h2 className="h2">Eleven polygons, not one box</h2>
      <p className="lede">
        A real chip from the D2 set with the net polygons that are actually annotated on it — not a
        mockup. Eleven separate panels of gear, traced individually. One bounding box around the
        same find would have told a crew to sweep most of the frame.
      </p>
      <div className="detect-grid">
        <div>
          <div className="chipwrap">
            <span className="chiptag">D2 · quanzhou_HN_005</span>
            {/* Not next/image: the SVG overlay is positioned against this
                element's own box, and the polygons are in the chip's native
                740x496 space. An optimiser free to change the intrinsic size
                would slide the annotations off the gear they trace. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/demo/d2_chip.jpg"
              alt="Side-scan sonar chip with eleven annotated ghost net panels"
              width={740}
              height={496}
            />
            <D2Polygons />
          </div>
          <div className="chipcap">
            Real side-scan imagery · geometry unretouched · tinted to the palette
          </div>
        </div>
        <div className="readout">
          <div className="rrow">
            <k>Class</k>
            <v>ghost_net</v>
          </div>
          <div className="rrow">
            <k>Polygons on this chip</k>
            <v>11</v>
          </div>
          <div className="rrow big">
            <k>Area claimed</k>
            <v>17.4 %</v>
          </div>
          <div className="rrow big">
            <k>A naive box would claim</k>
            <v>85.0 %</v>
          </div>
          <div className="rrow">
            <k>Net recall · D2</k>
            <v>0.525</v>
          </div>
          <div className="rrow">
            <k>Dataset</k>
            <v>73 chips · 425 polygons</v>
          </div>
          <div className="rrow">
            <k>Status</k>
            <v>review_only</v>
          </div>
          <p className="rnote">
            Both percentages are measured from the polygons beside them, not averaged over the
            dataset. The gap between them is the entire argument: it is the water a crew does not
            have to sweep.
          </p>
          <div className="gate">
            <p>Nothing leaves this queue until a human signs it off.</p>
            <div className="row">
              <a className="btn btn-primary" href="/app/review">
                <span>Accept</span>
              </a>
              <a className="btn btn-line" href="/app/review">
                <span>Reject</span>
              </a>
              <a className="link" href="/app/review">
                Escalate
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function OutputsSection() {
  return (
    <section className="band grain" id="outputs">
      <div className="kicker">02 — What comes out</div>
      <h2 className="h2">A polygon, a number, and a caveat</h2>
      <p className="lede">
        A pin on a map tells a boat crew nothing about how much water to sweep. Everything
        GhostNet-AI emits is shaped so the next person in the chain can act on it — or refuse it.
      </p>
      <div className="grid3">
        <div className="card">
          <span className="n">Geometry</span>
          <h3>
            Polygons,
            <br />
            not pins
          </h3>
          <p>
            D2 predicts the extent of the gear, not just its presence. Across 73 chips the model
            claims 7.0% of the frame instead of the 56.5% a naive box would — the difference between
            a search area and a shrug.
          </p>
          <div className="cardfoot">
            <k>Area claimed</k>
            <v>
              7.0 % <s>vs 56.5 %</s>
            </v>
          </div>
        </div>
        <div className="card">
          <span className="n">Confidence</span>
          <h3>
            Calibrated,
            <br />
            not raw
          </h3>
          <p>
            A raw softmax score is not a probability. Scores are calibrated so 0.9 means roughly
            nine in ten — and the app and the model deliberately speak two different score scales so
            neither can silently drift into the other.
          </p>
          <div className="cardfoot">
            <k>Reliability</k>
            <v>
              p ≈ 0.91 <s>calibrated</s>
            </v>
          </div>
        </div>
        <div className="card">
          <span className="n">Accountability</span>
          <h3>
            review_only
            <br />
            by default
          </h3>
          <p>
            Nothing is presented as a confirmed find. Every detection carries an honest position
            error and stays flagged for human sign-off, because a false positive costs a vessel a
            day and a false negative costs the seabed a decade.
          </p>
          <div className="cardfoot">
            <k>Verification</k>
            <v>
              human_flag <s>required</s>
            </v>
          </div>
        </div>
      </div>
    </section>
  );
}

export function MethodSection() {
  return (
    <section className="band blue" id="method">
      <div className="kicker">03 — How it decides</div>
      <h2 className="h2">Sonar in, geometry out</h2>
      <p className="lede">
        Five stages, each auditable on its own. The transform rule is absolute: anything applied in
        training is applied at inference, or it is applied in neither.
      </p>
      <div className="steps">
        <div className="step">
          <span>Stage 01</span>
          <b>Ingest</b>
          <p>Raw side-scan waterfall, despeckled and reduced to 8-bit, across-track 0–120 m.</p>
        </div>
        <div className="step">
          <span>Stage 02</span>
          <b>Chip</b>
          <p>
            The track is cut into overlapping chips so gear straddling a boundary is never lost to
            it.
          </p>
        </div>
        <div className="step">
          <span>Stage 03</span>
          <b>Segment</b>
          <p>
            The D2 model returns per-pixel extent, taking net recall from 0.000 to 0.525 as
            polygons.
          </p>
        </div>
        <div className="step">
          <span>Stage 04</span>
          <b>Calibrate</b>
          <p>Scores are mapped to real probabilities and a position error is attached to each.</p>
        </div>
        <div className="step">
          <span>Stage 05</span>
          <b>Review</b>
          <p>Everything lands in the console as review_only until a human signs it off.</p>
        </div>
      </div>
    </section>
  );
}

export function EvidenceSection() {
  return (
    <section className="band grain" id="evidence">
      <div className="kicker">04 — Where it stands</div>
      <h2 className="h2">Measured against the state of the art</h2>
      <div className="quote">
        <p>
          We independently reproduced the central finding of the current state of the art — the
          Microsoft AI for Good Lab and WWF Germany work of September 2025 — on different water, and
          we are in active correspondence with its authors.
        </p>
        <cite>Evidence: docs/D2_SEGMENTATION_SUMMARY.md</cite>
      </div>
      <div className="grid3">
        <div className="card">
          <span className="n">Segmentation</span>
          <h3>0.525</h3>
          <p>
            Net recall as polygons, up from 0.000 when the same data was posed as a detection
            problem. The task framing was the finding, not the model size.
          </p>
        </div>
        <div className="card">
          <span className="n">Honesty</span>
          <h3>62 images</h3>
          <p>
            The real-data ceiling we actually have. Synthetic volume was tested and disproved; we
            report the constraint rather than hiding it behind a synthetic score.
          </p>
        </div>
        <div className="card">
          <span className="n">Coverage</span>
          <h3>5 / 5</h3>
          <p>
            All five problem-statement classes are covered by the taxonomy, with ghost_net the one
            that carries a segmentation head and a review gate.
          </p>
        </div>
      </div>
    </section>
  );
}

/** The spec table, as data. It is read straight down in one column on a phone,
 *  so the key has to survive being separated from its value by a line break --
 *  which is why these are full labels and not abbreviations. */
const SPEC: [string, string][] = [
  [
    "Input",
    "Side-scan sonar waterfall — XTF and per-channel PNG tiles, despeckled, 8-bit, across-track 0–120 m",
  ],
  [
    "Model",
    "D2 segmentation head over the five-class GhostNet taxonomy; ghost_net carries the review gate",
  ],
  ["Training data", "73 annotated chips, 425 polygons; 62 real net images total — the honest ceiling"],
  ["Net recall", "0.525 as polygons, from 0.000 posed as detection"],
  ["Area claimed", "7.0 % median per chip, against 56.5 % for a naive bounding box"],
  ["Position error", "± 24 m median; reported per detection, never averaged away"],
  [
    "Outputs",
    "GeoJSON polygons and CSV; calibrated score, position error, class and review state on every record",
  ],
  ["Contract", "v1.2.0 — the app and the model speak deliberately different score scales"],
  ["Review", "review_only by default; accept, reject or escalate, always by a human"],
  ["Survey speed", "2.0 m/s (~4 kn) — the working speed the imagery assumes"],
];

export function SpecSection() {
  return (
    <section className="band grain" id="spec">
      <div className="kicker">05 — The specifics</div>
      <h2 className="h2">What it runs on</h2>
      <p className="lede">
        Nothing here is aspirational. These are the figures the current build reports.
      </p>
      <div className="spec">
        {SPEC.map(([key, value]) => (
          <div key={key}>
            <k>{key}</k>
            <v>{value}</v>
          </div>
        ))}
      </div>
    </section>
  );
}
