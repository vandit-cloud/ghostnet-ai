"""Tests for the VOC -> YOLO converter and the class taxonomy.

Label corruption during format conversion is silent and unrecoverable: the
training run succeeds, the metrics look plausible, and the boxes are in the
wrong place. These tests are built around the specific ways real annotation
sets are broken, not around the happy path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from ghostnet.decision import normalise_class  # noqa: E402
from ghostnet.taxonomy import (  # noqa: E402
    CLASS_TO_ID,
    TRAINING_CLASSES,
    source_to_training,
    training_to_contract,
)

SCRIPT = AI_ROOT / "scripts" / "voc_to_yolo.py"


# --- taxonomy --------------------------------------------------------------

def test_training_class_ids_are_stable():
    """Order is the YOLO class id and therefore a wire format. Reshuffling it
    silently relabels every previously converted dataset."""
    assert TRAINING_CLASSES == ("wreck", "plane", "debris", "ghost_pot")
    assert CLASS_TO_ID == {"wreck": 0, "plane": 1, "debris": 2, "ghost_pot": 3}


@pytest.mark.parametrize(
    "source,expected",
    [("ship", "wreck"), ("Shipwreck", "wreck"), ("aircraft", "plane"),
     ("shipwreck", "wreck"), ("Boat", "wreck")],
)
def test_source_names_map_to_training_classes(source, expected):
    assert source_to_training(source)[0] == expected


@pytest.mark.parametrize("name", ["seafloor", "Rock", "sea-bed", "terrain", "ripple"])
def test_plain_seabed_names_are_background_not_a_class(name):
    """Nobody draws boxes around rocks. These must resolve to background -- an
    empty label -- and NOT to 'unmapped', which would quarantine exactly the
    hard-negative images the artificial-vs-natural metric depends on."""
    cls, reason = source_to_training(name)
    assert cls is None
    assert reason.startswith("background")


def test_fish_is_excluded_as_a_modality_mismatch():
    """The sonar_detect 'fish' class is fish-finder / echosounder imagery, not
    side-scan seabed, and several frames carry the annotator's red circle burned
    into the pixels. Same principle that excludes MDT and UATD."""
    cls, reason = source_to_training("fish")
    assert cls is None
    assert "WRONG MODALITY" in reason


def test_other_maps_to_debris():
    """'other' is unidentified artificial seabed returns -- the closest thing to
    real marine debris in any side-scan data located so far."""
    assert source_to_training("other")[0] == "debris"
    assert training_to_contract("debris") == "debris"


def test_excluded_and_unmapped_are_distinguishable():
    """A policy exclusion is a decision; an unmapped name is a bug. The
    converter reports them differently, so they must not look alike here."""
    cls, reason = source_to_training("victim")
    assert cls is None and reason.startswith("excluded")

    cls, reason = source_to_training("some_new_thing")
    assert cls is None and reason == "unmapped"


def test_training_classes_reach_the_contract_vocabulary():
    from ghostnet.contract import CLASS_VALUES

    for name in TRAINING_CLASSES:
        assert training_to_contract(name) in CLASS_VALUES


def test_detector_class_names_survive_into_the_contract():
    """The model may emit a training name or a raw dataset name. Neither should
    fall through to 'unknown' and quietly demote a real detection."""
    assert normalise_class("wreck") == "debris"
    assert normalise_class("plane") == "debris"
    assert normalise_class("ship") == "debris"
    assert normalise_class("natural") == "natural"
    assert normalise_class("seafloor") == "natural"
    assert normalise_class("something_nobody_taught_us") == "unknown"


# --- fixtures --------------------------------------------------------------

def make_voc(tmp_path: Path, *, objects: str, img_size=(640, 480), declared=None, name="f1") -> Path:
    """Build a minimal VOC dataset under a fake ai/data/raw layout."""
    root = tmp_path / "raw" / "research" / "TESTSET"
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "annotations").mkdir(parents=True, exist_ok=True)
    Image.new("L", img_size).save(root / "images" / f"{name}.jpg")
    w, h = declared if declared else img_size
    (root / "annotations" / f"{name}.xml").write_text(
        f"<annotation><filename>{name}.jpg</filename>"
        f"<size><width>{w}</width><height>{h}</height></size>{objects}</annotation>",
        encoding="utf-8",
    )
    return root


def box(name, xmin, ymin, xmax, ymax, difficult=0) -> str:
    return (
        f"<object><name>{name}</name><difficult>{difficult}</difficult>"
        f"<bndbox><xmin>{xmin}</xmin><ymin>{ymin}</ymin>"
        f"<xmax>{xmax}</xmax><ymax>{ymax}</ymax></bndbox></object>"
    )


# The converter resolves ai/data/raw from the package layout, so point it at a
# temporary tree by monkeypatching rather than by environment variable.
@pytest.fixture
def convert(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("voc_to_yolo", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Must be in sys.modules BEFORE exec: the script uses postponed annotation
    # evaluation, and @dataclass resolves them via sys.modules[cls.__module__].
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    def _run(objects, out_name="out", argv_extra=(), **kw):
        root = make_voc(tmp_path, objects=objects, **kw)
        monkeypatch.setattr(mod, "RAW_ROOT", root.parent.parent)
        out = tmp_path / out_name
        argv = ["voc_to_yolo.py", "--dataset", "TESTSET", "--out", str(out), *argv_extra]
        monkeypatch.setattr(sys, "argv", argv)
        code = mod.main()
        labels = sorted((out / "labels").glob("*.txt")) if (out / "labels").exists() else []
        text = labels[0].read_text().strip() if labels else ""
        return code, out, text

    return _run


# --- conversion correctness ------------------------------------------------

def test_centre_and_size_are_normalised(convert):
    """A 100x100 box at (100,100)-(200,200) on a 640x480 image."""
    code, _, text = convert(box("ship", 100, 100, 200, 200))
    assert code == 0
    cls, cx, cy, w, h = text.split()
    assert cls == "0"                                    # wreck
    assert float(cx) == pytest.approx(150 / 640, abs=1e-5)
    assert float(cy) == pytest.approx(150 / 480, abs=1e-5)
    assert float(w) == pytest.approx(100 / 640, abs=1e-5)
    assert float(h) == pytest.approx(100 / 480, abs=1e-5)


def test_wrong_declared_size_does_not_corrupt_coordinates(convert):
    """The classic silent killer: <size> left over from a template. If the XML
    were trusted, every box on this image would be scaled wrong."""
    code, out, text = convert(box("ship", 100, 100, 200, 200), declared=(1280, 960))
    assert code == 0
    _, cx, _, w, _ = text.split()
    assert float(cx) == pytest.approx(150 / 640, abs=1e-5)   # real size, not declared
    report = (out / "conversion_report.json").read_text()
    assert "size_mismatches" in report and "1280x960" in report


def test_out_of_bounds_box_is_clamped_not_dropped(convert):
    code, out, text = convert(box("ship", -50, -50, 700, 500))
    assert code == 0
    _, cx, cy, w, h = text.split()
    assert float(w) == pytest.approx(1.0, abs=1e-6)
    assert float(h) == pytest.approx(1.0, abs=1e-6)
    assert '"clamped_boxes": 1' in (out / "conversion_report.json").read_text()


def test_swapped_corners_are_repaired(convert):
    code, _, text = convert(box("ship", 200, 200, 100, 100))
    assert code == 0
    _, cx, cy, w, h = text.split()
    assert float(w) == pytest.approx(100 / 640, abs=1e-5)


def test_zero_area_box_is_dropped(convert):
    code, out, _ = convert(box("ship", 100, 100, 100, 100) + box("ship", 10, 10, 90, 90))
    assert code == 0
    assert '"dropped_degenerate_boxes": 1' in (out / "conversion_report.json").read_text()


def test_difficult_objects_are_excluded_by_default(convert):
    objs = box("ship", 10, 10, 90, 90) + box("ship", 100, 100, 200, 200, difficult=1)
    code, out, text = convert(objs)
    assert len(text.splitlines()) == 1
    assert '"dropped_difficult": 1' in (out / "conversion_report.json").read_text()

    code, out2, text2 = convert(objs, out_name="out2", argv_extra=("--keep-difficult",))
    assert len(text2.splitlines()) == 2


# --- the cases that are NOT failures ---------------------------------------

def test_image_with_no_objects_becomes_an_empty_label(convert):
    """An empty label file is how YOLO expresses 'background'. These are the
    hard negatives the plan depends on -- dropping them would throw away
    exactly the data that teaches the model not to cry wolf."""
    code, out, text = convert("")
    assert code == 1            # no boxes at all in this tiny fixture
    assert (out / "labels" / "f1.txt").exists()
    assert text == ""
    assert '"empty_labels_background_images": 1' in (out / "conversion_report.json").read_text()


def test_excluded_class_is_counted_not_silently_dropped(convert):
    code, out, _ = convert(box("victim", 10, 10, 90, 90) + box("ship", 100, 100, 200, 200))
    report = (out / "conversion_report.json").read_text()
    assert '"victim": 1' in report
    assert '"boxes_kept": 1' in report


def test_image_with_only_unmapped_objects_is_quarantined(convert):
    """The subtle one. An empty label is not "no annotation" -- it is a positive
    claim that the image contains nothing. Writing one for an image whose only
    object was an unrecognised class would train the detector that a real
    artificial object is background. Losing the image is the cheaper mistake."""
    code, out, _ = convert(box("submarine", 10, 10, 90, 90))
    assert not (out / "labels" / "f1.txt").exists()
    report = (out / "conversion_report.json").read_text()
    assert "f1.jpg" in report
    assert '"quarantined_unmapped_only"' in report


def test_excluded_only_image_still_becomes_a_negative(convert):
    """Contrast with the test above: an EXCLUDED class is a deliberate policy
    choice, so treating that region as background is exactly what we want."""
    code, out, text = convert(box("victim", 10, 10, 90, 90))
    assert (out / "labels" / "f1.txt").exists()
    assert text == ""
    assert '"empty_labels_background_images": 1' in (out / "conversion_report.json").read_text()


def test_unmapped_class_is_reported_loudly(convert, capsys):
    convert(box("submarine", 10, 10, 90, 90) + box("ship", 100, 100, 200, 200))
    assert "UNMAPPED" in capsys.readouterr().out


# --- outputs ---------------------------------------------------------------

def test_data_yaml_matches_the_taxonomy(convert):
    code, out, _ = convert(box("ship", 10, 10, 90, 90))
    yaml = (out / "data.yaml").read_text()
    assert "nc: 4" in yaml
    for i, name in enumerate(TRAINING_CLASSES):
        assert f"  {i}: {name}" in yaml


def test_collapse_produces_the_binary_framing(convert):
    code, out, text = convert(
        box("ship", 10, 10, 90, 90), argv_extra=("--collapse", "artificial")
    )
    assert code == 0
    # Only one class survives the collapse: "artificial". Background stays
    # implicit, as YOLO expects, so a single-class detector is correct here.
    assert "nc: 1" in (out / "data.yaml").read_text()
    assert text.split()[0] == "0"   # artificial
