/* Reliable hero capture.
 *
 * Two things made the old loop lie:
 *
 *  1. devicePixelRatio here is 0.8 (Windows at 125%), so setViewportSize takes
 *     DEVICE pixels while everything in the page is CSS pixels. Asking for
 *     1600x900 produced a 2000x1125 CSS viewport and a 1600x900 crop of it.
 *     Fixed by measuring dpr first and sizing from it.
 *
 *  2. Captures were driven by scrolling, so the committed scroll offset, the
 *     value of vh and the sticky pane all had to agree at the instant of
 *     capture. They repeatedly did not. Fixed by pinning progress directly via
 *     __heroProgress and never scrolling at all.
 *
 * Every frame is verified after the pin and again after the shot; a frame that
 * does not check out is reported rather than silently saved.
 */

const FILE = "file:///C:/Users/vandi/OneDrive/Desktop/ghostnet-landing-atlantic-fullbleed.html";
const CSS_W = 1600, CSS_H = 900;
const STOPS = [
  { p: 0.00, name: "idle" },
  { p: 0.32, name: "paying-out" },
  { p: 0.58, name: "ensonifying" },
  { p: 0.85, name: "contact" },
  { p: 1.00, name: "end" },
];

const page = await browser.getPage("shoot");
const errs = [];
page.on("pageerror", (e) => errs.push(String(e).slice(0, 200)));
page.on("console", (m) => { if (m.type() === "error") errs.push("console: " + m.text().slice(0, 200)); });

// --- size the viewport from the real device scale factor ---------------------
await page.setViewportSize({ width: CSS_W, height: CSS_H });
await page.goto(FILE);
await new Promise((r) => setTimeout(r, 1200));
const dpr = await page.evaluate(() => window.devicePixelRatio || 1);
await page.setViewportSize({ width: Math.round(CSS_W * dpr), height: Math.round(CSS_H * dpr) });
await new Promise((r) => setTimeout(r, 800));

const viewport = await page.evaluate(() => ({ w: window.innerWidth, h: window.innerHeight }));
console.log("dpr=" + dpr + "  css viewport=" + viewport.w + "x" + viewport.h +
            (viewport.w === CSS_W && viewport.h === CSS_H ? "  OK" : "  MISMATCH"));

// let fonts, GLBs and the first shader compiles settle
await new Promise((r) => setTimeout(r, 3500));

for (const stop of STOPS) {
  const pinned = await page.evaluate((p) => window.__heroProgress(p), stop.p);
  // enough animation that drifting elements are not caught mid-jump
  await new Promise((r) => setTimeout(r, 1300));

  const before = await page.evaluate(() => {
    const pane = document.querySelector(".hero-pane").getBoundingClientRect();
    return { paneTop: Math.round(pane.top), paneH: Math.round(pane.height),
             scrollY: Math.round(window.scrollY),
             depth: document.getElementById("rdoDepth").textContent,
             stage: (document.querySelector("#swap b.on") || {}).textContent };
  });

  const name = "hero-" + stop.name + ".png";
  await saveScreenshot(await page.screenshot(), name);

  // if anything moved during the shot, the frame is not what was measured
  const after = await page.evaluate(() => {
    const pane = document.querySelector(".hero-pane").getBoundingClientRect();
    return { paneTop: Math.round(pane.top), scrollY: Math.round(window.scrollY) };
  });

  const stable = before.paneTop === 0 && after.paneTop === 0 &&
                 before.scrollY === 0 && after.scrollY === 0 &&
                 before.paneH === CSS_H;
  console.log((stable ? "OK   " : "SUSPECT ") + name +
              "  p=" + pinned + "  depth=" + before.depth +
              "  stage=" + JSON.stringify(before.stage) +
              "  pane=" + before.paneTop + ".." + (before.paneTop + before.paneH));
}

await page.evaluate(() => window.__heroProgress(null));
console.log(errs.length ? "ERRORS: " + JSON.stringify(errs) : "no page errors");
