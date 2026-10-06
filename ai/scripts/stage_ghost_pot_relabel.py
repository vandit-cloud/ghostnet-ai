"""Stage GHOSTVISION for a hand pass that ADDS the missing ghost_pot boxes.

    python ai/scripts/stage_ghost_pot_relabel.py            # build annotate/ghost_pot
    python ai/scripts/stage_ghost_pot_relabel.py --dry-run

Why (ai/experiments/ghost-pot-diagnosis/NOTES.md): the detector finds 72% of
training pots at conf 0.05 but scores them ~0.07, because many real pots carry
no box. Every unlabelled pot teaches "this is background".

What it writes: E:/New folder/ai/data/annotate/ghost_pot/
    images/<split>__<original>.jpg     one frame per ORIGINAL image
    labels/<same>.txt                  the existing boxes, class id 0
    labels/classes.txt, predefined_classes.txt   -> "ghost_pot"
    manifest.json                      staged name -> source copy, and every
                                       sibling copy of that original

One frame per original, not per copy
------------------------------------
The original download was pruned on 5 Sep (raw/research/PRUNED.md). Only the
Roboflow export survives: 6,655 frames, several augmented copies per original,
many rotated or sheared. Labelling copies would mean drawing the same pot up
to 12 times, and a box drawn on a rotated copy cannot be mapped to the others
(the transform is not recorded). So each original is labelled once, on its
least-distorted copy: no black rotation wedge if one exists, then the copy
with the most existing boxes. The rebuild then trains on these labelled
originals with our own physically valid augmentation, instead of on
Roboflow's copies.

Name collisions: one original name can cover different scenes (copies 6/10/12
of Rec5_wcp_ss_star_00010 are another image). Unrotated copies of one name are
therefore split into distinct scenes by a 16x16 thumbnail comparison, flips
included, and each scene is staged once.

Never overwrites: if annotate/ghost_pot exists, it refuses. That folder is
the hand-labelling working directory, and a rerun must not destroy a session's
work.
"""

from __future__ import annotations

import argparse
import collections
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

INTERIM = Path("E:/New folder/ai/data/interim/GHOSTVISION")
DEST = Path("E:/New folder/ai/data/annotate/ghost_pot")
SPLITS = {"test": "test", "train": "train", "valid": "val"}
POT = 3


def original(name: str) -> str:
    return name.split(".rf.")[0]


def rotated(g: np.ndarray) -> bool:
    k = max(8, g.shape[0] // 20)
    return any((c <= 3).mean() >= 0.9 for c in (g[:k, :k], g[:k, -k:], g[-k:, :k], g[-k:, -k:]))


def thumb(g: np.ndarray) -> np.ndarray:
    t = cv2.resize(g, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
    return (t - t.mean()) / (t.std() + 1e-6)


def same_scene(a: np.ndarray, b: np.ndarray) -> bool:
    """Correlation of 16x16 thumbnails, best over the four flips Roboflow may apply."""
    return max(float((a * f).mean()) for f in (b, b[:, ::-1], b[::-1], b[::-1, ::-1])) > 0.8


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if DEST.exists() and not a.dry_run:
        print(f"refusing: {DEST} exists (hand-labelling work may be in it)")
        return 1

    staged, manifest = [], {}
    for src_split, tag in SPLITS.items():
        groups = collections.defaultdict(list)
        for p in sorted((INTERIM / src_split / "images").iterdir()):
            groups[original(p.name)].append(p)
        n_scenes = 0
        for orig, copies in groups.items():
            info = []
            for p in copies:
                g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                lbl = INTERIM / src_split / "labels" / f"{p.stem}.txt"
                boxes = [l for l in lbl.read_text().splitlines() if l.split() and int(l.split()[0]) == POT] \
                    if lbl.exists() else []
                info.append({"path": p, "rot": rotated(g), "boxes": boxes, "thumb": thumb(g)})
            pool = [c for c in info if not c["rot"]] or info
            pool.sort(key=lambda c: -len(c["boxes"]))
            scenes = []
            for c in pool:
                if not any(same_scene(c["thumb"], s["thumb"]) for s in scenes):
                    scenes.append(c)
            for i, c in enumerate(scenes):
                n_scenes += 1
                name = f"{tag}__{orig}" + (f"__scene{i + 1}" if len(scenes) > 1 else "")
                staged.append((name, c))
                manifest[name] = {"split": tag, "source": str(c["path"]),
                                  "existing_boxes": len(c["boxes"]),
                                  "siblings": [str(x["path"]) for x in info]}
        print(f"  {tag:5s}: {len(groups):5d} originals -> {n_scenes:5d} frames to label")

    total_boxes = sum(len(c["boxes"]) for _, c in staged)
    print(f"  total: {len(staged)} frames, {total_boxes} existing boxes pre-loaded")
    if a.dry_run:
        return 0

    (DEST / "images").mkdir(parents=True)
    (DEST / "labels").mkdir()
    for name, c in staged:
        shutil.copy2(c["path"], DEST / "images" / f"{name}{c['path'].suffix}")
        lines = ["0 " + " ".join(b.split()[1:5]) for b in c["boxes"]]
        (DEST / "labels" / f"{name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
    (DEST / "labels" / "classes.txt").write_text("ghost_pot\n")
    (DEST / "predefined_classes.txt").write_text("ghost_pot\n")
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=1))
    shutil.copytree(DEST / "labels", DEST / "_labels_before_hand_pass")  # the diff = what was missing
    print(f"  written: {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
