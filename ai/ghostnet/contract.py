"""The AI -> web-app output contract (plan K25 / K28, Member-1 plan §54).

Intentionally dependency-free: plain dataclasses, no pydantic, no FastAPI.
Member 2 receives dicts and validates them on their side with whatever pydantic
version their app pins. This keeps the two halves of the project from ever
fighting over a shared dependency.

Anything added here is a contract change -- bump CONTRACT_VERSION and tell
Member 2, because their DB schema and UI read these keys by name.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

#: 1.1.0 adds the optional `frame_position` block below. Additive and optional,
#: so by the versioning rules in docs/HANDOFF.md section 7 this is a MINOR bump:
#: a consumer pinned to major 1 keeps working untouched and simply ignores it.
#:
#: 1.3.0: `Detection.mask` can now be NON-NULL. The key and its type are
#: unchanged since 1.0, but no producer ever filled it, so a consumer may have
#: typed it wrongly without anything failing -- the backend had it as a
#: string. The bump is the signal to check. Filled only by the optional net
#: segmentation model (ghostnet.netseg).
CONTRACT_VERSION = "1.3.0"

# Closed vocabularies. Member 2's DB uses these as enum values, so adding a
# member is a breaking change for them -- never silently emit something else.
DetectionClass = Literal["ghost_net", "debris", "natural", "unknown"]
Uncertainty = Literal["low", "medium", "high"]
Localization = Literal["frame-level", "ping-level", "none"]
ReviewStatus = Literal["pending", "confirmed", "rejected"]
DimensionStatus = Literal["estimated", "measured", "unavailable"]

CLASS_VALUES: tuple[str, ...] = ("ghost_net", "debris", "natural", "unknown")
UNCERTAINTY_VALUES: tuple[str, ...] = ("low", "medium", "high")


@dataclass
class Dimensions:
    """Physical size. `status` must never be 'measured' unless real range
    resolution and altitude were available -- see the honesty rules in §25/B4."""

    width: float | None = None
    length: float | None = None
    status: DimensionStatus = "unavailable"


@dataclass
class EvidenceSummary:
    """Human-readable justification shown in the review UI (K14)."""

    artificial_verification: str = "not_run"
    shadow_context: str = "not_evaluated"
    notes: str = ""


@dataclass
class Detection:
    detection_id: str
    cls: DetectionClass
    raw_score: float
    calibrated_confidence: float
    uncertainty: Uncertainty
    bbox: list[int]  # [x, y, w, h] in pixels, top-left origin
    #: Outline polygon, [[x, y], ...] in the same pixel frame as bbox. None
    #: from the box detector; filled for nets when the segmentation model runs.
    mask: list[list[int]] | None = None

    # Geospatial. None when metadata was missing -- never fabricate a position.
    latitude: float | None = None
    longitude: float | None = None
    position_error_m: float | None = None
    localization: Localization = "none"

    #: True when this detection is a REVIEW CANDIDATE, not a claim. The model
    #: is not able to assert this class at a useful rate, so the payload says
    #: so explicitly rather than letting a confidence number imply otherwise.
    #:
    #: Member 2: render these distinctly from ordinary detections -- they must
    #: not appear in a "detections found" count, and must not be styled like a
    #: confirmed `ghost_pot`. Treat it as "worth a human look", nothing more.
    #: Added in contract 1.2.0; absent means False for older payloads.
    review_only: bool = False

    dimensions: Dimensions = field(default_factory=Dimensions)
    review_status: ReviewStatus = "pending"
    model_version: str = "unknown"
    evidence_summary: EvidenceSummary = field(default_factory=EvidenceSummary)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # `class` is a Python keyword, so the field is `cls` internally and
        # renamed on the way out to match the agreed JSON key.
        d["class"] = d.pop("cls")
        return d


@dataclass
class FramePosition:
    """Where the towfish was when this frame was recorded. New in 1.1.0.

    Distinct from a DETECTION's position, and needed for different reasons. A
    detection's coordinates say where an object is; this says where the sensor
    was, which is what draws the survey track -- and a track is what turns a
    scatter of pins into a line someone can follow back to the water.

    It also carries the frame's own timestamp, so a consumer can order frames
    in acquisition order rather than by whenever the rows happened to be
    written.

    Every field is optional, because a frame assembled from pings that carry no
    navigation has no position, and inventing one here would be the same
    dishonesty the detection path already refuses.
    """

    latitude: float | None = None
    longitude: float | None = None
    heading_deg: float | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "heading_deg": self.heading_deg,
            "timestamp": self.timestamp,
        }


@dataclass
class FrameResult:
    survey_id: str
    frame_id: str
    detections: list[Detection] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    contract_version: str = CONTRACT_VERSION
    #: None when the frame's own position is unknown -- which is the normal
    #: case for a bare image with no metadata, and never the case for a frame
    #: cut out of an XTF by detect_survey.
    frame_position: FramePosition | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "survey_id": self.survey_id,
            "frame_id": self.frame_id,
            "detections": [d.to_dict() for d in self.detections],
            "provenance": self.provenance,
            "warnings": self.warnings,
            "contract_version": self.contract_version,
            "frame_position": self.frame_position.to_dict() if self.frame_position else None,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def validate(payload: dict[str, Any]) -> list[str]:
    """Cheap self-check used by tests and by the fixture generator.

    Returns a list of problems; empty means the payload satisfies the contract.
    Deliberately not a schema library -- one less dependency to align.
    """
    problems: list[str] = []
    for key in ("survey_id", "frame_id", "detections", "contract_version"):
        if key not in payload:
            problems.append(f"missing top-level key: {key}")
    for i, det in enumerate(payload.get("detections", [])):
        where = f"detections[{i}]"
        if det.get("class") not in CLASS_VALUES:
            problems.append(f"{where}.class invalid: {det.get('class')!r}")
        if det.get("uncertainty") not in UNCERTAINTY_VALUES:
            problems.append(f"{where}.uncertainty invalid: {det.get('uncertainty')!r}")
        conf = det.get("calibrated_confidence")
        if not isinstance(conf, (int, float)) or not 0.0 <= conf <= 1.0:
            problems.append(f"{where}.calibrated_confidence out of range: {conf!r}")
        bbox = det.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            problems.append(f"{where}.bbox must be [x, y, w, h]")
        has_lat, has_lon = det.get("latitude") is not None, det.get("longitude") is not None
        if has_lat != has_lon:
            problems.append(f"{where} has only one of latitude/longitude")
        if has_lat and det.get("localization") == "none":
            problems.append(f"{where} carries a position but localization is 'none'")
    return problems
