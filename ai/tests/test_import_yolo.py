"""Tests for the YOLO-to-YOLO importer and its overlay screening.

The screening exists to keep scraped contamination out of training: software
screenshots, annotated figures, measurement bars, and the annotator's own
circles burned into the pixels. A detector that learns the overlay validates
beautifully and fails on real sonar.

The most important test here is the negative one: acoustic shadow must NOT be
screened out. It is flat and near-black, which looks exactly like a screenshot
region to a naive detector, and it is the single most informative feature in a
side-scan image.
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

SCRIPT = AI_ROOT / "scripts" / "import_yolo.py"
LIMITS = {"off_hue": 0.040, "flat_midtone": 0.120, "ui_rows": 0.060, "pure_paint": 0.150}


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("import_yolo", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def amber_sonar(h=640, w=640, seed=0) -> np.ndarray:
    """A plausible single-hue sonar frame: copper ramp plus speckle."""
    rng = np.random.default_rng(seed)
    grey = rng.normal(110, 28, (h, w)).clip(0, 255).astype("uint8")
    img = np.zeros((h, w, 3), "uint8")
    img[..., 0] = (grey * 0.25).astype("uint8")   # B
    img[..., 1] = (grey * 0.62).astype("uint8")   # G
    img[..., 2] = grey                            # R
    return img


# --- the signal that must never fire ---------------------------------------

def test_acoustic_shadow_is_not_treated_as_contamination(mod):
    """A large flat near-black region is a shadow, which is the best cue a
    side-scan image offers. Screening it out would discard the best data."""
    img = amber_sonar()
    img[150:500, 150:500] = 0            # 30% of the frame, pure black shadow
    assert mod.screen(mod.overlay_signals(img), LIMITS) is None


def test_clean_sonar_passes(mod):
    assert mod.screen(mod.overlay_signals(amber_sonar()), LIMITS) is None


def test_bright_returns_do_not_trip_the_hue_signal(mod):
    """Saturated amber highlights are real sonar, not paint. This is exactly
    what over-rejected six real debris frames at the first threshold."""
    img = amber_sonar()
    img[100:260, 100:260] = (40, 200, 255)      # vivid amber-yellow return
    assert mod.screen(mod.overlay_signals(img), LIMITS) is None


# --- the signals that must fire --------------------------------------------

def test_far_hue_annotation_is_caught(mod):
    """Cyan, green, blue and white paint sit far from any sonar ramp."""
    img = amber_sonar()
    cv2.rectangle(img, (60, 60), (400, 400), (255, 255, 0), 14)   # cyan box
    cv2.circle(img, (450, 450), 90, (0, 255, 0), 12)              # green ring
    reason = mod.screen(mod.overlay_signals(img), LIMITS)
    assert reason is not None and "coloured graphics" in reason


def test_large_painted_area_is_caught_regardless_of_hue(mod):
    """A big block of pure red trips pure_paint. It also trips flat_midtone,
    since a uniform block has no texture, and that check runs first -- so the
    signal is asserted directly and the rejection separately. Either
    attribution is correct; being rejected is what matters."""
    img = amber_sonar()
    img[:, :250] = (0, 0, 255)
    signals = mod.overlay_signals(img)
    assert signals["pure_paint"] > LIMITS["pure_paint"]
    assert mod.screen(signals, LIMITS) is not None


def test_KNOWN_LIMITATION_thin_red_on_amber_is_not_caught(mod):
    """Pinned deliberately, so nobody assumes protection that is not there.

    Red sits at hue 0 and the copper ramp near hue 17, so a red ring is not
    "off hue"; and a saturated amber return reaches the same saturation as
    paint. The two overlap in colour space and no threshold separates them.
    This is why the strategy is to reduce exposure -- 71 inspected frames of
    one class -- rather than to trust the filter."""
    img = amber_sonar()
    cv2.circle(img, (320, 320), 130, (0, 0, 255), 14)
    assert mod.screen(mod.overlay_signals(img), LIMITS) is None


def test_toolbar_strip_is_caught(mod):
    """Software screenshots put a flat mid-tone band across the full width."""
    img = amber_sonar()
    img[:70, :] = (190, 190, 190)
    reason = mod.screen(mod.overlay_signals(img), LIMITS)
    assert reason is not None


def test_caption_panel_is_caught(mod):
    img = amber_sonar()
    img[520:, :] = (255, 255, 255)        # white copyright banner
    assert mod.screen(mod.overlay_signals(img), LIMITS) is not None


# --- import behaviour -------------------------------------------------------

def build(tmp_path: Path, names, labels_by_image, images=None) -> Path:
    root = tmp_path / "raw" / "research" / "FAKEYOLO"
    (root / "train" / "images").mkdir(parents=True, exist_ok=True)
    (root / "train" / "labels").mkdir(parents=True, exist_ok=True)
    body = "names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(names)) + f"nc: {len(names)}\n"
    (root / "data.yaml").write_text(body)
    for stem, text in labels_by_image.items():
        img = (images or {}).get(stem, amber_sonar(320, 320))
        cv2.imwrite(str(root / "train" / "images" / f"{stem}.jpg"), img)
        (root / "train" / "labels" / f"{stem}.txt").write_text(text)
    return root


@pytest.fixture
def run(tmp_path, monkeypatch, mod):
    def _run(names, labels, argv_extra=(), images=None):
        root = build(tmp_path, names, labels, images)
        monkeypatch.setattr(mod, "RAW_ROOT", root.parent.parent)
        out = tmp_path / "out"
        monkeypatch.setattr(sys, "argv",
                            ["import_yolo.py", "--dataset", "FAKEYOLO", "--out", str(out), *argv_extra])
        code = mod.main()
        d = out / "train" / "labels"
        got = {p.stem: p.read_text().strip() for p in d.glob("*.txt")} if d.exists() else {}
        return code, got
    return _run


def test_source_ids_are_remapped_through_the_taxonomy(run):
    """The source numbers its classes, we number ours. 'shipwreck' is source id
    3 but training id 0; copying labels verbatim would relabel every box."""
    code, got = run(["aircraft", "fish", "other", "shipwreck"],
                    {"a": "3 0.5 0.5 0.2 0.2\n"})
    assert code == 0
    assert got["a"].split()[0] == "0"          # wreck


def test_only_classes_leaves_the_rest_behind(run):
    code, got = run(["aircraft", "fish", "other", "shipwreck"],
                    {"a": "2 0.5 0.5 0.2 0.2\n", "b": "3 0.5 0.5 0.2 0.2\n"},
                    argv_extra=("--only-classes", "other"))
    assert code == 0
    assert "b" not in got, "a frame with only unwanted classes must not be imported"
    assert got["a"].split()[0] == "2"          # debris


def test_frames_with_only_unwanted_classes_are_not_imported_as_background(run):
    """This dataset ships no verified-empty frames. Its 'background' is objects
    of classes we skipped, so asserting emptiness over them is a false lesson."""
    code, got = run(["other", "shipwreck"],
                    {"a": "0 0.5 0.5 0.2 0.2\n", "b": "1 0.5 0.5 0.2 0.2\n"},
                    argv_extra=("--only-classes", "other"))
    assert set(got) == {"a"}


def test_excluded_class_does_not_quarantine_the_frame(run):
    """'fish' is a policy exclusion, not an unknown name: the frame's other
    boxes are still worth importing."""
    code, got = run(["fish", "shipwreck"],
                    {"a": "0 0.5 0.5 0.2 0.2\n1 0.2 0.2 0.1 0.1\n"})
    assert code == 0
    assert got["a"].split()[0] == "0"          # only the wreck survived


def test_contaminated_frame_is_rejected_during_import(run):
    dirty = amber_sonar(320, 320)
    cv2.rectangle(dirty, (20, 20), (300, 300), (255, 255, 0), 14)   # cyan, far hue
    code, got = run(["other"], {"clean": "0 0.5 0.5 0.2 0.2\n", "dirty": "0 0.5 0.5 0.2 0.2\n"},
                    images={"dirty": dirty})
    assert "clean" in got
    assert "dirty" not in got


def test_no_screen_imports_everything(run):
    dirty = amber_sonar(320, 320)
    cv2.rectangle(dirty, (20, 20), (300, 300), (255, 255, 0), 14)
    code, got = run(["other"], {"dirty": "0 0.5 0.5 0.2 0.2\n"},
                    images={"dirty": dirty}, argv_extra=("--no-screen",))
    assert "dirty" in got
