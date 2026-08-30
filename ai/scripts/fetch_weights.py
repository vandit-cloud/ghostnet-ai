"""Download the pretrained YOLO weights that git deliberately does not carry.

    python ai/scripts/fetch_weights.py

Weights are build inputs, not source. Committing them makes every clone and
every branch switch drag tens of megabytes around for files that are byte-identical
and freely re-downloadable. Trained weights later are worse: they change often
and git stores each version in full, so history grows without bound.

Ultralytics resolves these names against its own release assets, so this is the
same download the library would do implicitly on first use -- made explicit, so
a fresh clone can be prepared offline before a demo instead of discovering the
need for a network connection five minutes beforehand.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
DEST = AI_ROOT / "models" / "pretrained"

# yolo11n for fast iteration, yolo11s as the 4 GB-VRAM training target.
WEIGHTS = ["yolo11n.pt", "yolo11s.pt"]


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics is not installed. Run: pip install -r ai/requirements.txt")
        return 1

    for name in WEIGHTS:
        target = DEST / name
        if target.exists():
            print("have    " + name + "  (" + str(round(target.stat().st_size / 1e6, 1)) + " MB)")
            continue
        print("fetching " + name + " ...")
        # YOLO() downloads into the ultralytics cache, wherever that is; move
        # the file to our own tree so the path is stable across machines.
        model = YOLO(name)
        src = Path(getattr(model, "ckpt_path", "") or name)
        if src.exists() and src.resolve() != target.resolve():
            shutil.move(str(src), str(target))
        if target.exists():
            print("saved   " + str(target.relative_to(AI_ROOT.parent)))
        else:
            print("WARNING could not place " + name + " into " + str(DEST))

    missing = [w for w in WEIGHTS if not (DEST / w).exists()]
    if missing:
        print("missing: " + ", ".join(missing))
        return 1
    print("all pretrained weights present in ai/models/pretrained/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
