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
from .shadow import shadow_context
from .decision import apply_decision_policy, calibration_mismatch, escalate_uncertainty
from .geo import SonarGeometry, geotag_pixel, pixel_to_ground_offset, position_error_m

# One model, loaded once, guarded by a lock.
# Two reasons this matters: 4 GB of VRAM cannot hold a second copy, and
# Ultralytics predict() is not documented as thread-safe -- FastAPI runs
# non-async routes in a threadpool, so concurrent uploads WILL collide here.
_MODEL = None
_MODEL_LOCK = threading.Lock()
_PREDICT_LOCK = threading.Lock()


def load_model(settings: Settings = SETTINGS):
    """Idempotent, thread-safe model load. Returns None when no weights exist."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        weights = settings.weights_path
        if weights is None or not Path(weights).exists():
            return None
        from ultralytics import YOLO

        model = YOLO(str(weights))
        model.to(settings.device)
        _MODEL = model
        return _MODEL


def warmup(settings: Settings = SETTINGS) -> bool:
    """Call from the FastAPI lifespan handler so the first request is not slow."""
    return load_model(settings) is not None


def _geometry_from_meta(meta: dict[str, Any]) -> SonarGeometry | None:
    """Build sonar geometry from survey metadata, or None if under-specified.

    Missing metadata is normal and must not raise -- it just means the
    detection is reported without a position.
    """
    required = ("nadir_col", "range_resolution_m", "altitude_m", "heading_deg")
    if not all(meta.get(k) is not None for k in required):
        return None
    return SonarGeometry(
        nadir_col=float(meta["nadir_col"]),
        range_resolution_m=float(meta["range_resolution_m"]),
        altitude_m=float(meta["altitude_m"]),
        heading_deg=float(meta["heading_deg"]),
        layback_m=float(meta.get("layback_m", 0.0)),
        along_track_res_m=meta.get("along_track_res_m"),
    )


def modality_warning(image_path: Path) -> str | None:
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
        import cv2
        import numpy as np

        img = cv2.imread(str(image_path))
        if img is None:
            return None
        white = float(np.mean(img > 250))
        if white > 0.35:
            return (f"{white:.0%} of this frame is near-pure white, which real side-scan "
                    "sonar is not; it may be a chart, screenshot or document. "
                    "Detections below are reported anyway -- treat them with suspicion.")
    except Exception:
        return None      # a diagnostic must never be the thing that fails a run
    return None


def detect(
    image_path: str | Path,
    survey_meta: dict[str, Any] | None = None,
    settings: Settings = SETTINGS,
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

    # Before the model, deliberately: whether a frame is sonar is a property of
    # the frame, so the caller should hear about it even on a run with no
    # weights loaded.
    modality = modality_warning(image_path)
    if modality:
        result.warnings.append(modality)

    # One greyscale read, reused by the shadow evidence below. Done here so a
    # frame is decoded once rather than per detection.
    gray = None
    try:
        import cv2

        gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    except Exception:
        gray = None

    model = load_model(settings)
    if model is None:
        result.warnings.append(
            "no trained weights available; returning empty detections. "
            "Set GHOSTNET_WEIGHTS or Settings.weights_path once a model is trained."
        )
        return result.to_dict()

    with _PREDICT_LOCK:
        preds = model.predict(
            source=str(image_path),
            imgsz=settings.imgsz,
            conf=settings.raw_conf_threshold,
            iou=settings.iou_threshold,
            max_det=settings.max_detections,
            device=settings.device,
            quantize=settings.quantize(),
            verbose=False,
        )

    stale = calibration_mismatch(settings)
    if stale:
        result.warnings.append(stale)

    geom = _geometry_from_meta(meta)
    have_fix = meta.get("latitude") is not None and meta.get("longitude") is not None
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

    suppressed = 0
    for item in raw:
        decision = apply_decision_policy(item["cls"], item["score"], settings)
        if decision is None:
            suppressed += 1
            continue  # below the policy floor; never shown to a reviewer
        cls_out, calibrated, uncertainty = decision

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
                    float(meta["latitude"]),
                    float(meta["longitude"]),
                    geom,
                    nadir_row=meta.get("nadir_row"),
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
                    notes=(
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
    out = []
    for p in image_paths:
        p = Path(p)
        merged = {**shared, **per_frame.get(p.stem, {})}
        out.append(detect(p, merged, settings))
    return out
