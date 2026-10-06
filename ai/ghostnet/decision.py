"""Confidence calibration and the report/suppress decision policy.

Two separable concerns live here on purpose:

  1. CALIBRATION -- mechanical. A raw YOLO score is not a probability; it is
     systematically overconfident. Temperature scaling fits a scalar T on the
     validation set and divides the logit by it -- one T PER DETECTOR CLASS
     where a class has enough matched detections to fit one, the global T
     otherwise. Nothing to decide.

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

#: Per-class calibration maps, keyed by the DETECTOR's class name (wreck,
#: plane, debris, ghost_pot, ghost_net) -- not the contract class, because four
#: of the five collapse to `debris` in the contract and are miscalibrated by
#: different amounts underneath it. Empty means "global temperature for
#: everything", which is exactly what a format-1 file gives.
#:
#: Why per class at all: one temperature has to compromise between classes
#: that are miscalibrated in different directions. The old global T = 2.72 was
#: set by val ghost_pot -- half the val boxes, correct 69% of the time at a
#: mean raw score of 0.16 -- and it dragged every class toward 0.5, capping
#: calibrated scores at 0.728. wreck, the class the detector is good at, was
#: nearly calibrated RAW (test ECE 0.021) and the shared T made it 0.174.
#: Per class, test ECE goes 0.147 -> 0.046 pooled, wreck 0.174 -> 0.042. A
#: rival team saw the same direction (0.052 global -> 0.037 per class). Full
#: before/after: ai/experiments/calib-perclass/RESULTS.md.
_CLASS_PARAMS: dict[str, dict] = {}

#: Highest calibrator file format this code understands. 1 is the original
#: {"temperature": T}; 2 adds "classes". Every format keeps the top-level
#: "temperature", so an OLDER reader handed a newer file still gets a sane
#: global correction instead of crashing.
CALIBRATOR_FORMAT = 2

#: sha256 of the weights the calibrator was fitted for, when the file records
#: it (format 2). Lets the mismatch check compare CONTENT even when the path
#: it was fitted at does not exist on this machine.
_CALIBRATION_SHA256: str | None = None


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
    global _CLASS_PARAMS, _CALIBRATION_SHA256
    if _CALIBRATION_LOADED:
        return _TEMPERATURE
    path = Path(settings.models_dir) / "calibrator" / "temperature.json"
    if path.exists():
        try:
            blob = json.loads(path.read_text())
            _TEMPERATURE, _CLASS_PARAMS = parse_calibrator(blob)
            _CALIBRATION_WEIGHTS = blob.get("weights")
            _CALIBRATION_SHA256 = blob.get("weights_sha256")
            _CALIBRATION_ERROR = None
        except Exception as exc:
            # All-or-nothing: a file whose per-class table is malformed is not
            # trusted for its global temperature either. Half-applying it
            # would leave some classes raw and others calibrated on one map,
            # with nothing saying which.
            _TEMPERATURE = 1.0
            _CLASS_PARAMS = {}
            _CALIBRATION_WEIGHTS = None
            _CALIBRATION_SHA256 = None
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

    # A recorded digest is the strongest evidence there is, and it decides the
    # question both ways: a calibrator fitted at a path that later held a
    # DIFFERENT model is caught even though the paths agree, and one fitted on
    # another machine is accepted even though its path does not exist here.
    if _CALIBRATION_SHA256 and active.exists():
        try:
            if _digest(active) == _CALIBRATION_SHA256:
                return None
        except OSError:
            return None  # cannot read the weights; inference will say so louder
        return (
            "calibration was fitted for weights with sha256 " + _CALIBRATION_SHA256[:12]
            + " but the active weights (" + active.name + ") differ; confidences may be "
            "miscalibrated. Re-run ai/scripts/fit_calibration.py against the current model."
        )

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


def class_key(model_class: str) -> str:
    """The spelling a detector class is stored under in the calibrator file."""
    return model_class.strip().lower().replace("-", "_").replace(" ", "_")


def _check_map(params: dict) -> dict:
    """Validate one class's map; raise on anything this code cannot apply."""
    method = params.get("method", "temperature")
    if method == "temperature":
        t = float(params["temperature"])
        if not (t > 0 and math.isfinite(t)):
            raise ValueError("temperature must be positive and finite")
        return {"method": "temperature", "temperature": t}
    if method == "platt":
        a, b = float(params["a"]), float(params["b"])
        # a <= 0 would invert or flatten the ranking inside the class -- a
        # higher raw score reported as LESS likely -- which no fit on real
        # data should produce and no reader should apply.
        if not (a > 0 and math.isfinite(a) and math.isfinite(b)):
            raise ValueError("platt slope must be positive and finite")
        return {"method": "platt", "a": a, "b": b}
    raise ValueError("unknown calibration method " + repr(method))


def parse_calibrator(blob: dict) -> tuple[float, dict[str, dict]]:
    """(global temperature, per-class maps) from a calibrator file, any format.

    Format 1 (no "format_version") is {"temperature": T, ...}: global only.
    Format 2 adds "classes": {name: {"method": ..., ...}}. A class marked
    "fallback" is listed for the record -- why it has no map of its own -- and
    uses the global temperature, exactly as an absent class does.
    """
    version = int(blob.get("format_version", 1))
    if version > CALIBRATOR_FORMAT:
        raise ValueError(f"calibrator format {version} is newer than this code ({CALIBRATOR_FORMAT})")
    temperature = float(blob["temperature"])
    if not (temperature > 0 and math.isfinite(temperature)):
        raise ValueError("temperature must be positive and finite")
    classes: dict[str, dict] = {}
    for name, params in (blob.get("classes") or {}).items():
        if params.get("fallback"):
            continue
        classes[class_key(name)] = _check_map(params)
    return temperature, classes


def apply_map(params: dict, raw_score: float) -> float:
    """Apply one calibration map to one raw score.

    temperature: sigmoid(logit / T). Monotonic, one parameter, T == 1 is an
                 exact no-op.
    platt:       sigmoid(a * logit + b). Temperature is the special case
                 a = 1/T, b = 0; the intercept lets a class whose scores are
                 SHIFTED, not just stretched, be corrected.
    """
    method = params.get("method", "temperature")
    if method == "temperature" and float(params["temperature"]) == 1.0:
        return raw_score
    p = min(max(raw_score, 1e-6), 1 - 1e-6)
    logit = math.log(p / (1 - p))
    if method == "platt":
        z = float(params["a"]) * logit + float(params["b"])
    else:
        z = logit / float(params["temperature"])
    # Split by sign so a steep Platt slope cannot overflow math.exp.
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def calibrator_for(blob: dict, model_class: str | None = None) -> dict:
    """The map a calibrator file applies to one class. For scripts and tests."""
    temperature, classes = parse_calibrator(blob)
    if model_class is not None and class_key(model_class) in classes:
        return classes[class_key(model_class)]
    return {"method": "temperature", "temperature": temperature}


def calibrate(
    raw_score: float,
    settings: Settings = SETTINGS,
    model_class: str | None = None,
) -> float:
    """Map a raw score into a better-behaved probability.

    Uses the class's own map when the calibrator has one for `model_class`
    (the DETECTOR's class name), and the global temperature otherwise --
    for every class of a format-1 file, for a class that fell back at fit
    time, and whenever no class is given.
    """
    t = load_calibration(settings)
    if model_class is not None:
        params = _CLASS_PARAMS.get(class_key(model_class))
        if params is not None:
            return apply_map(params, raw_score)
    return apply_map({"method": "temperature", "temperature": t}, raw_score)


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

#: Contract classes reported as REVIEW CANDIDATES rather than as claims.
#:
#: `ghost_net` is here because the model cannot detect nets. gv5 scored recall
#: 0.000 on 36 held-out net boxes and gv6, with ten times the training boxes,
#: scored 0.000 as well -- so the honest options are to surface weak candidates
#: for a human or to surface nothing. We surface them, and we say what they are.
#: See docs/EXPERIMENT_GV7_PLAN.md §10.5, Tier 1.
REVIEW_ONLY_CLASSES = frozenset({"ghost_net"})


def is_review_only(contract_class: str) -> bool:
    """Whether a contract class may only be offered for review, never claimed.

    Keyed on the CONTRACT class, so it is evaluated after `normalise_class`
    and stays correct if the training taxonomy is renamed underneath it.
    """
    return contract_class in REVIEW_ONLY_CLASSES


def is_calibrated(settings: Settings = SETTINGS) -> bool:
    """True once a temperature has actually been fitted on a validation set.

    T == 1.0 is the sentinel for 'never fitted', so raw scores are passing
    through untouched and are known to be overconfident. A per-class table
    counts on its own: the global T could land on 1.0 while the classes that
    matter carry maps of their own.
    """
    return load_calibration(settings) != 1.0 or bool(_CLASS_PARAMS)


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

    4. `ghost_net` gets a THIRD, lower floor and is flagged `review_only`. It
       is not that nets matter less -- they are the headline class -- it is
       that the model cannot detect them (recall 0.000 across gv5 and gv6), so
       an ordinary floor suppresses the class entirely and an ordinary
       rendering would overclaim it. A lenient floor is only defensible
       BECAUSE the payload says the output is a candidate; the two halves are
       one decision and must not be separated. See is_review_only.

    5. The gate that matters for nets is the RAW one, not the calibrated one.
       A calibrated floor cannot recover a box the detector never emitted, and
       with raw_conf_threshold = 0.10 the minimum calibrated confidence
       reaching this function is 0.128 (wreck, T = 1.145; 0.139 for the
       global T = 1.202) -- above review_floor_artificial (0.12), which is
       inert by design. Under the old global T = 2.72 it was 0.309 against a
       floor of 0.20; the floor was lowered with the per-class calibrator so
       the recalibration did not quietly start suppressing detections. Both
       floors are applied, but only the raw one changes what a reviewer sees.
    """
    cls = normalise_class(model_class)

    # RAW gate first. The detector is run at the lower of the two raw
    # thresholds so that weak net boxes exist at all; every other class is
    # re-gated here to the original raw_conf_threshold, so nothing outside
    # REVIEW_ONLY_CLASSES sees any change in behaviour. Do this before
    # calibration: raw is the scale the detector's own `conf` argument uses,
    # and mixing the two scales is the standing trap on this codebase.
    raw_floor = (
        settings.raw_conf_threshold_net
        if is_review_only(cls)
        else settings.raw_conf_threshold
    )
    if raw_score < raw_floor:
        return None

    # Per DETECTOR class (model_class), not per contract class: wreck, plane,
    # debris and ghost_pot all report as `debris` but are miscalibrated by
    # different amounts underneath it.
    confidence = calibrate(raw_score, settings, model_class=model_class)

    if is_review_only(cls):
        # Lower bar, because the output is a candidate and not a claim. See
        # config.review_floor_net for why this is a floor and not a tuned value.
        floor = settings.review_floor_net
    elif cls in ARTIFICIAL_CLASSES:
        floor = settings.review_floor_artificial
    else:
        floor = settings.review_floor_natural
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

    With overlapping tiles (Settings.tile_overlap, 0.25 by default) the cost
    moves. At an INTERNAL seam a real object up to the overlap width (160 px)
    is whole in the neighbouring tile, so deleting its clipped sliver here
    loses nothing -- and `ghostnet.merge` folds the remaining sightings into
    one in survey coordinates. At the survey's OUTER border (far range, the
    first and last ping) there is no neighbour and the cost is what it always
    was. The rule is deliberately NOT relaxed at internal seams: the artefact
    itself appears there too (tile x0=1280 above), and the merge cannot remove
    an artefact the neighbouring tile never produced.

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
