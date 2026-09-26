"""Frozen AI input/output/error contract shared with Member 1 (spec sections 7-9)."""

from pydantic import BaseModel, ConfigDict, Field

#: The contract MAJOR version this backend is written against.
#:
#: Semver, per the agreement with Member 1:
#:   PATCH  docs only.
#:   MINOR  a new OPTIONAL field. This consumer keeps working untouched -- 1.1.0
#:          added `frame_position`, and nothing here had to change for it.
#:   MAJOR  a renamed or removed field, or a new `class` / `uncertainty` value.
#:          Member 1 announces it before pushing.
#:
#: Pin the MAJOR only. Bumping MINOR here on every AI release would defeat the
#: point: the whole reason MINOR is safe is that it needs no coordinated change.
EXPECTED_CONTRACT_MAJOR = 1


class ContractMajorMismatch(RuntimeError):
    """The installed `ghostnet` speaks a different MAJOR contract version.

    Raised at adapter construction, and deliberately NOT caught by
    `ghostnet_adapter.try_build()`. Every other initialisation failure there
    degrades to the mock, which is correct for a developer with no AI
    environment -- but degrading on a SCHEMA disagreement would serve
    `mock-ghostnet-dev-v0` detections to an operator who believes they are
    looking at real sonar analysis. Refusing to start is the cheaper failure.
    """

    def __init__(self, found: str, expected: int) -> None:
        super().__init__(
            f"ghostnet speaks contract {found}, this backend is written against "
            f"MAJOR {expected}. A field was renamed or removed, or a new class / "
            f"uncertainty value was added. Do not run: reconcile "
            f"backend/app/schemas/ai_contract.py against contracts/*.schema.json "
            f"in Member 1's repo, then raise EXPECTED_CONTRACT_MAJOR."
        )


def contract_major(version: str | None) -> int | None:
    """MAJOR out of a semver string, or None if it is missing or unparseable.

    None means "cannot tell", which is not the same as a mismatch: an older AI
    build that predates `contract_version` returns nothing here, and that is a
    warning, not a refusal to start.
    """
    if not version:
        return None
    head = version.split(".", 1)[0].strip()
    return int(head) if head.isdigit() else None


class AIFrameMetadata(BaseModel):
    timestamp: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    depth: float | None = None
    range: float | None = None

    # --- sonar geometry: what a coordinate actually needs ------------------
    #
    # A detection is placed on the map only when ALL FOUR of nadir_col,
    # range_resolution_m, altitude_m and heading are present, plus a lat/lon
    # fix. Any one missing means the AI reports the detection WITHOUT a
    # position rather than inventing one, and says which field is missing in
    # `warnings`.
    #
    # These are not the same quantities as `depth` and `range` above, and the
    # difference is not cosmetic:
    #   altitude_m          towfish height ABOVE THE SEABED (depth is water depth)
    #   range_resolution_m  metres per PIXEL (range is the whole swath width)
    # Substituting one for the other produces a map that looks correct and is
    # wrong by a variable amount, worst near nadir where it is most trusted.
    #
    # For a survey uploaded as .xtf these are all in the ping headers, and
    # ghostnet.xtf.geometry_for() derives them -- nobody types them in.
    nadir_col: float | None = None
    range_resolution_m: float | None = None
    altitude_m: float | None = None
    along_track_res_m: float | None = None
    layback_m: float | None = None
    nadir_row: float | None = None


class AIInferRequest(BaseModel):
    survey_id: str
    frame_id: str
    image_reference: str
    metadata: AIFrameMetadata


class AIDimensions(BaseModel):
    width: float | None = None
    length: float | None = None
    status: str | None = None


class AIDetection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    detection_id: str
    class_: str = Field(alias="class")
    raw_score: float | None = None
    calibrated_confidence: float | None = None
    uncertainty: str | None = None
    bbox: list[float] | None = None
    #: Outline polygon [[x, y], ...], same pixel frame as bbox. Was typed `str`
    #: while the AI only ever sent null; contract 1.3.0 fills it for nets.
    mask: list[list[float]] | None = None
    #: A review candidate, not a claim (contract 1.2.0). Absent means False.
    review_only: bool = False
    latitude: float | None = None
    longitude: float | None = None
    position_error_m: float | None = None
    localization: str | None = None
    dimensions: AIDimensions | None = None
    review_status: str | None = None
    model_version: str | None = None
    evidence_summary: dict = {}


class AIInferResponse(BaseModel):
    survey_id: str
    frame_id: str
    detections: list[AIDetection]

    # --- the rest of Member 1's envelope ----------------------------------
    #
    # `warnings` is the AI's explanation channel and the reason anything odd on
    # screen makes sense: why a detection has no coordinates, how many were
    # suppressed below the review floor, whether the frame even looks like
    # sonar, whether a model was loaded at all. Dropping it makes a careful
    # system look broken. Surface these in the UI.
    #
    # `contract_version` is semver and rides in every payload. Pin the MAJOR
    # and fail loudly on a mismatch: a silent schema disagreement found during
    # integration week is the most expensive thing that can happen here.
    #
    # `provenance` names the model, dataset and calibration that produced the
    # result (e.g. model_version "gv5-yolo11s"). Store it with the detection or
    # a stored result cannot be traced back to the run that made it.
    warnings: list[str] = []
    contract_version: str | None = None
    provenance: dict = {}


class AIErrorResponse(BaseModel):
    status: str
    frame_id: str
    error_code: str
    message: str
