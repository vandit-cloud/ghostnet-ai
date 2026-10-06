"""Add HARD NEGATIVES to the ghost_net segmentation dataset.

    python ai/scripts/build_net_seg_hardneg.py
    python ai/scripts/train_net_seg.py --data "E:/New folder/ai/data/net_seg_hardneg/data.yaml" \
        --epochs 1000 --name gv9n-netseg-hardneg-s0 --seed 0
    python ai/scripts/evaluate_net_negatives.py --weights <best.pt>

Reads  ai/data/net_seg/{train,val,test}                 (73 net chips, 425 polygons)
       ai/data/processed/{train,val,test}/CHINA-OFFSHORE__*   (empty seabed chips)
Writes ai/data/net_seg_hardneg/{train,val,test}/{images,labels}
       ai/data/net_seg_hardneg/neg_holdout/images       (false-alarm ruler, never trained on)
       ai/data/net_seg_hardneg/{data.yaml,negatives.json,sheet_*.png}

The gap this closes
-------------------
Every image the segmentation model has ever seen contains a net: 51/11/11 net
chips and zero negatives. It has never been shown seabed and told "nothing
here", and its false-alarm rate on empty seabed has never been MEASURED,
because the test split has no empty seabed to fire on. Its published precision
(0.66) is precision inside net chips only.

Why China-Offshore, and why stratified
--------------------------------------
Its natural-seabed chips (trench/gully TG, sediment SS, rock/reef RP, scour
mark SM, sand wave SW) include the SAME SITES as the net chips -- Quanzhou and
Yantai -- so they share the sensor and the coast. A negative from a different
sonar would teach "this sensor = no net", the one-source confound the texture
test already caught once. Sampling is even across the 11 site/type groups so
no single seabed type (537 of 1,453 are Shenzhen trench/gully) dominates.

One variable against the gv7d3 baseline
---------------------------------------
Train gains negatives; val and test are the SAME 11 + 11 net chips, so recall
and centroid numbers stay comparable with gv7d3's 3 seeds. Held-out negatives
go in a SEPARATE folder, read only by evaluate_net_negatives.py: putting them
in val would change which checkpoint becomes best.pt (a second variable), and
in test they would change mAP's denominator relative to the baseline.

Split hygiene: train negatives come from processed/train only; held-out ones
from processed/val and processed/test only -- build_dataset.py split those by
group, so no held-out chip shares a source group with a training chip.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import shutil
from pathlib import Path

import cv2
import numpy as np

PROCESSED = Path("E:/New folder/ai/data/processed")
DEFAULT_SRC = Path("E:/New folder/ai/data/net_seg")
DEFAULT_DST = Path("E:/New folder/ai/data/net_seg_hardneg")
SEED = 0


def groups(splits: tuple[str, ...]) -> dict[str, list[Path]]:
    by = collections.defaultdict(list)
    for s in splits:
        for p in sorted((PROCESSED / s / "images").glob("CHINA-OFFSHORE__*")):
            label = PROCESSED / s / "labels" / f"{p.stem}.txt"
            if label.exists() and label.read_text().strip():
                continue  # not empty: never use a labelled chip as a negative
            by[p.name.split("__")[1].rsplit("_", 1)[0]].append(p)
    return by


def stratified(by: dict[str, list[Path]], n: int, rng: random.Random) -> list[Path]:
    """Even per group; groups too small to fill their share donate the rest."""
    pools = {k: rng.sample(v, len(v)) for k, v in by.items()}
    picked: list[Path] = []
    while len(picked) < n and any(pools.values()):
        for k in sorted(pools):
            if pools[k] and len(picked) < n:
                picked.append(pools[k].pop())
    return picked


def sheet(paths: list[Path], out: Path, k: int = 40, cell: int = 128) -> None:
    tiles = []
    for p in paths[:k]:
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        tiles.append(cv2.resize(g, (cell, cell), interpolation=cv2.INTER_AREA))
    while len(tiles) % 10:
        tiles.append(np.full((cell, cell), 255, np.uint8))
    rows = [np.hstack(tiles[i:i + 10]) for i in range(0, len(tiles), 10)]
    cv2.imwrite(str(out), np.vstack(rows))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--dst", type=Path, default=DEFAULT_DST)
    ap.add_argument("--neg-ratio", type=float, default=2.0, help="train negatives per train positive")
    ap.add_argument("--holdout", type=int, default=100, help="held-out negatives for the false-alarm ruler")
    a = ap.parse_args()
    if a.dst.exists():
        raise SystemExit(f"{a.dst} exists -- delete it deliberately before rebuilding")
    rng = random.Random(SEED)

    for split in ("train", "val", "test"):
        shutil.copytree(a.src / split, a.dst / split)
    n_pos = len(list((a.dst / "train" / "images").iterdir()))

    train_negs = stratified(groups(("train",)), int(round(n_pos * a.neg_ratio)), rng)
    for p in train_negs:
        shutil.copy2(p, a.dst / "train" / "images" / p.name)
        (a.dst / "train" / "labels" / f"{p.stem}.txt").write_text("")

    hold = stratified(groups(("val", "test")), a.holdout, rng)
    (a.dst / "neg_holdout" / "images").mkdir(parents=True)
    for p in hold:
        shutil.copy2(p, a.dst / "neg_holdout" / "images" / p.name)

    def tally(ps):
        return dict(sorted(collections.Counter(p.name.split("__")[1].rsplit("_", 1)[0] for p in ps).items()))

    (a.dst / "negatives.json").write_text(json.dumps({
        "train_positives": n_pos, "train_negatives": len(train_negs), "train_negatives_by_group": tally(train_negs),
        "holdout_negatives": len(hold), "holdout_by_group": tally(hold),
        "train_negative_files": [p.name for p in train_negs], "holdout_files": [p.name for p in hold],
        "seed": SEED, "source": str(PROCESSED)}, indent=2))
    (a.dst / "data.yaml").write_text(
        "# ghost_net segmentation + HARD NEGATIVES (empty China-Offshore seabed chips in train).\n"
        "# Built by ai/scripts/build_net_seg_hardneg.py -- do not hand-edit.\n"
        "# val/test are the SAME net chips as net_seg; neg_holdout/ is read by evaluate_net_negatives.py only.\n"
        f"path: {a.dst.as_posix()}\ntrain: train/images\nval: val/images\ntest: test/images\n"
        "names:\n  0: ghost_net\n")
    sheet(train_negs, a.dst / "sheet_train_negatives.png")
    sheet(hold, a.dst / "sheet_holdout_negatives.png")
    print(f"train: {n_pos} positives + {len(train_negs)} negatives {tally(train_negs)}")
    print(f"holdout negatives: {len(hold)} {tally(hold)}")


if __name__ == "__main__":
    main()
