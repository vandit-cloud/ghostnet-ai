"""Build a local page for checking whether the real ghost_net boxes miss net.

    python ai/scripts/build_box_review.py
    # open ai/experiments/box-review/review.html in a browser

Why
---
evaluate_texture_prior.py drew "background" windows from the 73 real net
frames, clear of every labelled box, and several of them visibly contain the
same bead-chain structure the boxes are drawn around. If the boxes miss net,
every training pass teaches the detector that net pixels are seabed, which
would help explain real ghost_net recall sitting at zero.

The page shows each frame with its boxes, one at a time, and records one
verdict per frame. It is a LOCAL file on purpose: GHOSTNET-HAND's licence does
not allow republishing the imagery, so nothing here is uploaded anywhere.
Images are referenced by file:// path, not embedded.

Verdicts are autosaved in the browser and exported with the Download button
as ghostnet_box_review.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote

import cv2

AI_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = Path("E:/New folder/ai/data/processed")
OUT = AI_ROOT / "experiments" / "box-review"
NET = 4


def frames(data: Path) -> list[dict]:
    rows = []
    for split in ("train", "val", "test"):
        for lf in sorted((data / split / "labels").glob("GHOSTNET-HAND__*.txt")):
            img = next((data / split / "images" / f"{lf.stem}{e}"
                        for e in (".png", ".jpg", ".jpeg")
                        if (data / split / "images" / f"{lf.stem}{e}").exists()), None)
            if img is None:
                continue
            h, w = cv2.imread(str(img), cv2.IMREAD_GRAYSCALE).shape
            boxes = []
            for line in lf.read_text().splitlines():
                f = line.split()
                if len(f) >= 5:
                    boxes.append([int(f[0]), *map(float, f[1:5])])
            rows.append(dict(split=split, stem=lf.stem, w=w, h=h, boxes=boxes,
                             src="file:///" + quote(img.as_posix(), safe="/:")))
    return rows


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Ghost Net Box Review</title>
<style>
:root{--bg:#f5f5f2;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#d9d9d4;--acc:#1f6feb;
--ok:#1a7f37;--miss:#c4302b;--bad:#9a6700;--uns:#6e40c9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--fg:#ececea;--mut:#a3a39e;--card:#20201f;--line:#3a3a37;--acc:#58a6ff;--ok:#3fb950;--miss:#f85149;--bad:#d29922;--uns:#a371f7}}
:root[data-theme="dark"]{--bg:#161615;--fg:#ececea;--mut:#a3a39e;--card:#20201f;--line:#3a3a37;--acc:#58a6ff;--ok:#3fb950;--miss:#f85149;--bad:#d29922;--uns:#a371f7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;z-index:2}
h1{font-size:16px;margin:0}
.bar{flex:1;min-width:140px;height:6px;background:var(--line);border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--acc)}
main{max-width:1200px;margin:0 auto;padding:16px}
.help{color:var(--mut);font-size:13px;margin:0 0 12px}
.stage{background:#000;border-radius:6px;position:relative;overflow:auto;text-align:center}
canvas{image-rendering:pixelated;max-width:100%;height:auto}
.meta{display:flex;justify-content:space-between;gap:8px;margin:10px 0;color:var(--mut);font-size:13px;flex-wrap:wrap}
.btns{display:flex;gap:8px;flex-wrap:wrap}
button{font:inherit;padding:8px 12px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
button.v.sel{color:#fff;border-color:transparent}
button[data-v=ok].sel{background:var(--ok)}button[data-v=missed].sel{background:var(--miss)}
button[data-v=wrong].sel{background:var(--bad)}button[data-v=unsure].sel{background:var(--uns)}
kbd{font:12px ui-monospace,monospace;border:1px solid var(--line);border-radius:3px;padding:0 4px}
textarea{width:100%;margin-top:8px;font:inherit;padding:8px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.strip{display:flex;flex-wrap:wrap;gap:3px;margin-top:14px}
.strip span{width:14px;height:14px;border-radius:2px;background:var(--line);cursor:pointer}
.strip span.cur{outline:2px solid var(--acc)}
.strip .ok{background:var(--ok)}.strip .missed{background:var(--miss)}.strip .wrong{background:var(--bad)}.strip .unsure{background:var(--uns)}
</style></head><body>
<header><h1>Ghost net box review</h1><div class="bar"><i id="prog"></i></div><span id="count"></span>
<button id="dl">Download results</button></header>
<main>
<p class="help">Question for each frame: <b>is there net (bead chains: repeated dark beads in a line) outside the red boxes?</b>
Press <kbd>H</kbd> (or hold <kbd>Space</kbd>) to hide boxes and see underneath. <kbd>1</kbd> covered · <kbd>2</kbd> net missed · <kbd>3</kbd> a box is on something that isn't net · <kbd>4</kbd> unsure · <kbd>←</kbd>/<kbd>→</kbd> move · <kbd>+</kbd>/<kbd>−</kbd> zoom.</p>
<div class="stage"><canvas id="cv"></canvas></div>
<div class="meta"><span id="name"></span><span id="info"></span></div>
<div class="btns">
<button class="v" data-v="ok">1 · All net covered</button>
<button class="v" data-v="missed">2 · Net missed outside boxes</button>
<button class="v" data-v="wrong">3 · Box on non-net</button>
<button class="v" data-v="unsure">4 · Unsure</button>
<span style="flex:1"></span><button id="prev">← Prev</button><button id="next">Next →</button></div>
<textarea id="note" rows="2" placeholder="Optional note, e.g. 'two chains on the left unboxed'"></textarea>
<div class="strip" id="strip"></div>
</main>
<script>
const F = __DATA__;
const KEY = "ghostnet_box_review_v1";
let S = {}; try { S = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} };
let i = F.findIndex(f => !(S[f.stem] && S[f.stem].verdict)); if (i < 0) i = 0;
let zoom = 0, hide = false, img = new Image();
const cv = document.getElementById("cv"), cx = cv.getContext("2d");
function fit(f){ const maxW = Math.min(document.querySelector("main").clientWidth, 1168);
  const base = Math.max(1, Math.floor(Math.min(maxW / f.w, 700 / f.h)));
  return Math.max(1, base + zoom); }
function draw(){ const f = F[i], k = fit(f);
  cv.width = f.w * k; cv.height = f.h * k; cx.imageSmoothingEnabled = false;
  if (img.complete && img.naturalWidth) cx.drawImage(img, 0, 0, cv.width, cv.height);
  else { cx.fillStyle = "#400"; cx.fillRect(0,0,cv.width,cv.height); cx.fillStyle="#fff"; cx.fillText("image failed to load: " + f.src, 10, 20); }
  if (!hide) { cx.lineWidth = 2; f.boxes.forEach(b => { if (b[0] !== 4) return;
    cx.strokeStyle = "#ff2d2d"; const w = b[3]*cv.width, h = b[4]*cv.height;
    cx.strokeRect(b[1]*cv.width - w/2, b[2]*cv.height - h/2, w, h); }); } }
function show(){ const f = F[i], r = S[f.stem] || {};
  img = new Image(); img.onload = draw; img.onerror = draw; img.src = f.src; draw();
  document.getElementById("name").textContent = `${i+1} / ${F.length} · ${f.stem}`;
  const cover = f.boxes.filter(b=>b[0]===4).reduce((a,b)=>a+b[3]*b[4],0);
  document.getElementById("info").textContent = `${f.split} · ${f.w}×${f.h}px · ${f.boxes.filter(b=>b[0]===4).length} boxes · ${(cover*100).toFixed(0)}% of frame boxed`;
  document.querySelectorAll("button.v").forEach(b => b.classList.toggle("sel", b.dataset.v === r.verdict));
  document.getElementById("note").value = r.note || ""; strip(); }
function strip(){ const done = F.filter(f => S[f.stem] && S[f.stem].verdict).length;
  document.getElementById("count").textContent = `${done} / ${F.length} reviewed`;
  document.getElementById("prog").style.width = (100*done/F.length) + "%";
  const el = document.getElementById("strip"); el.innerHTML = "";
  F.forEach((f, j) => { const s = document.createElement("span");
    s.className = (S[f.stem] && S[f.stem].verdict || "") + (j === i ? " cur" : "");
    s.title = f.stem; s.onclick = () => { i = j; show(); }; el.appendChild(s); }); }
// A focused button would swallow Space as a click and record a verdict.
document.addEventListener("click", e => { if (e.target.tagName === "BUTTON") e.target.blur(); });
function setV(v){ const f = F[i]; S[f.stem] = Object.assign(S[f.stem] || {}, {verdict: v, split: f.split}); save();
  if (i < F.length - 1) { i++; } show(); }
function go(d){ i = Math.min(F.length-1, Math.max(0, i+d)); show(); }
document.querySelectorAll("button.v").forEach(b => b.onclick = () => setV(b.dataset.v));
document.getElementById("prev").onclick = () => go(-1);
document.getElementById("next").onclick = () => go(1);
document.getElementById("note").oninput = e => { const f = F[i];
  S[f.stem] = Object.assign(S[f.stem] || {split: f.split}, {note: e.target.value}); save(); };
document.getElementById("dl").onclick = () => {
  const out = F.map(f => Object.assign({stem: f.stem, split: f.split}, S[f.stem] || {}));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], {type: "application/json"}));
  a.download = "ghostnet_box_review.json"; a.click(); };
document.addEventListener("keydown", e => { if (e.target.tagName === "TEXTAREA") return;
  const m = {"1":"ok","2":"missed","3":"wrong","4":"unsure"};
  if (m[e.key]) setV(m[e.key]);
  else if (e.key === "ArrowRight") go(1); else if (e.key === "ArrowLeft") go(-1);
  else if (e.key === "h" || e.key === "H") { hide = !hide; draw(); }
  else if (e.key === " ") { e.preventDefault(); if (!hide) { hide = true; draw(); } }
  else if (e.key === "+" || e.key === "=") { zoom++; draw(); }
  else if (e.key === "-") { zoom = Math.max(-5, zoom-1); draw(); } });
document.addEventListener("keyup", e => { if (e.key === " ") { hide = false; draw(); } });
window.onresize = draw; show();
</script></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    a = ap.parse_args()
    rows = frames(a.data)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "review.html").write_text(PAGE.replace("__DATA__", json.dumps(rows)), encoding="utf-8")
    print(f"{len(rows)} frames -> {OUT / 'review.html'}")


if __name__ == "__main__":
    main()
