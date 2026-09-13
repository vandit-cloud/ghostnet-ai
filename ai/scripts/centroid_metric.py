"""Centroid detection rate for ghost nets, alongside mAP50.

Why this exists
---------------
EXPERIMENT_GV7_PLAN.md 10.4 commits to adopting this metric "regardless" of any
Track D outcome, and the argument is GhostNetZero's:

  IoU-based metrics understate operational utility for a long, thin, fragmented
  target. You only need to point a diver at the right spot. Three disconnected
  polygons over one continuous net should count as ONE true positive, not one
  hit and two false alarms.

That is not special pleading. A ghost net in side-scan is a chain of floatline
beads with gaps; where one annotator draws one polygon another draws four, and
IoU punishes the model for a fragmentation that has no operational meaning. Our
own D2 result -- mask mAP50 0.204 against box recall 0.525 -- is partly that
penalty rather than a real localisation failure.

What this does NOT do
---------------------
It does not rescue a zero. gv5 scored `ghost_net` recall 0.000 -- no predictions
at all -- and no matching rule repairs an empty prediction set. This metric
changes how a NON-empty result reads, which is why it is only worth wiring now
that D2 produces predictions.

It also does not escape section 4.3. The test split is 11 chips. Every number
this prints is an upper bound reported under Tier 1 of section 10.5 -- a review
candidate, never a detection claim.

Usage
-----
    python ai/scripts/centroid_metric.py \
        --weights ai/experiments/gv7d2b-netseg/weights/best.pt \
        --split test --device cpu
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NET_SEG = ROOT / "ai" / "data" / "net_seg"
EXPERIMENTS = ROOT / "ai" / "experiments"
DEFAULT_WEIGHTS = EXPERIMENTS / "gv7d2b-netseg" / "weights" / "best.pt"


# --------------------------------------------------------------------------
# Geometry. Coordinates are NORMALISED (0-1) throughout, so a tolerance is
# expressed as a fraction of the chip's diagonal and does not silently change
# meaning when chip size does.
# --------------------------------------------------------------------------

@dataclass
class Shape:
    """One annotated or predicted polygon, plus what it reduces to."""
    points: list[tuple[float, float]]
    score: float = 1.0
    centroid: tuple[float, float] = field(init=False)

    def __post_init__(self) -> None:
        self.centroid = polygon_centroid(self.points)


def polygon_centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Area-weighted centroid, falling back to the vertex mean.

    The shoelace centroid is the right answer for a filled polygon, but a net
    annotation is a long thin strip and can be very nearly degenerate -- a
    near-zero signed area makes the shoelace formula explode. So we detect that
    and fall back to the vertex mean, which for a strip traced down its middle
    is close to the same point and is always finite.
    """
    if not points:
        return (float("nan"), float("nan"))
    if len(points) < 3:
        return (sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points))

    a = cx = cy = 0.0
    for i in range(len(points)):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % len(points)]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-9:  # degenerate strip
        return (sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points))
    return (cx / (6.0 * a), cy / (6.0 * a))


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Euclidean distance in normalised units (1.0 == the chip's full width)."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def aspect_correct(points: list[tuple[float, float]], aspect: float) -> list[tuple[float, float]]:
    """Rescale y so that distance means the same thing in both axes.

    YOLO labels normalise x by width and y by height INDEPENDENTLY, which is
    fine for boxes and wrong for distances. Our chips are not square and not
    even consistently shaped -- 322x280, 401x316, 331x112 -- so on the 3:1 chip
    a "distance of 0.10" is 33 px across and 11 px down. A circular tolerance
    in that space is an ellipse on the seabed, and since side-scan across-track
    is RANGE and along-track is vessel travel, it is an ellipse whose axes mean
    different physical things.

    Multiplying y by height/width puts both axes in units of chip WIDTH, so a
    tolerance is a circle again. Left uncorrected this biases every chip
    differently, which is the sort of error that survives review because every
    individual number still looks plausible.
    """
    return [(x, y * aspect) for x, y in points]


# --------------------------------------------------------------------------
# THE METRIC. Rule C: cluster into nets first, then match nets one-to-one.
#
# The unit of account is a NET, not a polygon. Our 11 test chips carry 59
# ground-truth polygons because one physical net was traced as several bead
# chains, and the model fragments too -- along different seams. Counting
# polygons therefore measures annotation style as much as model skill.
#
# So both sides are collapsed into nets by the same rule before anything is
# compared, and a net is matched at most once. Over-prediction is charged for
# (unlike the lenient rule) but only once per spurious net, not once per
# fragment -- which is the fragmentation penalty this metric exists to drop.
#
# Consequence, and it is deliberate: the denominator is the number of ground-
# truth NETS, not 59. These numbers do not sit on the same footing as our
# mAP50 figures and the summary says so.
# --------------------------------------------------------------------------

def cluster_shapes(shapes: list[Shape], tolerance: float) -> list[list[Shape]]:
    """Group shapes into nets by single-linkage on centroid distance.

    Single linkage -- transitive, so A joins B joins C even when A and C are
    far apart -- is usually the objectionable property of this algorithm. Here
    it is the correct one: a ghost net IS a chain. A 400 m net traced as six
    bead chains end to end has distant endpoints and is still one net, and only
    a transitive rule recovers that. A compactness-based clustering would split
    exactly the long nets we most want counted once.
    """
    n = len(shapes)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if distance(shapes[i].centroid, shapes[j].centroid) <= tolerance:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj

    groups: dict[int, list[Shape]] = {}
    for i, shape in enumerate(shapes):
        groups.setdefault(find(i), []).append(shape)
    return list(groups.values())


def cluster_centroid(cluster: list[Shape]) -> tuple[float, float]:
    """Where the diver is sent: the mean of the member centroids.

    Unweighted on purpose. Weighting by polygon area would drag the point
    towards whichever end of the net happened to be traced in the most detail,
    which is an artefact of annotation effort rather than of the net.
    """
    return (sum(s.centroid[0] for s in cluster) / len(cluster),
            sum(s.centroid[1] for s in cluster) / len(cluster))


def match_centroids(
    truth: list[Shape],
    predictions: list[Shape],
    tolerance: float,
) -> tuple[int, int, int]:
    """Decide which ground-truth nets were found, and what was a false alarm.

    Both lists are for ONE chip. Coordinates are normalised 0-1; `tolerance` is
    a distance in those units (0.10 == a tenth of the chip's width). The same
    tolerance does both jobs -- clustering and matching -- because they are the
    same claim: "these two points refer to the same net."

    Returns:
        (hits, misses, false_alarms), counted in NETS

        hits + misses == number of ground-truth clusters, which is <= len(truth).
    """
    truth_nets = cluster_shapes(truth, tolerance)
    pred_nets = cluster_shapes(predictions, tolerance)

    truth_pts = [cluster_centroid(c) for c in truth_nets]
    pred_pts = [cluster_centroid(c) for c in pred_nets]

    # Greedy nearest-first, one-to-one. Sorting by distance before consuming
    # means the closest pair in the chip is always resolved first, so the
    # result does not depend on the order shapes happened to be listed in.
    pairs = sorted(
        ((distance(t, p), ti, pi)
         for ti, t in enumerate(truth_pts)
         for pi, p in enumerate(pred_pts)
         if distance(t, p) <= tolerance),
        key=lambda x: (x[0], x[1], x[2]),
    )

    matched_truth: set[int] = set()
    matched_pred: set[int] = set()
    for _, ti, pi in pairs:
        if ti in matched_truth or pi in matched_pred:
            continue
        matched_truth.add(ti)
        matched_pred.add(pi)

    hits = len(matched_truth)
    misses = len(truth_nets) - hits
    false_alarms = len(pred_nets) - len(matched_pred)
    return hits, misses, false_alarms


# --------------------------------------------------------------------------
# Loading, running and reporting. Mechanical.
# --------------------------------------------------------------------------

def load_truth(label_path: Path, aspect: float = 1.0) -> list[Shape]:
    """Read one YOLO-seg label file: `class x1 y1 x2 y2 ...`, normalised."""
    shapes: list[Shape] = []
    if not label_path.exists():
        return shapes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 7:  # class + at least 3 points
            continue
        coords = [float(v) for v in parts[1:]]
        pts = list(zip(coords[0::2], coords[1::2]))
        shapes.append(Shape(points=aspect_correct(pts, aspect)))
    return shapes


def load_predictions(result, conf: float, aspect: float = 1.0) -> list[Shape]:
    """Pull normalised polygons out of one Ultralytics result."""
    shapes: list[Shape] = []
    masks = getattr(result, "masks", None)
    if masks is None or masks.xyn is None:
        return shapes
    scores = result.boxes.conf.tolist() if result.boxes is not None else []
    for i, poly in enumerate(masks.xyn):
        score = float(scores[i]) if i < len(scores) else 1.0
        if score < conf:
            continue
        pts = [(float(x), float(y)) for x, y in poly]
        if pts:
            shapes.append(Shape(points=aspect_correct(pts, aspect), score=score))
    return shapes


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    ap.add_argument("--data", default=str(NET_SEG))
    ap.add_argument("--split", default="test", choices=["test", "val", "train"])
    ap.add_argument("--tolerance", type=float, default=0.10,
                    help="match radius, normalised chip units (default 0.10)")
    ap.add_argument("--conf", type=float, default=0.25,
                    help="prediction confidence floor")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="cpu",
                    help="cpu is fine: 11 chips, no training")
    ap.add_argument("--out", default=None, help="write JSON here")
    args = ap.parse_args()

    split_dir = Path(args.data) / args.split
    images = sorted(p for p in (split_dir / "images").iterdir()
                    if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not images:
        print(f"no images in {split_dir / 'images'}")
        return 1

    from ultralytics import YOLO
    model = YOLO(str(args.weights))

    per_image = []
    hits = misses = false_alarms = 0
    truth_polygons = pred_polygons = 0
    from PIL import Image

    for img in images:
        width, height = Image.open(img).size
        aspect = height / width  # see aspect_correct(): both axes in chip widths
        truth = load_truth(split_dir / "labels" / f"{img.stem}.txt", aspect)
        result = model.predict(str(img), imgsz=args.imgsz, device=args.device,
                               conf=args.conf, verbose=False)[0]
        preds = load_predictions(result, args.conf, aspect)
        h, m, fa = match_centroids(truth, preds, args.tolerance)

        # Rule C counts NETS, so the invariant is against the cluster count,
        # not the polygon count. Recomputed rather than returned so that a
        # disagreement between this and the matcher would actually surface.
        truth_nets = len(cluster_shapes(truth, args.tolerance))
        if h + m != truth_nets:
            print(f"! {img.name}: hits+misses={h + m} but truth nets={truth_nets}")

        hits += h
        misses += m
        false_alarms += fa
        truth_polygons += len(truth)
        pred_polygons += len(preds)
        per_image.append({"image": img.name,
                          "truth_polygons": len(truth), "truth_nets": truth_nets,
                          "prediction_polygons": len(preds),
                          "hits": h, "misses": m, "false_alarms": fa})

    total_nets = hits + misses
    rate = hits / total_nets if total_nets else float("nan")
    precision = hits / (hits + false_alarms) if (hits + false_alarms) else float("nan")

    summary = {
        "metric": "centroid detection rate (rule C: cluster into nets, match one-to-one)",
        "reference": "GhostNetZero technical report, Sept 2025; GV7 plan 10.4",
        "split": args.split,
        "weights": str(args.weights),
        "tolerance_normalised": args.tolerance,
        "conf": args.conf,
        "images": len(images),
        "ground_truth_polygons": truth_polygons,
        "ground_truth_nets": total_nets,
        "prediction_polygons": pred_polygons,
        "hits": hits,
        "misses": misses,
        "false_alarms": false_alarms,
        "centroid_detection_rate": rate,
        "centroid_precision": precision,
        "per_image": per_image,
        "denominator_note": (
            "The denominator is ground-truth NETS, not polygons: single-linkage "
            "clustering at the match tolerance collapses the bead chains of one "
            "net into one object on both sides. These figures are therefore NOT "
            "on the same footing as mAP50, which counts polygons."),
        "caveat": ("n=11 chips. Upper bound only, Tier 1 review candidate per "
                   "EXPERIMENT_GV7_PLAN.md 4.3 and 10.5. Not a detection claim."),
    }

    print(f"\n  centroid detection rate  {rate:.3f}   ({hits}/{total_nets} nets)")
    print(f"  centroid precision       {precision:.3f}   "
          f"({hits} hits, {false_alarms} false alarms)")
    print(f"  tolerance {args.tolerance} normalised, conf {args.conf}, "
          f"{len(images)} chips")
    print(f"  clustering: {truth_polygons} truth polygons -> {total_nets} nets; "
          f"{pred_polygons} predicted polygons")
    print(f"\n  {summary['caveat']}")

    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\n  written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
