"""Build the test bench page from a run's demo_data.json.

    python ai/scripts/build_testbench.py --run gv2-yolo11s

Writes ai/experiments/<run>/testbench.html -- a self-contained page holding the
real model output on real test tiles, with a live confidence threshold.

Why a threshold slider and not a static gallery
-----------------------------------------------
The one setting nobody can pick from a metrics table is the review floor: the
calibrated confidence below which a detection is not shown to a human. Raise it
and false alarms vanish along with real detections; lower it and the reviewer
drowns. The trade is only legible when you can watch both sides move at once,
against real frames, so the slider drives every box on the page and the measured
empty-seabed flag rate at the same time.

The page is GENERATED. Do not hand-edit the HTML -- edit this and re-run.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import cv2
import numpy as np

AI_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = AI_ROOT / "experiments"

TEMPLATE = r"""<title>GhostNet Test Bench</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
  /* Light palette on bare :root -- the un-stamped "system" state inherits it. */
  :root {
    --ground:      #EDF0EF;
    --panel:       #FFFFFF;
    --panel-sunk:  #E4E9E8;
    --ink:         #15201E;
    --muted:       #5B6A68;
    --faint:       #849492;
    --rule:        #D3DAD8;
    --rule-strong: #B6C1BF;

    --signal:      #C4741B;   /* detections: sonar amber */
    --signal-soft: #F3E2CC;
    --truth:       #1F7E96;   /* ground truth: cool, so it never reads as a prediction */

    --hit:         #24785A;
    --miss:        #7A4FA8;
    --clean:       #3F6E85;
    --alarm:       #B33F35;

    --shadow: 0 1px 2px rgba(21,32,30,.06), 0 8px 24px -12px rgba(21,32,30,.18);
  }
  /* OS dark, unless the viewer explicitly chose light. */
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground:      #0C1315;
      --panel:       #141E21;
      --panel-sunk:  #0F181A;
      --ink:         #DBE5E3;
      --muted:       #8FA09E;
      --faint:       #6A7B79;
      --rule:        #223034;
      --rule-strong: #33454A;

      --signal:      #E9A054;
      --signal-soft: #3A2B18;
      --truth:       #56C2DA;

      --hit:         #4CBB8C;
      --miss:        #A98BD6;
      --clean:       #74A6BE;
      --alarm:       #E0776C;

      --shadow: 0 1px 2px rgba(0,0,0,.4), 0 10px 28px -14px rgba(0,0,0,.7);
    }
  }
  /* Explicit dark choice wins over a light OS. */
  :root[data-theme="dark"] {
    --ground:      #0C1315;
    --panel:       #141E21;
    --panel-sunk:  #0F181A;
    --ink:         #DBE5E3;
    --muted:       #8FA09E;
    --faint:       #6A7B79;
    --rule:        #223034;
    --rule-strong: #33454A;

    --signal:      #E9A054;
    --signal-soft: #3A2B18;
    --truth:       #56C2DA;

    --hit:         #4CBB8C;
    --miss:        #A98BD6;
    --clean:       #74A6BE;
    --alarm:       #E0776C;

    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 10px 28px -14px rgba(0,0,0,.7);
  }

  * { box-sizing: border-box; }

  body {
    background: var(--ground);
    color: var(--ink);
    font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.55;
    margin: 0;
    -webkit-font-smoothing: antialiased;
  }

  .wrap { max-width: 1180px; margin: 0 auto; padding: 0 24px 96px; }

  h1, h2, h3 {
    font-family: "IBM Plex Sans Condensed", "IBM Plex Sans", sans-serif;
    text-wrap: balance;
    margin: 0;
  }

  .eyebrow {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11px;
    letter-spacing: .13em;
    text-transform: uppercase;
    color: var(--muted);
  }

  /* ---- masthead ---------------------------------------------------- */
  header.masthead {
    border-bottom: 1px solid var(--rule);
    background: var(--panel);
    padding: 34px 0 26px;
    margin-bottom: 28px;
  }
  .masthead h1 { font-size: 32px; font-weight: 700; letter-spacing: -.015em; margin-top: 6px; }
  .lede { color: var(--muted); max-width: 66ch; margin-top: 10px; }

  .provenance {
    display: flex; flex-wrap: wrap; gap: 6px 8px; margin-top: 18px;
    font-family: "IBM Plex Mono", monospace; font-size: 11.5px;
  }
  .provenance span {
    border: 1px solid var(--rule); border-radius: 3px;
    padding: 3px 8px; color: var(--muted); background: var(--panel-sunk);
  }

  /* ---- stat row ---------------------------------------------------- */
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); gap: 1px;
           background: var(--rule); border: 1px solid var(--rule); border-radius: 4px; overflow: hidden; }
  .stat { background: var(--panel); padding: 14px 16px; }
  .stat .k { font-family: "IBM Plex Mono", monospace; font-size: 10.5px; letter-spacing: .1em;
             text-transform: uppercase; color: var(--muted); }
  .stat .v { font-family: "IBM Plex Sans Condensed", sans-serif; font-size: 27px; font-weight: 600;
             font-variant-numeric: tabular-nums; margin-top: 3px; line-height: 1.1; }
  .stat .n { font-size: 12px; color: var(--faint); margin-top: 2px; }
  .stat .v.up { color: var(--hit); }

  /* ---- threshold console ------------------------------------------- */
  .console {
    position: sticky; top: 0; z-index: 20;
    background: var(--panel); border: 1px solid var(--rule-strong); border-radius: 4px;
    padding: 18px 20px; margin: 26px 0 30px; box-shadow: var(--shadow);
  }
  .console-grid { display: grid; grid-template-columns: minmax(280px, 1.35fr) minmax(240px, 1fr); gap: 22px 30px; align-items: start; }
  @media (max-width: 760px) { .console-grid { grid-template-columns: 1fr; } }

  .thr-value {
    font-family: "IBM Plex Mono", monospace; font-size: 30px; font-weight: 500;
    font-variant-numeric: tabular-nums; color: var(--signal); line-height: 1;
  }
  input[type=range] { width: 100%; accent-color: var(--signal); margin: 14px 0 4px; height: 22px; }
  input[type=range]:focus-visible { outline: 2px solid var(--signal); outline-offset: 4px; }
  .scale { display: flex; justify-content: space-between; font-family: "IBM Plex Mono", monospace;
           font-size: 10.5px; color: var(--faint); font-variant-numeric: tabular-nums; }

  .readout { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .readout div { min-width: 0; }
  .readout .k { font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .09em;
                text-transform: uppercase; color: var(--muted); }
  .readout .v { font-family: "IBM Plex Sans Condensed", sans-serif; font-size: 22px; font-weight: 600;
                font-variant-numeric: tabular-nums; line-height: 1.15; }

  .curve-note { font-size: 12.5px; color: var(--muted); margin-top: 12px; max-width: 60ch; }
  .curve-note b { color: var(--ink); font-weight: 600; }

  /* ---- legend ------------------------------------------------------- */
  .legend { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; font-size: 12.5px;
            color: var(--muted); margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--rule); }
  .swatch { display: inline-flex; align-items: center; gap: 7px; }
  .swatch i { width: 22px; height: 0; border-top-width: 2px; border-top-style: solid; display: inline-block; }

  /* ---- sections ----------------------------------------------------- */
  section { margin-top: 40px; }
  .sec-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
              border-bottom: 1px solid var(--rule); padding-bottom: 10px; margin-bottom: 4px; }
  .sec-head h2 { font-size: 20px; font-weight: 600; }
  .sec-head .count { font-family: "IBM Plex Mono", monospace; font-size: 12px; color: var(--muted); }
  .sec-why { color: var(--muted); font-size: 13.5px; max-width: 68ch; margin: 10px 0 18px; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); gap: 18px; }

  .card { background: var(--panel); border: 1px solid var(--rule); border-radius: 4px;
          overflow: hidden; box-shadow: var(--shadow); }
  .card > button { all: unset; display: block; width: 100%; cursor: pointer; }
  .card > button:focus-visible { outline: 2px solid var(--signal); outline-offset: -2px; }

  .frame { position: relative; aspect-ratio: 1 / 1; background: var(--panel-sunk); }
  .frame img { width: 100%; height: 100%; display: block; object-fit: cover; }
  .box { position: absolute; pointer-events: none; }
  .box.truth { border: 1.5px dashed var(--truth); }
  .box.pred  { border: 2px solid var(--signal); box-shadow: 0 0 0 1px rgba(0,0,0,.35); }
  .box.pred > b {
    position: absolute; top: -1px; left: -2px; transform: translateY(-100%);
    background: var(--signal); color: #14100A;
    font-family: "IBM Plex Mono", monospace; font-size: 10px; font-weight: 600;
    padding: 1px 4px; white-space: nowrap; font-variant-numeric: tabular-nums;
  }

  .card-meta { padding: 9px 11px 11px; border-top: 1px solid var(--rule); }
  .card-meta .id { font-family: "IBM Plex Mono", monospace; font-size: 10.5px; color: var(--muted);
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .card-meta .row { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-top: 4px; }
  .card-meta .n { font-family: "IBM Plex Mono", monospace; font-size: 11.5px; font-variant-numeric: tabular-nums; }

  .chip { font-family: "IBM Plex Mono", monospace; font-size: 10px; letter-spacing: .07em;
          text-transform: uppercase; padding: 2px 6px; border-radius: 2px; border: 1px solid; font-weight: 600; }
  .chip.hit   { color: var(--hit);   border-color: var(--hit); }
  .chip.miss  { color: var(--miss);  border-color: var(--miss); }
  .chip.clean { color: var(--clean); border-color: var(--clean); }
  .chip.false_alarm { color: var(--alarm); border-color: var(--alarm); }

  /* ---- detail dialog ------------------------------------------------ */
  dialog {
    border: 1px solid var(--rule-strong); border-radius: 5px; padding: 0;
    background: var(--panel); color: var(--ink);
    max-width: min(760px, 94vw); width: 100%; box-shadow: var(--shadow);
  }
  dialog::backdrop { background: rgba(4,10,11,.62); }
  .dlg-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
              padding: 16px 18px; border-bottom: 1px solid var(--rule); }
  .dlg-head h3 { font-size: 16px; font-weight: 600; }
  .dlg-head .id { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: var(--muted); margin-top: 3px;
                  word-break: break-all; }
  .dlg-body { padding: 16px 18px 20px; }
  .dlg-body pre {
    background: var(--panel-sunk); border: 1px solid var(--rule); border-radius: 3px;
    padding: 12px; overflow-x: auto; font-family: "IBM Plex Mono", monospace;
    font-size: 11.5px; line-height: 1.5; margin: 12px 0 0;
  }
  .close { all: unset; cursor: pointer; font-family: "IBM Plex Mono", monospace; font-size: 12px;
           color: var(--muted); border: 1px solid var(--rule); padding: 4px 9px; border-radius: 3px; }
  .close:hover, .close:focus-visible { color: var(--ink); border-color: var(--rule-strong); }

  .warn { background: var(--signal-soft); border-left: 2px solid var(--signal);
          padding: 9px 12px; font-size: 12.5px; margin-top: 12px; }

  footer { margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--rule);
           color: var(--muted); font-size: 12.5px; max-width: 72ch; }
  footer code { font-family: "IBM Plex Mono", monospace; font-size: 11.5px;
                background: var(--panel-sunk); padding: 1px 4px; border-radius: 2px; }

  @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>

<header class="masthead">
  <div class="wrap">
    <div class="eyebrow">SIH26057 &middot; side-scan sonar &middot; held-out test split</div>
    <h1>GhostNet Test Bench</h1>
    <p class="lede">
      Real output from the trained detector on sonar tiles it has never seen. The mix is
      deliberate: confident finds, things it missed, empty seabed it correctly ignored, and
      the false alarms. Move the threshold to see what a reviewer would actually be shown.
    </p>
    <div class="provenance" id="prov"></div>
  </div>
</header>

<div class="wrap">
  <div class="stats" id="stats"></div>

  <div class="console">
    <div class="console-grid">
      <div>
        <div class="eyebrow">Review floor &middot; calibrated confidence</div>
        <div class="thr-value" id="thrValue">0.20</div>
        <input type="range" id="thr" min="5" max="90" step="1" value="20"
               aria-label="Review floor on calibrated confidence">
        <div class="scale"><span>0.05</span><span>0.30</span><span>0.60</span><span>0.90</span></div>
      </div>
      <div>
        <div class="readout">
          <div>
            <div class="k">Shown here</div>
            <div class="v" id="roShown">0</div>
          </div>
          <div>
            <div class="k">False alarms</div>
            <div class="v" id="roFalse" style="color:var(--alarm)">0</div>
          </div>
          <div>
            <div class="k">Empty seabed flagged</div>
            <div class="v" id="roBg">0%</div>
          </div>
        </div>
        <p class="curve-note" id="curveNote"></p>
      </div>
    </div>
    <div class="legend">
      <span class="swatch"><i style="border-color:var(--signal)"></i> model detection</span>
      <span class="swatch"><i style="border-color:var(--truth); border-top-style:dashed"></i> ground truth</span>
      <span>Boxes below the floor are hidden, exactly as a reviewer would see it.</span>
    </div>
  </div>

  <div id="sections"></div>

  <footer>
    <p>
      Every payload here is untouched output from <code>ghostnet.detect()</code> &mdash; the same
      function the application imports &mdash; validated against the frozen contract. Confidence shown
      is <b>calibrated</b>, never the raw detector score. Coordinates are absent because these tiles
      carry no navigation metadata, which the contract reports as <code>localization: "none"</code>
      rather than inventing a position.
    </p>
    <p id="genline"></p>
  </footer>
</div>

<dialog id="dlg">
  <div class="dlg-head">
    <div>
      <h3 id="dlgTitle">Detection detail</h3>
      <div class="id" id="dlgId"></div>
    </div>
    <button class="close" id="dlgClose">Close</button>
  </div>
  <div class="dlg-body">
    <div id="dlgWarn"></div>
    <pre id="dlgJson"></pre>
  </div>
</dialog>

<script id="payload" type="application/json">__DATA__</script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("payload").textContent);

  var KIND = {
    hit:   { label: "Found it",
             why: "The model reported an object where the survey actually recorded one. Dashed cyan is the human-drawn truth; solid amber is what the model produced." },
    miss:  { label: "Missed it",
             why: "A real object the model did not report at this threshold. Lowering the floor recovers some of these — and admits false alarms with them." },
    clean: { label: "Correctly ignored",
             why: "Verified-empty seabed with nothing reported. This is the artificial-vs-natural requirement working: the model declined to call a rock an anomaly." },
    false_alarm: { label: "False alarm",
             why: "Empty seabed the model flagged anyway. Every one of these is a dive somebody would waste, which is why the review floor is a real decision and not a default." }
  };
  var ORDER = ["hit", "miss", "clean", "false_alarm"];

  function pct(n) { return (n * 100).toFixed(1).replace(/\.0$/, "") + "%"; }
  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined) n.textContent = txt;
    return n;
  }

  /* ---- provenance + headline stats -------------------------------- */
  var prov = document.getElementById("prov");
  [["model", D.model_version],
   ["split", D.split + " · held out"],
   ["contract", (D.cases[0] && D.cases[0].payload.contract_version) || "1.0.0"],
   ["frames", D.cases.length + " of 3410"]
  ].forEach(function (p) {
    prov.appendChild(el("span", null, p[0] + " = " + p[1]));
  });

  var tm = D.test_metrics;
  var bg = D.background_metrics;
  var at20 = bg.curve.filter(function (c) { return c.threshold === 0.2; })[0];
  [["ghost_pot mAP50", "0.297", "derelict fishing gear, 567 boxes"],
   ["precision", tm.precision.toFixed(3), "all classes, held-out test", true],
   ["recall", tm.recall.toFixed(3), "the cost of the trade"],
   ["false alarms @ 0.20", pct(at20.rate), at20.frames_flagged + " of " + bg.background_tiles + " empty tiles", true]
  ].forEach(function (s) {
    var d = el("div", "stat");
    d.appendChild(el("div", "k", s[0]));
    d.appendChild(el("div", "v" + (s[3] ? " up" : ""), s[1]));
    d.appendChild(el("div", "n", s[2]));
    document.getElementById("stats").appendChild(d);
  });

  /* ---- build the case cards --------------------------------------- */
  var sections = document.getElementById("sections");
  var cards = [];

  ORDER.forEach(function (kind) {
    var group = D.cases.filter(function (c) { return c.kind === kind; });
    if (!group.length) return;

    var sec = el("section");
    var head = el("div", "sec-head");
    head.appendChild(el("h2", null, KIND[kind].label));
    head.appendChild(el("span", "count", group.length + " frame" + (group.length === 1 ? "" : "s")));
    sec.appendChild(head);
    sec.appendChild(el("p", "sec-why", KIND[kind].why));

    var grid = el("div", "grid");
    group.forEach(function (c) {
      var card = el("div", "card");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("aria-label", "Open payload for " + c.frame_id);

      var frame = el("div", "frame");
      var img = document.createElement("img");
      img.src = c.image;
      img.alt = "Side-scan sonar tile " + c.frame_id;
      img.loading = "lazy";
      frame.appendChild(img);

      (c.truth || []).forEach(function (t) {
        var b = el("div", "box truth");
        b.style.left   = ((t[1] - t[3] / 2) * 100) + "%";
        b.style.top    = ((t[2] - t[4] / 2) * 100) + "%";
        b.style.width  = (t[3] * 100) + "%";
        b.style.height = (t[4] * 100) + "%";
        frame.appendChild(b);
      });

      var predEls = [];
      (c.payload.detections || []).forEach(function (d) {
        var b = el("div", "box pred");
        b.style.left   = (d.bbox[0] / c.width  * 100) + "%";
        b.style.top    = (d.bbox[1] / c.height * 100) + "%";
        b.style.width  = (d.bbox[2] / c.width  * 100) + "%";
        b.style.height = (d.bbox[3] / c.height * 100) + "%";
        var tag = el("b", null, d["class"] + " " + d.calibrated_confidence.toFixed(2));
        b.appendChild(tag);
        frame.appendChild(b);
        predEls.push({ node: b, conf: d.calibrated_confidence });
      });

      btn.appendChild(frame);
      card.appendChild(btn);

      var meta = el("div", "card-meta");
      meta.appendChild(el("div", "id", c.frame_id));
      var row = el("div", "row");
      row.appendChild(el("span", "chip " + c.kind, KIND[c.kind].label));
      var n = el("span", "n", "");
      row.appendChild(n);
      meta.appendChild(row);
      card.appendChild(meta);

      btn.addEventListener("click", function () { openCase(c); });

      grid.appendChild(card);
      cards.push({ case: c, preds: predEls, counter: n });
    });

    sec.appendChild(grid);
    sections.appendChild(sec);
  });

  /* ---- threshold ---------------------------------------------------- */
  var thr = document.getElementById("thr");
  var thrValue = document.getElementById("thrValue");
  var roShown = document.getElementById("roShown");
  var roFalse = document.getElementById("roFalse");
  var roBg = document.getElementById("roBg");
  var curveNote = document.getElementById("curveNote");

  // The measured curve is sampled at fixed thresholds; report the nearest one
  // AT OR BELOW the slider rather than interpolating, so the figure on screen
  // is always a number that was actually measured on the 2,620 empty tiles.
  function nearestMeasured(t) {
    var best = bg.curve[0];
    bg.curve.forEach(function (c) { if (c.threshold <= t + 1e-9) best = c; });
    return best;
  }

  function apply() {
    var t = parseInt(thr.value, 10) / 100;
    thrValue.textContent = t.toFixed(2);

    var shown = 0, falses = 0;
    cards.forEach(function (card) {
      var visible = 0;
      card.preds.forEach(function (p) {
        var on = p.conf >= t;
        p.node.style.display = on ? "" : "none";
        if (on) visible++;
      });
      shown += visible;
      if (card.case.kind === "clean" || card.case.kind === "false_alarm") falses += visible;
      card.counter.textContent = visible === 0
        ? "nothing reported"
        : visible + (visible === 1 ? " detection" : " detections");
    });

    roShown.textContent = shown;
    roFalse.textContent = falses;

    var m = nearestMeasured(t);
    roBg.textContent = pct(m.rate);
    curveNote.innerHTML =
      "Measured on <b>" + bg.background_tiles.toLocaleString() + "</b> verified-empty seabed tiles at " +
      "threshold <b>" + m.threshold.toFixed(2) + "</b>: <b>" + m.frames_flagged.toLocaleString() +
      "</b> frames flagged. Below about 0.20 the alarm rate climbs steeply; above 0.50 real " +
      "detections start disappearing faster than false ones.";
  }

  thr.addEventListener("input", apply);

  /* ---- detail dialog ------------------------------------------------ */
  var dlg = document.getElementById("dlg");
  document.getElementById("dlgClose").addEventListener("click", function () { dlg.close(); });

  function openCase(c) {
    document.getElementById("dlgTitle").textContent = KIND[c.kind].label + " · " + c.source;
    document.getElementById("dlgId").textContent = c.frame_id;
    document.getElementById("dlgJson").textContent = JSON.stringify(c.payload, null, 2);
    var w = document.getElementById("dlgWarn");
    w.innerHTML = "";
    (c.payload.warnings || []).forEach(function (msg) {
      w.appendChild(el("div", "warn", msg));
    });
    dlg.showModal();
  }

  document.getElementById("genline").textContent =
    "Generated from " + D.weights + " by ai/scripts/build_testbench.py. Regenerate rather than edit.";

  apply();
})();
</script>
"""


def shrink(uri: str, max_side: int, quality: int) -> str:
    """Re-encode an embedded image smaller.

    make_demo writes 512px tiles, which is faithful but puts ~2.4 MB of base64
    into the page -- enough that the viewer fails to load it. The cards render
    at ~232px, so anything past ~384 is invisible detail paid for in bytes.
    Downscaling here keeps demo_data.json as the untouched record and treats
    size as what it is: a rendering concern.
    """
    head, _, b64 = uri.partition(",")
    buf = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return uri
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        f = max_side / max(h, w)
        img = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    ok, out = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return uri
    return "data:image/jpeg;base64," + base64.b64encode(out).decode("ascii")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the test bench page for a run.")
    ap.add_argument("--run", required=True, help="experiment name, e.g. gv2-yolo11s")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-side", type=int, default=320,
                    help="downscale embedded tiles to this; cards render at ~232px")
    ap.add_argument("--quality", type=int, default=68, help="JPEG quality for embedded tiles")
    args = ap.parse_args()

    run_dir = EXPERIMENTS / args.run
    demo = run_dir / "demo_data.json"
    if not demo.exists():
        print(f"no demo_data.json in {run_dir}")
        print(f"run: python ai/scripts/make_demo.py --weights ai/experiments/{args.run}/weights/best.pt")
        return 1

    data = json.loads(demo.read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else run_dir / "testbench.html"

    before = sum(len(c["image"]) for c in data["cases"])
    for c in data["cases"]:
        c["image"] = shrink(c["image"], args.max_side, args.quality)
    after = sum(len(c["image"]) for c in data["cases"])
    print(f"  tiles {before / 1e6:.2f} MB -> {after / 1e6:.2f} MB "
          f"at {args.max_side}px q{args.quality}")

    # Guard the closing-tag sequence: a "</script>" inside JSON string data would
    # end the block early. Escaping the slash keeps it valid JSON and inert HTML.
    blob = json.dumps(data).replace("</", "<\\/")
    out.write_text(TEMPLATE.replace("__DATA__", blob), encoding="utf-8")

    kinds: dict[str, int] = {}
    for c in data["cases"]:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"  wrote {out}  ({size_mb:.1f} MB)")
    print(f"  {len(data['cases'])} cases: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
