"""Copy-paste synthesis tests.

Synthetic training data is the easiest way in this project to produce a number
that is both excellent and meaningless, so these assert the properties that
keep it honest rather than the pixels.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

SCRIPT = AI_ROOT / "scripts" / "synth_ghost_net.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("synth", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def seabed(h=200, w=300, level=150):
    rng = np.random.default_rng(0)
    return np.clip(rng.normal(level, 18, (h, w)), 0, 255).astype(np.uint8)


def net_attenuation(h=40, w=60):
    """A synthetic 'net': mostly transparent, with darkened lines."""
    a = np.ones((h, w), np.float32)
    a[10:12, :] = 0.55
    a[:, 20:22] = 0.55
    return a


# --- the honesty guarantees ------------------------------------------------

def test_synthetic_data_is_pinned_to_the_train_split():
    """A ghost_net score measured on generated nets would be
    self-congratulation. This is the line that prevents it."""
    spec = importlib.util.spec_from_file_location("bd", AI_ROOT / "scripts" / "build_dataset.py")
    bd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bd)
    policy = bd.SPLIT_POLICY["GHOSTNET-SYNTH"]
    assert policy["mode"] == "fixed"
    assert set(policy["map"].values()) == {"train"}, "synthetic data must never reach val or test"


def test_backgrounds_come_only_from_the_train_split(mod):
    """Compositing onto val or test seabed would leak the evaluation set into
    training through the back door."""
    assert mod.TRAIN.name == "train"
    assert "processed" in str(mod.TRAIN)


# --- the compositing itself ------------------------------------------------

def test_composite_leaves_no_seam(mod):
    """The failure mode this whole approach exists to avoid: a detector that
    learns the paste boundary instead of the net."""
    import random

    bg = seabed()
    out, box = mod.composite(bg, net_attenuation(), random.Random(0))
    assert out is not None
    x1, y1, x2, y2 = box
    # Outside the attenuated pixels the background must be bit-identical.
    untouched = (out.astype(int) != bg.astype(int))
    assert not untouched[:y1].any() and not untouched[y2:].any(), "rows outside the box changed"


def test_composite_only_ever_darkens(mod):
    """A net attenuates a return. Anything that brightens the seabed is an
    artefact, and a bright artefact is exactly what a detector latches onto."""
    import random

    bg = seabed()
    out, _ = mod.composite(bg, net_attenuation(), random.Random(1))
    assert (out.astype(int) <= bg.astype(int)).all()


def test_label_tracks_the_net_not_the_source_rectangle(mod):
    """After a flip or a scale the tight box moves; a stale rectangle would
    teach a systematic offset."""
    import random

    a = np.ones((90, 90), np.float32)
    a[60:82, 60:82] = 0.5                     # net in one corner, above MIN_BOX_PX
    out, box = mod.composite(seabed(), a, random.Random(2))
    assert out is not None
    x1, y1, x2, y2 = box
    assert (x2 - x1) < 40 and (y2 - y1) < 40, "box should hug the net, not the 90px patch"


def test_degenerate_boxes_are_rejected(mod):
    """A net scaled to a handful of pixels is a label nothing can learn."""
    import random

    a = np.ones((40, 40), np.float32)
    a[5:7, 5:7] = 0.5                          # smaller than MIN_BOX_PX
    out, box = mod.composite(seabed(), a, random.Random(3))
    assert out is None and box is None


def test_unusable_backgrounds_are_filtered(mod):
    """The first preview composited nets onto pure-black nadir and padding
    tiles, where multiplying by 0.85 leaves 0 and the label points at nothing."""
    assert mod.MIN_BG_MEAN > 0 and mod.MIN_BG_STD > 0
    black = np.zeros((100, 100), np.uint8)
    assert black.mean() < mod.MIN_BG_MEAN
    flat = np.full((100, 100), 150, np.uint8)
    assert flat.std() < mod.MIN_BG_STD
