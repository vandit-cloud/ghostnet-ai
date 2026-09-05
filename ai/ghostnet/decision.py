"""Confidence calibration and the report/suppress decision policy.

Two separable concerns live here on purpose:

  1. CALIBRATION -- mechanical. A raw YOLO score is not a probability; it is
     systematically overconfident. Temperature scaling fits a single scalar T
     on the validation set and divides the logit by it. Nothing to decide.

  2. POLICY -- a judgement call. Given a calibrated probability, do we report
     this detection at all, and how much confidence do we claim? That depends
     on what it costs to be wrong in each direction, which is a domain
     question, not a machine-learning one.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .config import SETTINGS, Settings
from .contract import CLASS_VALUES
from .taxonomy import TRAINING_TO_CONTRACT, source_to_training, training_to_contract

# Fitted on the validation set by scripts/fit_calibration.py once a model
# exists. T == 1.0 means "uncalibrated", i.e. raw scores pass through.
_TEMPERATURE: float = 1.0
_CALIBRATION_LOADED = False


_CALIBRATION_WEIGHTS: str | None = None

#: Set when a calibrator file EXISTS but could not be read. Distinct from the
#: file being absent, which is the legitimate uncalibrated state.
_CALIBRATION_ERROR: str | None = None


def load_calibration(settings: Settings = SETTINGS) -> float:
    """Read the fitted temperature from models/calibrator/temperature.json.

    A missing file and an unreadable one are NOT the same thing, and the
    difference used to be invisible. Both fell back to T == 1.0, which
    `is_calibrated()` reads as "never fitted" -- so a truncated or half-written
    temperature.json silently downgraded every score to raw and capped every
    detection at "medium" uncertainty, with nothing anywhere saying why. The
    symptom (no 'low' uncertainty ever appears) looks exactly like a model that
    has simply not been calibrated yet.

    So a parse failure now records itself for `calibration_mismatch()` to
    surface, and deliberately does NOT latch `_CALIBRATION_LOADED`: re-reading
    a small JSON file on each call costs nothing measurable, and it means
    fixing the file recovers the process instead of requiring a restart of
    Member 2's API.
    """
    global _TEMPERATURE, _CALIBRATION_LOADED, _CALIBRATION_WEIGHTS, _CALIBRATION_ERROR
    if _CALIBRATION_LOADED:
        return _TEMPERATURE
    path = Path(settings.models_dir) / "calibrator" / "temperature.json"
    if path.exists():
        try:
            blob = json.loads(path.read_text())
            _TEMPERATURE = float(blob["temperature"])
            _CALIBRATION_WEIGHTS = blob.get("weights")
            _CALIBRATION_ERROR = None
        except Exception as exc:
            _TEMPERATURE = 1.0
            _CALIBRATION_WEIGHTS = None
            _CALIBRATION_ERROR = (
                "calibrator at " + path.name + " exists but could not be read ("
                + type(exc).__name__ + "); scores are RAW and uncertainty is capped "
                "at 'medium'. Re-run ai/scripts/fit_calibration.py."
            )
            return _TEMPERATURE  # not latched -- a repaired file is picked up
    else:
        _CALIBRATION_ERROR = None
    _CALIBRATION_LOADED = True
    return _TEMPERATURE


#: Digest cache, keyed by (path, size, mtime). Weights are tens of MB and this
#: runs inside detect(), i.e. once per frame: hashing them every call cost 34 ms
#: per frame measured, which is 34 seconds across a thousand-frame survey spent
#: re-answering a question whose inputs cannot have changed mid-run. The mtime
#: and size in the key mean a file swapped underneath a long-running process is
#: still noticed.
_DIGESTS: dict[tuple[str, int, float], str] = {}


def _digest(path: Path) -> str:
    """Hash of a weights file, read in chunks -- these run to tens of MB."""
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime)
    cached = _DIGESTS.get(key)
    if cached is not None:
        return cached
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    _DIGESTS[key] = h.hexdigest()
    return _DIGESTS[key]


def calibration_mismatch(settings: Settings = SETTINGS) -> str | None:
    """Warn when the calibrator was fitted for a DIFFERENT set of weights.

    A temperature is a property of one trained model. Retrain, and the old
    file still loads and still looks fine -- it just silently applies the wrong
    correction, which is worse than no calibration at all because the numbers
    look authoritative. Nothing else in the pipeline would notice, so the check
    lives here and the caller surfaces it as a warning.
    """
    load_calibration(settings)
    # An unreadable calibrator outranks a mismatched one: there is no fitted
    # temperature to compare against, and the caller needs to hear the louder
    # of the two facts.
    if _CALIBRATION_ERROR:
        return _CALIBRATION_ERROR
    if _CALIBRATION_WEIGHTS is None or settings.weights_path is None:
        return None
    fitted, active = Path(_CALIBRATION_WEIGHTS), Path(settings.weights_path)
    try:
        same = fitted.resolve() == active.resolve()
    except OSError:
        same = str(fitted) == str(active)

    # Paths first because it is free, then CONTENT, because a model is its
    # bytes and not its location. Promoting a run copies best.pt to
    # models/trained/ghostnet.pt, and Member 2 will deploy it somewhere else
    # again -- identical weights under three paths. Comparing paths alone
    # would fire a "confidences may be miscalibrated" warning on every single
    # payload from a correctly calibrated model, and a warning that cries wolf
    # on the happy path is one nobody reads on the day it matters.
    if not same and fitted.exists() and active.exists():
        try:
            if fitted.stat().st_size == active.stat().st_size:
                same = _digest(fitted) == _digest(active)
        except OSError:
            pass
    if same:
        return None
    return (
        "calibration was fitted for " + fitted.name + " but the active weights are "
        + active.name + "; confidences may be miscalibrated. Re-run "
        "ai/scripts/fit_calibration.py against the current model."
    )


def calibrate(raw_score: float, settings: Settings = SETTINGS) -> float:
    """Temperature-scale a raw score into a better-behaved probability.

    Invert the sigmoid to recover the logit, divide by T, re-apply the sigmoid.
    T > 1 softens overconfident scores; T == 1 is a no-op.
    """
    t = load_calibration(settings)
    if t == 1.0:
        return raw_score
    p = min(max(raw_score, 1e-6), 1 - 1e-6)
    logit = math.log(p / (1 - p))
    return 1.0 / (1.0 + math.exp(-logit / t))


# Net-like names never appear in a training set today -- no public side-scan
# data contains ghost nets -- but they will once synthetic examples exist, and
# a stray alias costs nothing meanwhile.
_NET_ALIASES = frozenset({"ghostnet", "net", "nets", "fishing_net", "fishingnet", "netting"})


def normalise_class(model_class: str) -> str:
    """Map a detector class name onto the closed contract vocabulary.

    Resolution order, most specific first:
      1. already a contract value        -> itself
      2. a net-like alias                -> ghost_net
      3. a TRAINING class (taxonomy.py)  -> its contract class
      4. a raw SOURCE name from a dataset -> training class -> contract class
      5. anything else                   -> unknown

    Step 4 matters because a model trained straight from a dataset's own labels
    can emit 'ship' rather than 'wreck'. Falling through to 'unknown' there
    would quietly demote a confident wreck detection.
    """
    name = model_class.strip().lower().replace("-", "_").replace(" ", "_")
    if name in CLASS_VALUES:
        return name
    if name in _NET_ALIASES:
        return "ghost_net"
    if name in TRAINING_TO_CONTRACT:
        return training_to_contract(name)
    training_class, reason = source_to_training(model_class)
    if training_class is not None:
        return training_to_contract(training_class)
    if reason.startswith("background"):
        # 'seafloor', 'rock' and friends are background at TRAINING time -- an
        # empty label, not a class. But the contract vocabulary still carries
        # `natural`, and a second-stage classifier or a future model may emit
        # one of these names. Reporting it as `unknown` would throw away a
        # confident, correct statement that this is natural seabed.
        return "natural"
    return "unknown"


# ---------------------------------------------------------------------------
# The reporting policy.
# ---------------------------------------------------------------------------

# Classes that describe a man-made object. These are actionable: someone may
# put a boat in the water because of them. 'unknown' is included deliberately
# -- an anomaly the model cannot name is exactly what a reviewer should see.
ARTIFICIAL_CLASSES = frozenset({"ghost_net", "debris", "unknown"})


def is_calibrated(settings: Settings = SETTINGS) -> bool:
    """True once a temperature has actually been fitted on a validation set.

    T == 1.0 is the sentinel for 'never fitted', so raw scores are passing
    through untouched and are known to be overconfident.
    """
    return load_calibration(settings) != 1.0


def assess_uncertainty(confidence: float, settings: Settings = SETTINGS) -> str:
    """Bucket a calibrated confidence into the contract's three bands.

    The cap below is the important part. Before calibration is fitted, the
    number being bucketed is a ranking score wearing a probability's clothes.
    Claiming 'low uncertainty' from it would be a confident statement derived
    from an admittedly untrustworthy input -- precisely the overconfidence the
    honesty rules (§25, B4, E16) exist to prevent. So while uncalibrated, the
    best band available is 'medium', no matter how high the score.
    """
    if confidence >= settings.uncertainty_low_edge:
        band = "low"
    elif confidence >= settings.uncertainty_medium_edge:
        band = "medium"
    else:
        band = "high"

    if band == "low" and not is_calibrated(settings):
        return "medium"
    return band


def escalate_uncertainty(current: str) -> str:
    """Widen an uncertainty band by one step.

    Used by the caller for detections landing in acoustically degraded regions
    (the water column), where the class score itself is less trustworthy --
    not merely the position.
    """
    return {"low": "medium", "medium": "high", "high": "high"}[current]


def apply_decision_policy(
    model_class: str,
    raw_score: float,
    settings: Settings = SETTINGS,
) -> tuple[str, float, str] | None:
    """Decide whether and how to report one detection.

    Args:
        model_class: raw class name from the detector.
        raw_score:   raw detector score, 0..1, uncalibrated.
        settings:    runtime settings carrying the floors and band edges.

    Returns:
        (contract_class, calibrated_confidence, uncertainty) to report it, or
        None to suppress it so it never reaches the reviewer.

    Policy, and the reasoning behind each choice:

    1. 'natural' is REPORTED, not discarded. The model asserting "that is a
       rock" is the evidence that the artificial-vs-natural separation works,
       which is both the PS's own wording and the headline metric that replaced
       the unmeasurable ghost-net F1 (gap #4). Throwing it away would delete the
       proof of the thing being claimed. Member 2 filters by `class` for the
       default map view; the data still exists behind that filter.

    2. The floors are ASYMMETRIC. A missed ghost net keeps fishing for years,
       so artificial classes clear a low bar (0.20). A low-confidence 'natural'
       is neither actionable nor evidential, so it clears a higher one (0.45).
       This buys back most of the reviewer-fatigue cost of choice 1 without
       touching the artificial recall that actually matters.

    3. Suppression happens on CALIBRATED confidence, after temperature scaling,
       so the floor keeps a fixed meaning as the model changes. A floor on raw
       scores would silently drift every time the detector is retrained.
    """
    cls = normalise_class(model_class)
    confidence = calibrate(raw_score, settings)

    floor = (
        settings.review_floor_artificial
        if cls in ARTIFICIAL_CLASSES
        else settings.review_floor_natural
    )
    if confidence < floor:
        return None

    return cls, confidence, assess_uncertainty(confidence, settings)


def is_edge_sliver(
    bbox: tuple[int, int, int, int] | list[int],
    frame_width: int,
    frame_height: int,
    settings: Settings = SETTINGS,
) -> bool:
    """Whether a box is a thin strip welded to a frame border.

    The artifact this exists for
    ---------------------------
    `survey._offsets` cuts a waterfall into 640 px tiles. The detector reacts
    to the resulting image border, and produces boxes with a very particular
    shape: flush against x=0 or x=W-1, a few dozen pixels thick, running most
    of the frame's height. On the demo survey, eight of nine detections looked
    like this:

        tile x0=1408  x 605-639 (34 px wide)  y 169-636 (467 px tall)
        tile x0=1280  x 604-638 (34 px wide)  y  80-640 (560 px tall)
        tile x0=   0  x   0- 24 (24 px wide)  y   0-640 (640 px tall)

    It is not an artefact of the across-track assembly -- that was a separate
    bug (F1 in docs/KNOWN_ISSUES.md), and fixing it moved these boxes from one
    fixed global column to each tile's own local edge without removing them.

    What this costs, said out loud
    ------------------------------
    A real object clipped by a tile seam also touches the border, and this rule
    will discard it when the visible sliver happens to be thin and long. Two
    things make that an acceptable trade rather than a silent loss of recall:

      * `_offsets` pulls the last tile back to end flush with the data, so
        interior seams are shared by two tiles. An object cut by one is usually
        whole, or more nearly whole, in its neighbour.
      * The shape is discriminating on its own. A 34 px x 467 px strip is a
        13:1 aspect ratio pinned to a border. Objects that thin and that long
        exist -- a cable running along-track is exactly that -- which is why
        this is a setting and why the caller reports the count rather than
        dropping them quietly.

    The proper fix is NMS in SURVEY coordinates, merging the two halves an
    object splits into instead of judging each half alone. That is the work
    `_offsets`'s own docstring defers, and this rule does not replace it.

    Returns False when the frame size is unknown (0 or negative), because a
    rule about proportions cannot be evaluated without them.
    """
    if not settings.suppress_edge_slivers:
        return False
    if frame_width <= 0 or frame_height <= 0:
        return False

    x, y, w, h = (int(v) for v in bbox)
    if w <= 0 or h <= 0:
        return False

    tol = settings.edge_touch_px
    max_thick = settings.edge_sliver_max_thickness
    min_extent = settings.edge_sliver_min_extent

    touches_side = x <= tol or (x + w) >= (frame_width - tol)
    if touches_side and w <= frame_width * max_thick and h >= frame_height * min_extent:
        return True

    # The same shape rotated: a strip along the top or bottom border. Not seen
    # in this data -- tiles are cut on both axes, so it is reachable -- and
    # leaving it out would make the rule depend on which axis happened to fail.
    touches_end = y <= tol or (y + h) >= (frame_height - tol)
    if touches_end and h <= frame_height * max_thick and w >= frame_width * min_extent:
        return True

    return False
