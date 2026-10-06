"""Build the PINTA North Sea held-out EVALUATION subset.

    python ai/scripts/build_pinta_eval.py --dry-run
    python ai/scripts/build_pinta_eval.py

Reads  ai/data/interim/PINTA-N09/{targets.jsonl, images/*.png}
Writes ai/data/interim/PINTA-EVAL/{images/*.png, manifest.jsonl,
                                   contact_sheet.png, build_report.json}

Why this exists, and why it is TWENTY images and not 563
---------------------------------------------------------
PINTA cannot help ghost_net as TRAINING data -- measured 22 Sep 2026. Of 563
targets, 446 carry a blank classification, and against 2,246 existing ghost_net
train boxes the rope-like handful is +0.4%. The class is synthetic-bound anyway
(51 real frames : 1,364 synthetic), so volume is not the lever.

What PINTA is uniquely good for is MEASUREMENT. Every other source in this
project is Great Lakes (AI4SHIPWRECKS), Chinese coastal (CHINA-OFFSHORE) or
a single pipeline survey (SUBPIPE). PINTA is German North Sea, a different sea,
a different sonar, a different contractor. It is the only out-of-domain
evaluation material available, and measurement -- not data volume -- is this
project's binding constraint.

So this script selects only the targets whose surveyor classification is
wreck-like or rope-like, which is the subset a human can box in ~30 minutes.
Boxing all 563 would cost days and mostly produce boxes around "Objekt?".

What the marker gives you, and what it does not
------------------------------------------------
`extract_pinta_targets.py` recovered a POINT per target from the blue annotation
circle, then painted the circle out. That point is a real datum -- the
surveyor's own localisation -- and it is carried here as `marker_centroid_xy`
so the boxing tool can seed a crosshair. It is NOT a box. The extent still has
to come from a human looking at the frame, because metres-per-pixel is only
recoverable by OCR'ing each snippet's range axis.

The surveyor's measured `target_width_m` / `target_length_m` ARE carried, in
metres, unconverted. They are a sanity check on a drawn box's aspect ratio,
not a substitute for drawing it.

Honesty constraints inherited from the extractor
-------------------------------------------------
- Images here are INPAINTED where the marker sat. The circle was drawn ON the
  target, so those pixels are reconstructed, not measured. `inpainted_px` rides
  along per record. This is disclosed rather than hidden precisely because this
  subset is meant to produce a published number.
- Classifications stay in the surveyor's hedged German ("Wrack?", "Seil?").
  They are evidence about the target, not labels.

Licence
-------
Cleared for this use. BSH permits *Drittverwendung* subject to citation and
disclosure of modifications; see docs/DATA.md, "BSH / PINTA N-09". Note the
subset may NOT be sublicensed onward -- it cannot go to GhostNetZero.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent

SRC_ROOT = AI_ROOT / "data" / "interim" / "PINTA-N09"
OUT_ROOT = AI_ROOT / "data" / "interim" / "PINTA-EVAL"

#: Surveyor classification substrings that select a target into the subset.
#: Matched case-insensitively against `classification1`. Deliberately literal:
#: these are the exact strings the extractor tallied, so a new PINTA area with
#: new wording will simply not match rather than silently mis-select.
#:
#: "Sewil?" is an OCR corruption of "Seil?" in TargetReport-N-09-04_Rev1.pdf --
#: it appears once, and dropping it would silently lose a rope target.
WRECK_LIKE = ("wrack",)
ROPE_LIKE = ("seil", "sewil")


def is_candidate(classification1: str) -> bool:
    """True if the surveyor's hedged German reads wreck-like or rope-like."""
    c = (classification1 or "").lower()
    return any(k in c for k in WRECK_LIKE + ROPE_LIKE)


def eval_class(record: dict) -> tuple[str | None, str]:
    """Map one PINTA target to a GhostNet class.

    Returns (class_or_None, reason). None means "keep the image in the subset
    for inspection, but do not box it and do not score against it".

    Decided 2026-09-23. The three calls, and why:

    1. `Fischereispur?` ("fishing trace") is a TRAWL SCAR -- a mark dragged in
       the sediment, not an object resting on it. Scoring a detector against a
       scar teaches and measures a false positive. Excluded outright, and the
       check runs FIRST so that "Seil? Fischereispur?" is excluded on the
       stronger evidence rather than mapped on the weaker.

    2. `Wrack` in any hedging maps to `wreck`. These are the only confident
       labels in the set (4 unhedged), and the hedged ones -- "Wrack?",
       "Objekt? Wrack?", "Objekt? Wrackteil?" -- still assert wreck material.
       `Wrackteil` ("wreck part") stays `wreck` rather than going to `debris`:
       `debris` in this project means seabed litter, and a 7.8 x 4.2 m piece
       of a ship is not that.

    3. `Seil?` does NOT map to `ghost_net`. A rope on the seabed is not
       necessarily lost fishing gear -- only 2 of 10 rope-like targets mention
       fishing at all, and both of those are the excluded scars. Forcing the
       remaining ~8 into `ghost_net` would produce a number off too few boxes
       to publish and too easy to misread as a real ghost_net measurement.
       They are kept, unboxed, as an inspection set.

    The `record` carries, among others:
        classification1   e.g. "Wrack", "Wrack?", "Objekt? Wrackteil?",
                               "Seil?", "Seil? Spur?", "Seil? Fischereispur?"
        description       surveyor free text, German
        target_width_m    surveyor's measured extent, metres
        target_length_m
        target_shadow_m   acoustic shadow length -- height proxy
    """
    c = (record.get("classification1") or "").lower()

    if "fischereispur" in c:
        return None, "trawl scar, not an object"
    if "wrack" in c:
        return "wreck", "wreck material, surveyor-asserted"
    if any(k in c for k in ROPE_LIKE):
        return None, "rope, not confidently lost fishing gear"
    return None, "no rule matched"


def load_candidates() -> list[dict]:
    src = SRC_ROOT / "targets.jsonl"
    if not src.exists():
        sys.exit(f"missing {src} -- run extract_pinta_targets.py first")
    records = [json.loads(line) for line in src.open(encoding="utf-8")]
    return [r for r in records if is_candidate(r.get("classification1", ""))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be written, touch nothing")
    ap.add_argument("--list", action="store_true",
                    help="print the candidates and exit; use this to decide "
                         "eval_class() before implementing it")
    args = ap.parse_args()

    cands = load_candidates()

    if args.list or args.dry_run:
        print(f"{len(cands)} candidates from {SRC_ROOT.name}\n")
        hdr = f"{'target_id':<16} {'W(m)':>6} {'L(m)':>6} {'shad':>6} {'depth':>6}  classification1"
        print(hdr)
        print("-" * len(hdr))
        for r in sorted(cands, key=lambda x: x["target_id"]):
            def num(k):
                v = r.get(k)
                return f"{float(v):6.1f}" if v not in (None, "") else "     -"
            print(f"{r['target_id']:<16} {num('target_width_m')} "
                  f"{num('target_length_m')} {num('target_shadow_m')} "
                  f"{num('water_depth_m')}  {r.get('classification1', '')}")
        tally = Counter(r.get("classification1", "") for r in cands)
        print("\nby classification:")
        for k, v in tally.most_common():
            print(f"  {v:3d}  {k!r}")
        if args.list:
            return
        print(f"\n--dry-run: would write {len(cands)} images to {OUT_ROOT}")
        return

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "images").mkdir(exist_ok=True)

    written, missing = 0, []
    class_tally: Counter = Counter()
    with (OUT_ROOT / "manifest.jsonl").open("w", encoding="utf-8") as fh:
        for r in sorted(cands, key=lambda x: x["target_id"]):
            png = SRC_ROOT / "images" / f"{r['target_id']}.png"
            if not png.exists():
                missing.append(r["target_id"])
                continue
            cls, reason = eval_class(r)
            class_tally[cls or "(excluded)"] += 1
            shutil.copy2(png, OUT_ROOT / "images" / png.name)
            fh.write(json.dumps({
                "target_id": r["target_id"],
                "image": f"images/{png.name}",
                "sub_area": r.get("sub_area"),
                "classification1": r.get("classification1"),
                "classification2": r.get("classification2"),
                "description": r.get("description"),
                # the surveyor's own localisation -- a point, never a box
                "marker_centroid_xy": r.get("marker_centroid_xy"),
                "marker_centroid_norm": r.get("marker_centroid_norm"),
                "marker_bbox_xyxy": r.get("marker_bbox_xyxy"),
                "crop_wh": r.get("crop_wh"),
                # surveyor's measured extent, metres, unconverted
                "target_width_m": r.get("target_width_m"),
                "target_length_m": r.get("target_length_m"),
                "target_shadow_m": r.get("target_shadow_m"),
                "water_depth_m": r.get("water_depth_m"),
                "range_to_target_m": r.get("range_to_target_m"),
                # disclosure: these pixels were reconstructed, not measured
                "inpainted_px": r.get("inpainted_px"),
                "eval_class": cls,           # None = keep, inspect, do not score
                "eval_class_reason": reason,
                "box_xyxy": None,            # <- the human fills this in
            }, ensure_ascii=False) + "\n")
            written += 1

    (OUT_ROOT / "build_report.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "out-of-domain (German North Sea) held-out EVALUATION subset",
        "source": "BSH PINTA, site N-9.1, area N-09 sub-areas 01-04",
        "selected_from": 563,
        "selected": written,
        "missing_images": missing,
        "selection_rule": {"wreck_like": WRECK_LIKE, "rope_like": ROPE_LIKE},
        "eval_class_tally": dict(class_tally),
        "to_box": class_tally.get("wreck", 0),
        "boxes": "NOT emitted -- marker gives a point; box_xyxy is hand-drawn",
        "licence": ("Cleared for training/eval per BSH Drittverwendung; "
                    "NOT sublicensable onward. See docs/DATA.md."),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {written} images + manifest.jsonl to {OUT_ROOT}")
    if missing:
        print(f"WARNING: {len(missing)} images missing: {missing}")


if __name__ == "__main__":
    main()
