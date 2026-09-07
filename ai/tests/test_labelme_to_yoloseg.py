"""D2: labelme polygons -> YOLO segmentation labels."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT / "scripts"))

from labelme_to_yoloseg import convert_one  # noqa: E402


def doc(shapes, w=100, h=200):
    return {"imageWidth": w, "imageHeight": h, "shapes": shapes}


def poly(points, label="ghost_net"):
    return {"label": label, "shape_type": "polygon", "points": points}


def test_polygon_is_normalised_against_its_own_image():
    lines, _ = convert_one(doc([poly([[0, 0], [100, 0], [50, 200]])]), 0, "ghost_net")
    assert lines == ["0 0.000000 0.000000 1.000000 0.000000 0.500000 1.000000"]


def test_output_has_no_width_height_pair():
    """YOLO-seg is class + point list. A detection-shaped label in a -seg
    dataset trains silently and wrongly, so pin the shape."""
    lines, _ = convert_one(doc([poly([[10, 10], [20, 10], [20, 20], [10, 20]])]), 0, "ghost_net")
    fields = lines[0].split()
    assert fields[0] == "0"
    assert len(fields) == 9, "4 points -> 8 coordinates + class id"


def test_other_labels_are_skipped_not_converted():
    lines, skipped = convert_one(
        doc([poly([[0, 0], [10, 0], [5, 10]], label="debris")]), 0, "ghost_net"
    )
    assert lines == [] and skipped == 1


def test_a_rectangle_is_refused_loudly():
    """Reverting to the rectangle tool is the exact mistake this track exists
    to undo, so it must fail rather than convert."""
    shape = {"label": "ghost_net", "shape_type": "rectangle", "points": [[0, 0], [10, 10]]}
    with pytest.raises(ValueError, match="not a polygon"):
        convert_one(doc([shape]), 0, "ghost_net")


def test_a_degenerate_polygon_is_refused():
    with pytest.raises(ValueError, match="at least 3"):
        convert_one(doc([poly([[0, 0], [10, 10]])]), 0, "ghost_net")


def test_vertices_outside_the_canvas_are_clamped_not_dropped():
    """labelme allows a vertex a pixel off-canvas. Out-of-range coordinates make
    ultralytics discard the whole file, so clamping keeps the annotation."""
    lines, _ = convert_one(doc([poly([[-5, -5], [105, 0], [50, 250]])]), 0, "ghost_net")
    vals = [float(v) for v in lines[0].split()[1:]]
    assert all(0.0 <= v <= 1.0 for v in vals)


def test_multiple_nets_in_one_image_become_multiple_lines():
    d = doc([poly([[0, 0], [10, 0], [5, 10]]), poly([[20, 20], [30, 20], [25, 30]])])
    lines, _ = convert_one(d, 0, "ghost_net")
    assert len(lines) == 2
