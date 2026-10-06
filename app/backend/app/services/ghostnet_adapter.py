"""Real AI adapter: Member 1's `ghostnet` package behind the existing seam.

Drops in beside `MockAIAdapter` and implements the same `AIServiceAdapter`
protocol, so nothing else in the backend changes. `get_ai_adapter()` picks this
one when the package and a trained model are both present, and falls back to
the mock when they are not.

Install, editable, FROM THE REPOSITORY ROOT:

    pip install -e ./ai --no-deps

Relative on purpose. The AI half lives in this same repository at ai/ (the two
were separate repos until 2026-09-04), so an absolute path resolves only on the
machine it was written on and breaks the moment a second PC clones this.

`--no-deps` because torch, ultralytics, opencv and pyproj are expected to be
present already -- see app/README.md for why the backend venv is created with
--system-site-packages rather than pulling a second 2.6 GB copy of torch. On a
machine with no GPU the package runs on CPU by design: slower, still correct.

Two things this adapter deliberately does NOT do
------------------------------------------------
**It does not translate `depth` into altitude.** `AIFrameMetadata.depth` is how
deep the water is; the geometry needs the towfish's height ABOVE the seabed.
They are different quantities, and substituting one for the other does not
degrade the position, it corrupts it -- the slant-range correction is computed
from altitude, so a wrong altitude moves every box by a variable amount, worst
near nadir where an operator trusts it most. A missing altitude yields no
coordinates, which is honest. A wrong one yields a plausible map that is lying.

**It does not translate `range` into range resolution.** `range` is the swath
width in metres; the geometry needs metres per pixel. They differ by roughly
the image width.

So both are read from the OPTIONAL geometry fields on the metadata model, and
when they are absent the detection is reported without a position and the
reason is in `warnings`. Filling those four fields is what turns the map on --
and if the survey was uploaded as .xtf, `ghostnet.xtf` can derive all four from
the ping headers, so nobody has to enter them by hand.
"""

import logging
from typing import Any

from app.schemas.ai_contract import (
    EXPECTED_CONTRACT_MAJOR,
    AIDetection,
    AIDimensions,
    AIFrameMetadata,
    AIInferResponse,
    ContractMajorMismatch,
    contract_major,
)

logger = logging.getLogger("ghostnet.ai")

#: The four fields a position needs, beyond a lat/lon fix. All or nothing:
#: ghostnet returns no geometry unless every one is present.
GEOMETRY_FIELDS = ("nadir_col", "range_resolution_m", "altitude_m", "heading_deg")


def _survey_meta(survey_id: str, frame_id: str, metadata: AIFrameMetadata) -> dict[str, Any]:
    """Translate the backend's frame metadata into the shape `detect()` reads.

    Optional geometry fields are passed through when present. `heading` is the
    one straight rename -- everything else either matches already or has no
    honest equivalent (see the module docstring).
    """
    meta: dict[str, Any] = {"survey_id": survey_id, "frame_id": frame_id}

    if metadata is None:
        return meta

    if metadata.latitude is not None:
        meta["latitude"] = metadata.latitude
    if metadata.longitude is not None:
        meta["longitude"] = metadata.longitude
    if metadata.heading is not None:
        meta["heading_deg"] = metadata.heading

    # Optional geometry, present once the metadata model carries it. getattr
    # rather than attribute access so this adapter keeps working whether or not
    # those fields have been added yet.
    for field in ("nadir_col", "range_resolution_m", "altitude_m",
                  "along_track_res_m", "layback_m", "nadir_row"):
        value = getattr(metadata, field, None)
        if value is not None:
            meta[field] = value

    return meta


#: The AI contract and the backend name one class differently. The contract
#: (contracts/ai-output.schema.json) says `natural`; the database, the
#: validator (detection_service.VALID_CLASSES), the filters and the map icons
#: have always said `natural_object`. Translated here, at the one seam between
#: the two vocabularies -- renaming either side would touch stored rows or a
#: frozen contract. Before this mapping every `natural` detection was rejected
#: at ingest as an unrecognised class.
_CLASS_FROM_AI = {"natural": "natural_object"}


def _to_detection(raw: dict[str, Any]) -> AIDetection:
    dims = raw.get("dimensions") or {}
    return AIDetection(
        detection_id=raw["detection_id"],
        **{"class": _CLASS_FROM_AI.get(raw["class"], raw["class"])},
        raw_score=raw.get("raw_score"),
        calibrated_confidence=raw.get("calibrated_confidence"),
        uncertainty=raw.get("uncertainty"),
        bbox=raw.get("bbox"),
        mask=raw.get("mask"),
        review_only=bool(raw.get("review_only", False)),
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        position_error_m=raw.get("position_error_m"),
        localization=raw.get("localization"),
        dimensions=AIDimensions(
            width=dims.get("width"),
            length=dims.get("length"),
            status=dims.get("status"),
        ),
        review_status=raw.get("review_status", "pending"),
        model_version=raw.get("model_version"),
        evidence_summary=raw.get("evidence_summary") or {},
    )


class GhostNetAdapter:
    """Runs the real detector in-process.

    `ghostnet.detect()` is contracted never to raise for a missing model,
    missing metadata, an unreadable frame or a missing GPU -- it returns a valid
    payload with `warnings` instead. The try/except here is therefore a belt
    for the unforeseen, not the expected path, and it degrades to an empty
    frame rather than a 500.
    """

    def __init__(self) -> None:
        import ghostnet
        from ghostnet import warmup

        # Checked BEFORE warmup: a schema disagreement should not spend twenty
        # seconds loading weights it is about to refuse to use.
        self.contract_version = getattr(ghostnet, "CONTRACT_VERSION", None)
        found = contract_major(self.contract_version)
        if found is None:
            logger.warning(
                "ghostnet reports no contract_version; cannot verify the schema. "
                "Expected MAJOR %s. Treating as compatible, but upgrade the AI "
                "package -- this check is the cheap guard against a silent "
                "schema disagreement.",
                EXPECTED_CONTRACT_MAJOR,
            )
        elif found != EXPECTED_CONTRACT_MAJOR:
            raise ContractMajorMismatch(self.contract_version, EXPECTED_CONTRACT_MAJOR)
        else:
            logger.info("ghostnet contract %s (MAJOR %s, as expected)",
                        self.contract_version, found)

        self.loaded = warmup()
        if not self.loaded:
            logger.warning(
                "ghostnet imported but no trained weights were found; frames will "
                "come back empty with a warning. Set GHOSTNET_WEIGHTS or copy the "
                "promoted model to ai/models/trained/ghostnet.pt (with its .json "
                "sidecar, or provenance reports v0-stub)."
            )

    def analyze_frame(
        self,
        survey_id: str,
        frame_id: str,
        image_path: str,
        metadata: AIFrameMetadata,
    ) -> AIInferResponse:
        from ghostnet import detect

        meta = _survey_meta(survey_id, frame_id, metadata)
        missing = [f for f in GEOMETRY_FIELDS if meta.get(f) is None]

        try:
            payload = detect(image_path, meta)
        except Exception:                                   # pragma: no cover
            logger.exception("ghostnet.detect raised on frame %s", frame_id)
            return AIInferResponse(
                survey_id=survey_id,
                frame_id=frame_id,
                detections=[],
                warnings=["the detector failed on this frame; see server logs"],
            )

        warnings = list(payload.get("warnings") or [])
        if missing:
            # Named, because "no coordinates" with no reason attached reads as
            # a broken map rather than as absent input.
            warnings.append(
                "no position: survey metadata is missing "
                + ", ".join(missing)
                + ". Upload the survey as .xtf to derive these from the ping headers."
            )

        return AIInferResponse(
            survey_id=payload.get("survey_id", survey_id),
            frame_id=payload.get("frame_id", frame_id),
            detections=[_to_detection(d) for d in payload.get("detections", [])],
            warnings=warnings,
            contract_version=payload.get("contract_version"),
            provenance=payload.get("provenance") or {},
        )


def try_build() -> "GhostNetAdapter | None":
    """Return a real adapter, or None when the package is not installed.

    Chosen over raising so a developer with no AI environment still gets a
    working backend on the mock -- which is the whole point of the seam.
    """
    try:
        return GhostNetAdapter()
    except ImportError:
        logger.info("ghostnet is not installed; using MockAIAdapter")
        return None
    except ContractMajorMismatch:
        # Deliberately NOT degraded to the mock. Every other failure here means
        # "no AI available", which the mock honestly stands in for. This one
        # means "the AI is available and we disagree about what its output
        # means" -- and serving mock detections to an operator who believes
        # they are real sonar analysis is worse than not starting.
        logger.critical("ghostnet contract mismatch; refusing to start")
        raise
    except Exception:
        logger.exception("ghostnet failed to initialise; using MockAIAdapter")
        return None
