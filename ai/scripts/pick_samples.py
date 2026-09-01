"""Copy test tiles that actually contain objects into a folder you can test on.

    python ai/scripts/pick_samples.py --class ghost_pot --n 10 --out "E:/sonar-test"
    python ai/scripts/pick_samples.py --class any --n 20
    python ai/scripts/pick_samples.py --list

The test split is 77% empty seabed -- 2,620 of 3,410 tiles. Browsing that folder
and grabbing files gives you tiles with nothing in them, the model correctly
reports nothing, and it looks broken. This picks from the 790 tiles that hold a
labelled object, densest first, so a smoke test actually tests something.

Densest first is deliberate: a tile with one tiny box at the frame edge is a
legitimate test but a terrible demonstration, and when you are trying to answer
"does this work at all" you want the unambiguous cases first.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = AI_ROOT / "data" / "processed"
CLASSES = {0: "wreck", 1: "plane", 2: "debris", 3: "ghost_pot"}


def scan(split: str) -> dict[str, list[tuple[int, Path]]]:
    """Map class name -> [(object count, label path)], for non-empty labels."""
    by: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for lp in sorted((PROCESSED / split / "labels").glob("*.txt")):
        rows = [r for r in lp.read_text(encoding="utf-8").splitlines() if r.strip()]
        if not rows:
            continue
        for c in {int(r.split()[0]) for r in rows}:
            by[CLASSES[c]].append((len(rows), lp))
        by["any"].append((len(rows), lp))
    return by


def image_for(label: Path, split: str) -> Path | None:
    """Find the image beside a label. GhostVision is .jpg, AI4Shipwrecks .png."""
    for suffix in (".png", ".jpg", ".jpeg"):
        p = PROCESSED / split / "images" / (label.stem + suffix)
        if p.exists():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Copy test tiles that contain objects.")
    ap.add_argument("--class", dest="cls", default="ghost_pot",
                    choices=[*CLASSES.values(), "any"],
                    help="which class to sample (default ghost_pot, the strongest one)")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default="E:/sonar-test")
    ap.add_argument("--split", default="test", choices=["test", "val", "train"])
    ap.add_argument("--list", action="store_true", help="just show what is available")
    ap.add_argument("--clean", action="store_true", help="empty the output folder first")
    args = ap.parse_args()

    if not (PROCESSED / args.split / "labels").exists():
        print(f"no {args.split} split at {PROCESSED} -- run build_dataset.py first")
        return 1

    by = scan(args.split)

    print(f"\n  {args.split} split, tiles containing a labelled object:")
    for name in [*CLASSES.values(), "any"]:
        n = len(by.get(name, []))
        note = ""
        if name == "ghost_pot":
            note = "  <- strongest class, use these"
        elif name in ("plane", "debris"):
            note = "  <- too few to judge the model on"
        print(f"    {name:10} {n:5}{note}")

    if args.list:
        print()
        return 0

    picks = sorted(by.get(args.cls, []), reverse=True)[: args.n]
    if not picks:
        print(f"\nno tiles found for class '{args.cls}'")
        return 1

    out = Path(args.out).expanduser()
    if args.clean and out.exists():
        for f in out.iterdir():
            if f.is_file():
                f.unlink()
        print(f"\n  emptied {out}")
    out.mkdir(parents=True, exist_ok=True)

    copied = 0
    print(f"\n  copying {len(picks)} '{args.cls}' tiles to {out}\n")
    for count, lp in picks:
        img = image_for(lp, args.split)
        if img is None:
            print(f"    ! no image beside {lp.name}")
            continue
        shutil.copy(img, out / img.name)
        copied += 1
        print(f"    {count:3} object(s)  {img.name}")

    print(f"\n  {copied} copied. Now run:")
    print(f'    & $PY ai\\scripts\\try_model.py --images "{out}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
