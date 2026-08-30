"""Tests for the waterfall tiler and mask -> YOLO box conversion.

Tiling is where a dataset quietly goes wrong: coordinates are recomputed per
tile, objects get cut by boundaries, and the positive/negative balance is
decided by code rather than by the data. All three are invisible in a training
log and fatal to the result, so they are pinned here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

cv2 = pytest.importorskip("cv2")

SCRIPT = AI_ROOT / "scripts" / "masks_to_yolo.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("masks_to_yolo", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m          # required before exec: see test_voc_to_yolo
    spec.loader.exec_module(m)
    return m


def build(tmp_path: Path, frames: dict[str, tuple[np.ndarray, np.ndarray]], split="train") -> Path:
    """Write a fake dataset in the images/ + labels/ layout the tiler expects."""
    root = tmp_path / "raw" / "research" / "FAKEMASK"
    (root / split / "images").mkdir(parents=True, exist_ok=True)
    (root / split / "labels").mkdir(parents=True, exist_ok=True)
    for name, (img, mask) in frames.items():
        cv2.imwrite(str(root / split / "images" / f"{name}.png"), img)
        cv2.imwrite(str(root / split / "labels" / f"{name}.png"), mask)
    return root


def textured(h, w, seed=0):
    """Noise, not flat grey -- a uniform tile is rejected as dead by design."""
    return (np.random.default_rng(seed).normal(120, 30, (h, w)).clip(0, 255)).astype("uint8")


@pytest.fixture
def run(tmp_path, monkeypatch, mod):
    def _run(frames, split="train", argv_extra=(), out_name="out"):
        root = build(tmp_path, frames, split)
        monkeypatch.setattr(mod, "RAW_ROOT", root.parent.parent)
        monkeypatch.setitem(mod.DATASET_CLASS, "FAKEMASK", "shipwreck")
        out = tmp_path / out_name
        monkeypatch.setattr(
            sys, "argv",
            ["masks_to_yolo.py", "--dataset", "FAKEMASK", "--out", str(out), *argv_extra],
        )
        code = mod.main()
        return code, out

    return _run


def labels_in(out: Path, split="train") -> dict[str, str]:
    d = out / split / "labels"
    return {p.stem: p.read_text().strip() for p in d.glob("*.txt")} if d.exists() else {}


# --- geometry --------------------------------------------------------------

def test_tile_origins_always_reach_the_far_edge(mod):
    """Without a flush final tile the last strip of every waterfall is silently
    discarded -- and it is exactly where towed-sonar targets often sit."""
    o = mod.tile_origins(1000, 640, 480)
    assert o[0] == 0
    assert o[-1] == 1000 - 640
    assert all(x + 640 <= 1000 for x in o)


def test_short_axis_yields_one_tile(mod):
    assert mod.tile_origins(400, 640, 480) == [0]


def test_box_coordinates_are_correct_in_tile_space(run):
    """A single 100x100 object at (200,200) in a 640x640 frame: one tile, and
    the box must land where the object is."""
    img = textured(640, 640)
    mask = np.zeros((640, 640), "uint8")
    mask[200:300, 200:300] = 1
    code, out = run({"f": (img, mask)})
    assert code == 0
    line = labels_in(out)["f__x0_y0"]
    cid, cx, cy, w, h = line.split()
    assert cid == "0"                                     # wreck
    assert float(cx) == pytest.approx(250 / 640, abs=1e-3)
    assert float(cy) == pytest.approx(250 / 640, abs=1e-3)
    assert float(w) == pytest.approx(100 / 640, abs=1e-3)


def test_disjoint_objects_become_separate_boxes(run):
    """One box spanning both would be mostly empty water."""
    img = textured(640, 640)
    mask = np.zeros((640, 640), "uint8")
    mask[50:150, 50:150] = 1
    mask[400:500, 400:500] = 1
    code, out = run({"f": (img, mask)})
    assert len(labels_in(out)["f__x0_y0"].splitlines()) == 2


# --- the three decisions that break datasets -------------------------------

def test_edge_fragments_below_min_visible_are_dropped(run):
    """A sliver of hull labelled as a whole wreck teaches the detector that a
    scrap is an object. The overlapping stride keeps it whole in a neighbour."""
    img = textured(640, 1200)
    mask = np.zeros((1200, 640), "uint8")
    mask[620:660, 200:300] = 1          # straddles the y=640 tile boundary
    code, out = run({"f": (img, mask)}, argv_extra=("--min-visible", "0.9", "--neg-ratio", "0"))
    kept = [v for v in labels_in(out).values() if v]
    assert len(kept) <= 1, "a 9:1 split fragment must not be labelled twice as a whole object"


def test_tiny_boxes_are_dropped_and_their_tile_quarantined(run):
    """Dropping the box but keeping the tile would assert the image contains
    nothing -- training the model that a real object is background."""
    img = textured(640, 640)
    mask = np.zeros((640, 640), "uint8")
    mask[300:305, 300:315] = 1          # 5px short side, real but unlearnable
    code, out = run({"f": (img, mask)}, argv_extra=("--min-object-px", "1", "--neg-ratio", "-1"))
    assert "f__x0_y0" not in labels_in(out), "tile should be quarantined, not written as background"


def test_dead_tiles_are_rejected(run):
    """Pure black is the water column or padding, not seabed. As a negative it
    teaches the model that 'empty' looks like nothing at all."""
    img = np.zeros((640, 1280), "uint8")            # entirely dead
    img[:, :640] = textured(640, 640)               # one live half
    mask = np.zeros((640, 1280), "uint8")
    mask[100:200, 100:200] = 1
    code, out = run({"f": (img, mask)}, argv_extra=("--neg-ratio", "-1"))
    for stem in labels_in(out):
        assert not stem.endswith("x640_y0"), "the all-black tile should not have been kept"


def test_train_negatives_are_capped_by_ratio(run):
    """At ~1.6% foreground almost every tile is empty. Keeping them all gives a
    dataset where predicting 'nothing' scores brilliantly."""
    img = textured(640, 3200)
    mask = np.zeros((3200, 640), "uint8")
    mask[100:300, 100:300] = 1
    code, out = run({"f": (img, mask)}, argv_extra=("--neg-ratio", "1.0"))
    labs = labels_in(out)
    pos = sum(1 for v in labs.values() if v)
    neg = sum(1 for v in labs.values() if not v)
    assert pos >= 1
    assert neg <= pos, f"expected at most {pos} negatives, kept {neg}"


def test_validation_keeps_every_negative(run):
    """A 1:1 validation set flatters the false-positive rate, because real
    surveys are overwhelmingly empty seabed. Measure on the real ratio."""
    img = textured(640, 3200)
    mask = np.zeros((3200, 640), "uint8")
    mask[100:300, 100:300] = 1
    code, out = run({"f": (img, mask)}, split="test")
    labs = labels_in(out, "test")
    pos = sum(1 for v in labs.values() if v)
    neg = sum(1 for v in labs.values() if not v)
    assert neg > pos * 2, "val/test must keep the real negative ratio"


def test_object_free_split_is_kept_and_merged_into_train(run, tmp_path, monkeypatch, mod):
    """AI4Shipwrecks ships 25 terrain frames with empty masks. Budgeting their
    negatives off a positive count of zero would discard the cleanest hard
    negatives in the dataset, and writing them to their own split would leave
    them unreferenced by data.yaml."""
    root = build(tmp_path, {"t": (textured(640, 1280), np.zeros((640, 1280), "uint8"))}, split="terrain")
    (root / "train" / "images").mkdir(parents=True, exist_ok=True)
    (root / "train" / "labels").mkdir(parents=True, exist_ok=True)
    img = textured(640, 640)
    mask = np.zeros((640, 640), "uint8")
    mask[100:300, 100:300] = 1
    cv2.imwrite(str(root / "train" / "images" / "f.png"), img)
    cv2.imwrite(str(root / "train" / "labels" / "f.png"), mask)

    monkeypatch.setattr(mod, "RAW_ROOT", root.parent.parent)
    monkeypatch.setitem(mod.DATASET_CLASS, "FAKEMASK", "shipwreck")
    out = tmp_path / "merged"
    monkeypatch.setattr(sys, "argv", ["masks_to_yolo.py", "--dataset", "FAKEMASK", "--out", str(out)])
    assert mod.main() == 0

    assert not (out / "terrain").exists(), "negative-only split must not sit in its own directory"
    labs = labels_in(out, "train")
    assert any(k.startswith("t__") for k in labs), "terrain tiles should be in train"
    assert all(not labs[k] for k in labs if k.startswith("t__")), "terrain tiles must be background"


# --- outputs ---------------------------------------------------------------

def test_tile_names_carry_source_frame_and_origin(run):
    """Grouping tiles by source frame is what makes a leakage-safe split
    possible later; two tiles of one waterfall either side of a split boundary
    is leakage."""
    img = textured(640, 1280)
    mask = np.zeros((640, 1280), "uint8")
    mask[100:300, 100:300] = 1
    code, out = run({"survey7": (img, mask)})
    stems = list(labels_in(out))
    assert all(s.startswith("survey7__x") and "_y" in s for s in stems)


def test_data_yaml_and_report_are_written(run):
    img = textured(640, 640)
    mask = np.zeros((640, 640), "uint8")
    mask[100:300, 100:300] = 1
    code, out = run({"f": (img, mask)})
    yaml = (out / "data.yaml").read_text()
    assert "nc: 3" in yaml and "0: wreck" in yaml
    assert "leakage" in yaml, "the split warning must travel with the dataset"
    assert (out / "tiling_report.json").exists()
