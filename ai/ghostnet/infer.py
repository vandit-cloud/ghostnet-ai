"""The single integration surface Member 2 consumes.

    from ghostnet import detect
    result = detect(image_path, survey_meta)   # -> dict matching the K28 contract

Everything else in this package is an internal detail. Member 2 never imports
ultralytics, never touches a .pt file, and never sees a confidence threshold.

Designed to degrade rather than fail:
  * no weights on disk     -> empty detections + an explicit warning
  * no GPU                 -> runs on CPU
  * no navigation metadata -> boxes without coordinates, localization "none"
In every case the returned payload still satisfies the contract, so the web app
can be built and demoed before the model exists.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from .config import SETTINGS, Settings
from .contract import Detection, Dimensions, EvidenceSummary, FrameResult
from .dropout import (
    OVERLAP_ESCALATE,
    dropout_context,
    dropout_overlap,
    frame_dropout_note,
    invalid_row_mask,
)
from .shadow import shadow_context
from .decision import (
    apply_decision_policy,
    is_review_only,
    calibration_mismatch,
    escalate_uncertainty,
    is_edge_sliver,
)
from .geo import SonarGeometry, geotag_pixel, pixel_to_ground_offset, position_error_m

# One model, loaded once, guarded by a lock.
# Two reasons this matters: 4 GB of VRAM cannot hold a second copy, and
# Ultralytics predict() is not documented as thread-safe -- FastAPI runs
# non-async routes in a threadpool, so concurrent uploads WILL collide here.
_MODEL = None
_MODEL_LOCK = threading.Lock()
_PREDICT_LOCK = threading.Lock()


#: Set when weights EXIST but will not load. Distinct from there being none,
#: which is a legitimate state Member 2 builds against.
_MODEL_ERROR: str | None = None


def load_model(settings: Settings = SETTINGS):
    """Idempotent, thread-safe model load. Returns None when no usable weights
    exist -- whether that is because there are none, or because the file on
    disk cannot be loaded.

    A truncated or wrong-format .pt used to raise out of here, which meant out
    of `warmup()` too: Member 2 calls that from the FastAPI lifespan handler,
    so a bad weights file took down the whole API at startup rather than
    degrading to the empty-detections path this package is built around.
    """
    global _MODEL, _MODEL_ERROR
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        weights = settings.weights_path
        if weights is None or not Path(weights).exists():
            return None
        try:
            from ultralytics import YOLO

            model = YOLO(str(weights))
            model.to(settings.device)
        except Exception as exc:
            # Not latched: the path is re-read next call, so replacing a bad
            # file recovers a running process instead of needing a restart.
            _MODEL_ERROR = (
                "weights at " + Path(weights).name + " exist but could not be loaded ("
                + type(exc).__name__ + "); returning empty detections. The file may be "
                "truncated, or may not be a YOLO checkpoint."
            )
            return None
        _MODEL_ERROR = None
        _MODEL = model
        return _MODEL


def warmup(settings: Settings = SETTINGS) -> bool:
    """Call from the FastAPI lifespan handler so the first request is not slow."""
    return load_model(settings) is not None


#: Metadata keys this package reads as numbers. Anything here that is present
#: but not numeric is a malformed frame, not a missing one.
NUMERIC_META_KEYS: tuple[str, ...] = (
    "nadir_col",
    "range_resolution_m",
    "altitude_m",
    "heading_deg",
    "layback_m",
    "along_track_res_m",
    "latitude",
    "longitude",
    "nadir_row",
)


def _num(meta: dict[str, Any], key: str, default: float | None = None) -> float | None:
    """Read one metadata value as a float, or the default if it is not one.

    `float()` on unvalidated input is where this package used to break its
    central promise. The old guard tested `is not None`, which a hand-filled
    sidecar, an unfilled form field, a CSV column or a nullable text column all
    pass with a value like "" or "n/a" -- and then `float("")` raised
    ValueError straight out of detect(), where HANDOFF tells Member 2 in as
    many words that no try/except is needed.

    A value that cannot be read is treated exactly like a value that is not
    there: no geometry, no position, a warning, and the detection still
    reported. That equivalence is the point -- there is nothing useful a caller
    could do with the distinction at THIS level, and `malformed_meta_keys`
    below preserves it for the warning that explains why.
    """
    raw = meta.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def malformed_meta_keys(meta: dict[str, Any]) -> list[str]:
    """Keys that carry a value which is not a number.

    Kept separate from `_num` so the caller can say WHICH field is unusable.
    "incomplete sonar geometry" sends someone hunting for a missing field; a
    frame whose heading arrived as the string "north" needs a different fix,
    and the difference is invisible from the payload otherwise.
    """
    bad = []
    for key in NUMERIC_META_KEYS:
        raw = meta.get(key)
        if raw is None:
            continue
        try:
            float(raw)
        except (TypeError, ValueError):
            bad.append(key)
    return bad


def _geometry_from_meta(meta: dict[str, Any]) -> SonarGeometry | None:
    """Build sonar geometry from survey metadata, or None if under-specified.

    Missing metadata is normal and must not raise -- it just means the
    detection is reported without a position. Neither must UNREADABLE
    metadata; see `_num`.
    """
    required = ("nadir_col", "range_resolution_m", "altitude_m", "heading_deg")
    values = {k: _num(meta, k) for k in required}
    if any(v is None for v in values.values()):
        return None
    return SonarGeometry(
        nadir_col=values["nadir_col"],
        range_resolution_m=values["range_resolution_m"],
        altitude_m=values["altitude_m"],
        heading_deg=values["heading_deg"],
        layback_m=_num(meta, "layback_m", 0.0) or 0.0,
        along_track_res_m=_num(meta, "along_track_res_m"),
    )


def modality_warning(gray) -> str | None:
    """Warn when a frame does not look like side-scan sonar at all.

    A WARNING, never a refusal. The signal is one cheap statistic -- the
    fraction of near-pure-white pixels -- and it was chosen by measurement, not
    by intuition: on 400 real tiles across all eight sources it fires zero
    times, and it catches a text screenshot the detector otherwise reported two
    objects in, above the review floor.

    A colour-variance test was proposed alongside it and REJECTED. Sonar is a
    single-band acoustic return, so "R should equal G should equal B" sounds
    exactly right -- but amber and copper are standard side-scan display
    palettes, and the check rejected 5 of 5 SCTD tiles, the source of every
    wreck and plane box in the project. It would have silently refused to
    process the data the model was trained on.

    What this does NOT catch, and the reason it warns rather than blocks: a
    synthetic nautical chart, greyscale and unsaturated, sails through and the
    detector reports three objects at 0.46 calibrated. Non-sonar rejection is
    not solved by one statistic. Blocking on a test this partial would trade
    two visible false alarms for an invisible refusal, which is the worse
    failure -- so the frame is still processed and the caller is told.
    """
    try:
        import numpy as np

        # Takes the frame ALREADY DECODED by detect(). It used to imread the
        # file a second time, which is 6.7 ms of decoding a diagnostic could
        # simply be handed.
        if gray is None:
            return None
        white = float(np.mean(gray > 250))
        if white > 0.35:
            return (f"{white:.0%} of this frame is near-pure white, which real side-scan "
                    "sonar is not; it may be a chart, screenshot or document. "
                    "Detections below are reported anyway -- treat them with suspicion.")
    except Exception:
        return None      # a diagnostic must never be the thing that fails a run
    return None


def _predict_many(model, paths: list[str], settings: Settings) -> list:
    """One model call for many frames.

    Batching is not a micro-optimisation here, it is the difference between a
    usable service and an unusable one. Measured on the RTX 3050 this project
    targets:

        batch 1     275 ms/frame     3.6 frames/s
        batch 8      15.6 ms/frame    64 frames/s
        batch 16     15.1 ms/frame    66 frames/s

    18x, and the cause is not arithmetic. A single 640px frame is too little
    work to pull the GPU out of its idle power state: it stays at 255 MHz of a
    2100 MHz boost clock, drawing 4.8 W. Feed it eight and it clocks to
    1987 MHz at 40 W. One frame at a time, this laptop GPU is SLOWER than its
    own CPU (144 ms/frame), which is the kind of result that gets blamed on
    the model.
    """
    with _PREDICT_LOCK:
        return list(model.predict(
            source=paths,
            imgsz=settings.imgsz,
            # Lower of the two, so weak `ghost_net` boxes exist for the policy
            # to consider. Every other class is re-gated back to
            # raw_conf_threshold in apply_decision_policy, so this widens what
            # is CONSIDERED without widening what is REPORTED.
            conf=min(settings.raw_conf_threshold, settings.raw_conf_threshold_net),
            iou=settings.iou_threshold,
            max_det=settings.max_detections,
            device=settings.device,
            quantize=settings.quantize(),
            verbose=False,
        ))


def detect(
    image_path: str | Path,
    survey_meta: dict[str, Any] | None = None,
    settings: Settings = SETTINGS,
    _prediction: Any = None,
) -> dict[str, Any]:
    """Run detection on one sonar frame.

    Args:
        image_path: path to a single preprocessed side-scan frame.
        survey_meta: optional acquisition metadata. Recognised keys --
            survey_id, frame_id, latitude, longitude, heading_deg,
            altitude_m, nadir_col, range_resolution_m, along_track_res_m,
            layback_m, nadir_row.
        settings: override for tests or alternate deployments.

    Returns:
        A dict matching the K28 contract. Never raises for a missing model,
        missing metadata or a missing GPU.
    """
    meta = dict(survey_meta or {})
    image_path = Path(image_path)

    result = FrameResult(
        survey_id=str(meta.get("survey_id", "UNKNOWN-SURVEY")),
        frame_id=str(meta.get("frame_id", image_path.stem)),
        provenance=settings.provenance(),
    )

    if not image_path.exists():
        result.warnings.append("image not found: " + image_path.name)
        return result.to_dict()

    # ONE greyscale decode per frame, and everything frame-shaped derived from
    # it once. All three of these are properties of the frame rather than of a
    # box, and computing them per detection is how 35 ms of inference became
    # 251 ms: modality_warning used to imread the file a second time, and the
    # dropout row mask was rebuilt twice for every detection in the frame.
    gray = None
    try:
        import cv2

        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    except Exception:
        gray = None

    row_mask = None
    if gray is not None:
        # Before the model, deliberately: whether a frame is sonar does not
        # depend on whether weights happen to be loaded.
        modality = modality_warning(gray)
        if modality:
            result.warnings.append(modality)

        row_mask = invalid_row_mask(gray)
        note = frame_dropout_note(gray)
        if note:
            result.warnings.append(note)

    model = load_model(settings)
    if model is None:
        # Two different facts, and the wrong one sends someone to the wrong
        # place: "set GHOSTNET_WEIGHTS" is useless advice when the variable is
        # already set and the file it points at is broken.
        result.warnings.append(
            _MODEL_ERROR
            or (
                "no trained weights available; returning empty detections. "
                "Set GHOSTNET_WEIGHTS or Settings.weights_path once a model is trained."
            )
        )
        return result.to_dict()

    # `_prediction` lets detect_batch hand in a result the model already
    # produced for a whole batch, so the per-frame path and the batched path
    # stay ONE code path. Duplicating the post-processing for speed is how the
    # two quietly diverge and only one of them gets the next bug fix.
    if _prediction is not None:
        preds = [_prediction]
    else:
        try:
            preds = _predict_many(model, [str(image_path)], settings)
        except Exception as exc:
            # A file that exists but will not decode. This became reachable the
            # day a promoted model started loading by default: before that, the
            # no-weights early return happened to catch it, so the crash was
            # hidden behind a missing model rather than handled.
            #
            # An upload service is exactly where truncated and mislabelled
            # files arrive, and the contract promise is that a frame always
            # comes back as a valid payload explaining itself -- never as an
            # exception the caller has to catch.
            result.warnings.append(
                f"could not read this frame as an image ({type(exc).__name__}); "
                "it may be truncated, or not an image at all. No detections reported."
            )
            return result.to_dict()

    stale = calibration_mismatch(settings)
    if stale:
        result.warnings.append(stale)

    geom = _geometry_from_meta(meta)
    fix_lat, fix_lon = _num(meta, "latitude"), _num(meta, "longitude")
    have_fix = fix_lat is not None and fix_lon is not None

    # Named before the generic geometry warning, because it is the actionable
    # one: a malformed field is a bug in whatever produced the metadata, while
    # a missing one is often just how the survey was recorded.
    malformed = malformed_meta_keys(meta)
    if malformed:
        result.warnings.append(
            "metadata field(s) " + ", ".join(malformed) + " are not numeric and were "
            "ignored; affected positions are withheld rather than guessed"
        )

    if geom is None:
        result.warnings.append("incomplete sonar geometry; detections reported without coordinates")
    elif not have_fix:
        result.warnings.append("no navigation fix for this frame; detections reported without coordinates")

    names = getattr(model, "names", {}) or {}
    raw: list[dict[str, Any]] = []
    for pred in preds:
        boxes = getattr(pred, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
            raw.append(
                {
                    "cls": str(names.get(int(box.cls[0]), "unknown")),
                    "score": float(box.conf[0]),
                    "bbox": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
                    "centre": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
                }
            )

    # Tile-edge artifacts, removed before the confidence policy runs.
    #
    # Reported in `warnings` rather than dropped quietly: this rule can also
    # discard a real object that a tile seam clipped into a thin strip, and a
    # reviewer who sees "3 detections" needs to be able to find out that two
    # more were judged to be border artifacts. See decision.is_edge_sliver.
    if gray is not None:
        frame_h, frame_w = gray.shape[:2]
        kept = [d for d in raw if not is_edge_sliver(d["bbox"], frame_w, frame_h, settings)]
        removed = len(raw) - len(kept)
        if removed:
            result.warnings.append(
                f"{removed} detection(s) suppressed as tile-edge artifacts: thin strips "
                f"flush against a frame border. Set suppress_edge_slivers=False to see them."
            )
        raw = kept

    suppressed = 0
    for item in raw:
        decision = apply_decision_policy(item["cls"], item["score"], settings)
        if decision is None:
            suppressed += 1
            continue  # below the policy floor; never shown to a reviewer
        cls_out, calibrated, uncertainty = decision

        # A detection standing on dead pings is suspect for the same reason a
        # detection in the water column is: the pixels underneath it are not
        # seabed return. That case already widens the band a few lines below,
        # and this is the same judgement applied to the same kind of evidence.
        drop_note = "not_evaluated: frame could not be read"
        if gray is not None:
            drop_note = dropout_context(gray, item["bbox"], row_mask)
            if dropout_overlap(gray, item["bbox"], row_mask) >= OVERLAP_ESCALATE:
                uncertainty = escalate_uncertainty(uncertainty)

        lat = lon = err = None
        localization = "none"
        dims = Dimensions()

        if geom is not None:
            col, row = item["centre"]
            ground_m, _side = pixel_to_ground_offset(col, geom)
            if ground_m is None:
                # The water column is acoustically meaningless: no seabed
                # return, so the CLASS score is suspect too, not just the
                # position. Widen the band rather than reporting a confident
                # call made on noise.
                uncertainty = escalate_uncertainty(uncertainty)
                result.warnings.append(
                    "detection at column %.0f lies in the water column; position withheld" % col
                )
            elif have_fix:
                placed = geotag_pixel(
                    col,
                    row,
                    fix_lat,
                    fix_lon,
                    geom,
                    nadir_row=_num(meta, "nadir_row"),
                )
                if placed is not None:
                    lat, lon = placed
                    err = round(position_error_m(geom, ground_range_m=ground_m), 2)
                    localization = "frame-level"

            # Across-track width is in true ground metres only after the slant
            # correction; along-track length needs the row scale.
            w_px = item["bbox"][2]
            near, _ = pixel_to_ground_offset(col - w_px / 2, geom)
            far, _ = pixel_to_ground_offset(col + w_px / 2, geom)
            if near is not None and far is not None:
                dims = Dimensions(
                    width=round(abs(far - near), 2),
                    length=(
                        round(item["bbox"][3] * geom.along_track_res_m, 2)
                        if geom.along_track_res_m
                        else None
                    ),
                    status="estimated",
                )

        result.detections.append(
            Detection(
                detection_id="D-" + uuid.uuid4().hex[:8].upper(),
                cls=cls_out,
                raw_score=round(item["score"], 4),
                calibrated_confidence=round(calibrated, 4),
                uncertainty=uncertainty,
                bbox=item["bbox"],
                # A candidate, not a claim -- see decision.is_review_only.
                review_only=is_review_only(cls_out),
                latitude=lat,
                longitude=lon,
                position_error_m=err,
                localization=localization,
                dimensions=dims,
                model_version=settings.model_version,
                evidence_summary=EvidenceSummary(
                    artificial_verification="positive" if cls_out != "natural" else "negative",
                    shadow_context=(
                        shadow_context(gray, item["bbox"], geom, cls_out)
                        if gray is not None
                        else "not_evaluated: frame could not be read for shadow analysis"
                    ),
                    # The contract vocabulary is four values wide, so a wreck and
                    # an aircraft both report as 'debris'. The finer class the
                    # detector actually produced is preserved here rather than
                    # lost -- free text, so no schema change, and the reviewer
                    # sees what the model really said.
                    notes=(drop_note + " | " if not drop_note.startswith("clear") else "") + (
                        "detector class: " + item["cls"]
                        if item["cls"].strip().lower() != cls_out
                        else ""
                    ),
                ),
            )
        )

    # Suppression must stay visible. A policy floor that silently deletes
    # detections is indistinguishable from a model that never found them,
    # which is how a recall problem hides in plain sight.
    if suppressed:
        result.warnings.append(
            "%d detection(s) below the review floor were suppressed" % suppressed
        )

    return result.to_dict()


def detect_batch(
    image_paths: list[str | Path],
    survey_meta: dict[str, Any] | None = None,
    settings: Settings = SETTINGS,
) -> list[dict[str, Any]]:
    """Convenience wrapper. Per-frame metadata can be passed via
    survey_meta["frames"][<stem>], which overlays the shared keys."""
    shared = dict(survey_meta or {})
    per_frame = shared.pop("frames", {}) or {}
    paths = [Path(p) for p in image_paths]

    model = load_model(settings)
    if model is None:                      # degrade exactly as detect() does
        return [detect(p, {**shared, **per_frame.get(p.stem, {})}, settings) for p in paths]

    out: list[dict[str, Any]] = []
    for i in range(0, len(paths), settings.batch_size):
        chunk = paths[i : i + settings.batch_size]
        try:
            preds = _predict_many(model, [str(p) for p in chunk], settings)
        except Exception:
            # ONE unreadable frame must not lose the whole batch, so fall back
            # to per-frame for this chunk and let each one degrade on its own.
            for path in chunk:
                out.append(detect(path, {**shared, **per_frame.get(path.stem, {})}, settings))
            continue
        for path, pred in zip(chunk, preds):
            merged = {**shared, **per_frame.get(path.stem, {})}
            out.append(detect(path, merged, settings, _prediction=pred))
    return out
