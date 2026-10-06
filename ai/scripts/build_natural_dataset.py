"""Build the chip-level `natural` classification dataset from CHINA-OFFSHORE.

    python ai/scripts/build_natural_dataset.py --dry-run
    python ai/scripts/build_natural_dataset.py

Reads  ai/data/processed/{train,val,test}/images/CHINA-OFFSHORE__*.jpg
Writes ai/data/natural/{train,val,test}/<class>/*.jpg + build_report.json

Why this exists, when taxonomy.py says `natural` stays out for good
-------------------------------------------------------------------
That ruling is correct and this does not overturn it. `ai/ghostnet/taxonomy.py`
rejects `natural` as a DETECTOR class, for a reason that still holds: nobody
draws boxes around rocks, a gully field has no discrete object in it, and a
full-frame box would teach the detector that objects fill the image.

This is a different thing. A gully field needs no box because the answer is the
whole chip -- which is a CLASSIFICATION label, and classification labels are
exactly what CHINA-OFFSHORE shipped. `import_classification.py` reads them and
deliberately throws them away, writing an empty label file so the frame serves
as a hard negative for the detector. That is the right call for the detector
and it discards a second, independent use of the same pixels.

What this recovers, and how
---------------------------
The source class survived in the filename even though the label did not:

    CHINA-OFFSHORE__<site>_<CODE>_<nnn>.jpg

Counts recovered this way reconcile exactly to the 2,072 CHINA-OFFSHORE frames
recorded in every run's provenance block, which is the check that the parse is
complete rather than merely plausible:

    TG  trench gully    782      RP  riprap         355
    SS  (see below)     763      SM  scour mark     123
                                 SW  sand wave       49      total 2,072

`SS` is INFERRED to be plain seabed surface, not asserted. The other four codes
match named classes in taxonomy.BACKGROUND_SOURCES; `SS` does not, and no
source document in this repo names it. --dry-run writes a contact sheet of
samples so the reading can be confirmed by eye before anything trains on it.
Do not publish a class name for `SS` until someone has looked.

The splits are INHERITED, never redrawn
---------------------------------------
Every chip keeps the split it already has in ai/data/processed. This is the
same discipline D2 used for the net polygons, and it matters twice here:

  * redrawing would leak detector test frames into classifier train, and the
    two models are scored on overlapping pixels;
  * _fingerprint.py exists because adding one source silently re-drew every
    other split once already (PLANE-HAND moved ghost_net 36 -> 38 test boxes).

Nothing here writes to ai/data/processed, so the detector's ruler cannot move.

The site confound, which is this dataset's real limitation
----------------------------------------------------------
Class and site are badly entangled, and the report prints the full matrix so it
cannot be overlooked:

    SM  scour mark   123 chips, shenzhen ONLY
    SW  sand wave     49 chips, quanzhou 43 + yantai 6
    TG  trench gully 782 chips, shenzhen 715 + quanzhou 67

A model can score well on SM by learning "shenzhen", exactly as gv7d3's net
result cannot distinguish "learned nets" from "learned Chinese coastal seabed"
(EXPERIMENT_GV7_PLAN.md 10.6). Report per-class accuracy with its site
breakdown beside it, or do not report it.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PROCESSED = AI_ROOT / "data" / "processed"
OUT_ROOT = AI_ROOT / "data" / "natural"
SPLITS = ("train", "val", "test")

#: Parses CHINA-OFFSHORE__<site>_<CODE>_<nnn>.<ext>. The double underscore
#: after the source name is load-bearing -- site names themselves are single
#: tokens, but anchoring on `__` means a future source with an underscore in
#: its site name does not silently reparse into the wrong groups.
CHIP_RE = re.compile(r"^CHINA-OFFSHORE__(?P<site>.+?)_(?P<code>[A-Za-z]+)_(?P<idx>\d+)\.")

#: Expected totals, asserted at the end. If the parse drifts, it should fail
#: loudly rather than quietly train on a subset.
EXPECTED = {"TG": 782, "SS": 763, "RP": 355, "SM": 123, "SW": 49}


# ---------------------------------------------------------------------------
# THE DECISION -- see the module docstring and docs/ for the trade-offs.
# ---------------------------------------------------------------------------
def natural_class(code: str, site: str) -> str | None:
    """Map a filename class code to the label this classifier will predict.

    Return the class name to train on, or None to drop the chip entirely.

    The five codes available, with counts and their site spread:

        TG  trench gully   782   shenzhen 715, quanzhou 67
        SS  plain seabed?  763   dongying 523, quanzhou/shenzhen/yantai 80 each
        RP  riprap         355   shenzhen 221, quanzhou 134
        SM  scour mark     123   shenzhen ONLY
        SW  sand wave       49   quanzhou 43, yantai 6

    Three things worth deciding rather than defaulting:

    1. HOW FINE. Five separate classes tell a reviewer the most, but SM is
       single-site and SW has 49 chips, so both will be unreliable and the
       confusion matrix will say so in public. Collapsing to three
       (gully / rock-armour / flat-or-bedform) trades detail for numbers that
       survive a jury question. Binary natural-vs-not is the most robust and
       adds least, because the false-alarm rate already measures that.

    2. WHERE RIPRAP GOES. taxonomy.py is explicit that riprap is PLACED rock
       armour -- man-made seabed modification, not natural at all. Calling it
       `natural` states something false; calling it `debris` implies a discrete
       recoverable object that is not there; dropping it discards 355 chips of
       the best false-positive bait in the project. The contract vocabulary is
       frozen at ghost_net | debris | natural | unknown, so a fourth answer
       would have to be `unknown`.

    3. WHETHER `SS` IS TRUSTED at all, given its name is inferred. Dropping it
       costs 763 chips but removes the only class whose meaning is a guess.

    Returning None for a code drops it, and the report counts what was dropped.
    """
    # Decided 26 Sep 2026 after looking at 8 chips per code across sites
    # (Vandit delegated the call). Three classes, each spanning >= 2 sites, so
    # no class can be learned purely as a site fingerprint:
    #
    #   sediment     SS + SW  812 chips, 4 sites. SS is NOT "plain seabed":
    #                quanzhou's is flat, but dongying's is textured sediment with
    #                dune scarps, the same bedform family as SW sand waves. So
    #                "open sediment surface, flat or textured", and SW joins it
    #                rather than standing alone at 49 chips.
    #   erosion      TG + SM  905 chips, 2 sites. Gullies and scour marks are
    #                both erosion; SM alone is shenzhen-only.
    #   rock_armour  RP       355 chips, 2 sites. Kept, not dropped: it is the
    #                best false-alarm bait in the project. PLACED rock is
    #                man-made, so whatever serves this classifier must report it
    #                as contract class `unknown`, never `natural`.
    return {"SS": "sediment", "SW": "sediment",
            "TG": "erosion", "SM": "erosion",
            "RP": "rock_armour"}.get(code)


def parse_chip(name: str) -> tuple[str, str] | None:
    """Return (site, code) for a CHINA-OFFSHORE chip, or None if it is not one."""
    m = CHIP_RE.match(name)
    if not m:
        return None
    return m.group("site"), m.group("code").upper()


def collect(processed: Path = PROCESSED) -> dict[str, list[tuple[Path, str, str]]]:
    """Gather every CHINA-OFFSHORE chip, keyed by the split it already lives in."""
    found: dict[str, list[tuple[Path, str, str]]] = {s: [] for s in SPLITS}
    for split in SPLITS:
        images = processed / split / "images"
        if not images.is_dir():
            raise SystemExit(
                f"! {images} does not exist.\n"
                "  This checkout has no dataset. Training data lives in the\n"
                "  working tree (E:\\New folder), not the docker-demo checkout."
            )
        for entry in images.iterdir():
            parsed = parse_chip(entry.name)
            if parsed is None:
                continue
            site, code = parsed
            found[split].append((entry, site, code))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build the chip-level natural classification set from CHINA-OFFSHORE."
    )
    ap.add_argument("--out", default=None, help=f"output root (default {OUT_ROOT})")
    ap.add_argument("--dry-run", action="store_true",
                    help="report the parse and write a contact sheet; copy nothing")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output root")
    ap.add_argument("--processed", default=str(PROCESSED),
                    help="detector dataset whose splits are inherited (the training tree's "
                         "ai/data/processed; this checkout has none)")
    args = ap.parse_args()

    out_root = Path(args.out) if args.out else OUT_ROOT
    processed = Path(args.processed)
    found = collect(processed)

    # --- the parse, checked against the provenance count before anything moves
    by_code: Counter[str] = Counter()
    site_matrix: dict[str, Counter[str]] = defaultdict(Counter)
    unparsed = 0
    for split in SPLITS:
        for _path, site, code in found[split]:
            by_code[code] += 1
            site_matrix[code][site] += 1

    total = sum(by_code.values())
    print(f"  {total} CHINA-OFFSHORE chips found across {len(SPLITS)} splits\n")
    print(f"  {'code':6} {'count':>6}  sites")
    for code, n in by_code.most_common():
        spread = ", ".join(f"{s} {c}" for s, c in site_matrix[code].most_common())
        flag = "" if EXPECTED.get(code) == n else f"  <-- expected {EXPECTED.get(code, '?')}"
        print(f"  {code:6} {n:>6}  {spread}{flag}")

    if by_code != Counter(EXPECTED):
        print(
            "\n! Parsed counts do not match the 2,072 recorded in the run provenance.\n"
            "  Refusing to build: a partial parse would train on a silent subset."
        )
        if not args.dry_run:
            return 1

    # --- single-site classes are named out loud, every run
    single = [c for c, sites in site_matrix.items() if len(sites) == 1]
    if single:
        print(
            f"\n  NOTE: {', '.join(single)} come from ONE site each. Accuracy on "
            "them\n  cannot be separated from learning that site. Report the "
            "breakdown beside\n  the score, per EXPERIMENT_GV7_PLAN.md 10.6."
        )

    if args.dry_run:
        print("\n  --dry-run: nothing written.")
        return 0

    # --- apply the human's mapping and copy, split inherited unchanged
    if out_root.exists() and not args.force:
        print(f"\n! {out_root} exists. Pass --force to rebuild it.")
        return 1
    if out_root.exists():
        shutil.rmtree(out_root)

    written: Counter[str] = Counter()
    dropped: Counter[str] = Counter()
    per_split: dict[str, Counter[str]] = {s: Counter() for s in SPLITS}
    for split in SPLITS:
        for path, site, code in found[split]:
            label = natural_class(code, site)
            if label is None:
                dropped[code] += 1
                continue
            dest = out_root / split / label
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest / path.name)
            written[label] += 1
            per_split[split][label] += 1

    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "CHINA-OFFSHORE, labels recovered from filenames",
        "splits_inherited_from": str(processed),
        "codes_parsed": dict(by_code),
        "site_matrix": {c: dict(s) for c, s in site_matrix.items()},
        "classes_written": dict(written),
        "per_split": {s: dict(c) for s, c in per_split.items()},
        "dropped_by_code": dict(dropped),
        "single_site_classes": single,
        "unparsed": unparsed,
    }
    (out_root / "build_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n  wrote {sum(written.values())} chips to {out_root}")
    for label, n in written.most_common():
        print(f"    {label:20} {n}")
    if dropped:
        print(f"  dropped {sum(dropped.values())}: {dict(dropped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
