"""Generate contracts/*.schema.json FROM ghostnet.contract.

    python ai/scripts/export_schemas.py            # write
    python ai/scripts/export_schemas.py --check    # fail if stale (for CI)

Why generated and not hand-written: a hand-maintained schema is a second
source of truth. The day someone adds a field to `Detection` and forgets the
JSON file, Member 2's validator starts rejecting valid payloads -- during
integration week, which is the worst possible time to debug it. Here the
dataclasses ARE the contract and the schema is a build artefact, so the two
cannot disagree. `--check` in CI makes a forgotten regeneration a red build
rather than a silent divergence.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import types
import typing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ghostnet.contract import (  # noqa: E402
    CONTRACT_VERSION,
    Detection,
    Dimensions,
    EvidenceSummary,
    FrameResult,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "contracts"

_PRIMITIVES = {str: "string", float: "number", int: "integer", bool: "boolean"}

# Field-level prose. Keys are "<Dataclass>.<field>". Kept here rather than in
# contract.py so the runtime package stays free of documentation weight.
DESCRIPTIONS: dict[str, str] = {
    "Detection.detection_id": "Stable per-detection identifier, unique within a frame.",
    "Detection.cls": "Detected class, from the closed vocabulary.",
    "Detection.raw_score": "Uncalibrated detector score. Diagnostic only; do NOT display or threshold on it.",
    "Detection.calibrated_confidence": "Temperature-scaled probability. This is the number to show and threshold on.",
    "Detection.uncertainty": "Confidence band for the UI. Capped at medium while the model is uncalibrated, so a low band is a real claim.",
    "Detection.bbox": "[x, y, width, height] in pixels, top-left origin.",
    "Detection.mask": "Optional polygon, [[x, y], ...]. Null when the model is detection-only.",
    "Detection.latitude": "WGS84 latitude. Null when geometry or the nav fix was unavailable; never fabricated.",
    "Detection.longitude": "WGS84 longitude. Null under the same conditions as latitude.",
    "Detection.position_error_m": "Radius of the position-uncertainty circle, metres. Render this, not a bare pin.",
    "Detection.localization": "How the position was derived. A value of none means no position is claimed.",
    "Detection.review_status": "Human review state. Owned by Member 2 after ingest; the AI always emits pending.",
    "Detection.model_version": "Version of the model that produced this detection.",
    "Dimensions.width": "Across-track size in ground metres, after slant-range correction. Null if unavailable.",
    "Dimensions.length": "Along-track size in metres. Null unless the along-track pixel scale is known.",
    "Dimensions.status": "Estimated from sonar geometry; measured only with verified range resolution and altitude; otherwise unavailable.",
    "EvidenceSummary.artificial_verification": "Why this was judged artificial or natural.",
    "EvidenceSummary.shadow_context": "Acoustic-shadow support, the classic side-scan cue for a raised object.",
    "EvidenceSummary.notes": "Free text for the reviewer.",
    "FrameResult.survey_id": "Identifier of the survey this frame belongs to.",
    "FrameResult.frame_id": "Identifier of the frame within the survey.",
    "FrameResult.detections": "Reported detections. An empty list is a valid, meaningful result: clean seabed.",
    "FrameResult.provenance": "Model, dataset, preprocessing and calibration versions behind this result.",
    "FrameResult.warnings": "Non-fatal conditions. Surface these in the UI; they explain missing positions and suppressed detections.",
    "FrameResult.contract_version": "Semver of this contract. A major bump is a breaking change for Member 2.",
}

# `class` is a Python keyword, so the dataclass field is named `cls`.
FIELD_RENAMES = {"cls": "class"}


def _schema_for(annotation: typing.Any, defs: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Translate one type annotation into a JSON Schema fragment."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is typing.Literal:
        return {"type": "string", "enum": list(args)}

    # X | None  ->  nullable X
    if origin is typing.Union or origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            inner = dict(_schema_for(non_none[0], defs))
            if isinstance(inner.get("type"), str):
                inner["type"] = [inner["type"], "null"]
                return inner
            return {"oneOf": [inner, {"type": "null"}]}
        return {"oneOf": [_schema_for(a, defs) for a in non_none] + [{"type": "null"}]}

    if origin is list:
        return {"type": "array", "items": _schema_for(args[0], defs) if args else {}}

    if origin is dict:
        return {"type": "object", "additionalProperties": {"type": "string"}}

    if annotation in _PRIMITIVES:
        return {"type": _PRIMITIVES[annotation]}

    if dataclasses.is_dataclass(annotation):
        name = annotation.__name__
        if name not in defs:
            defs[name] = None  # reserve the slot first; guards against recursion
            defs[name] = _object_schema(annotation, defs)
        return {"$ref": "#/$defs/" + name}

    return {}


def _object_schema(cls: type, defs: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Build an object schema from a dataclass, preserving required-ness.

    A field with no default is required; a field with one is optional. That is
    exactly the distinction the dataclass already encodes, so it is read here
    rather than restated by hand.
    """
    hints = typing.get_type_hints(cls)
    props: dict[str, typing.Any] = {}
    required: list[str] = []

    for f in dataclasses.fields(cls):
        key = FIELD_RENAMES.get(f.name, f.name)
        frag = _schema_for(hints[f.name], defs)
        desc = DESCRIPTIONS.get(cls.__name__ + "." + f.name)
        if desc:
            frag = {**frag, "description": desc}
        props[key] = frag
        has_default = (
            f.default is not dataclasses.MISSING
            or f.default_factory is not dataclasses.MISSING  # type: ignore[misc]
        )
        if not has_default:
            required.append(key)

    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def build_output_schema() -> dict[str, typing.Any]:
    defs: dict[str, typing.Any] = {}
    root = _object_schema(FrameResult, defs)
    for cls in (Detection, Dimensions, EvidenceSummary):
        if cls.__name__ not in defs:
            defs[cls.__name__] = _object_schema(cls, defs)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ghostnet-ai/contracts/ai-output.schema.json",
        "title": "GhostNet-AI frame result",
        "description": (
            "What the AI returns for ONE sonar frame. Generated from "
            "ghostnet/contract.py by ai/scripts/export_schemas.py; do not edit by hand. "
            "Contract version " + CONTRACT_VERSION + "."
        ),
        "$defs": defs,
        **root,
    }


def build_input_schema() -> dict[str, typing.Any]:
    """What Member 2 sends.

    Every navigation field is optional on purpose: real surveys have gaps, and
    the pipeline is required to degrade to a detection without coordinates
    rather than reject the frame or invent a position.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ghostnet-ai/contracts/ai-input.schema.json",
        "title": "GhostNet-AI inference request",
        "type": "object",
        "properties": {
            "survey_id": {"type": "string", "description": "Survey this frame belongs to."},
            "frame_id": {"type": "string", "description": "Frame identifier. Defaults to the image filename stem."},
            "image": {
                "type": "string",
                "description": (
                    "The frame itself: a multipart file part, or a URL the AI service can fetch. "
                    "NOT a local filesystem path. When the backend and the AI run on different "
                    "machines, a path valid on one is meaningless on the other."
                ),
            },
            "latitude": {"type": ["number", "null"], "description": "GPS latitude of the towfish at this ping."},
            "longitude": {"type": ["number", "null"], "description": "GPS longitude of the towfish at this ping."},
            "heading_deg": {"type": ["number", "null"], "description": "Course over ground in degrees, 0 = north."},
            "altitude_m": {"type": ["number", "null"], "description": "Towfish height above the seabed. Required for slant-range correction."},
            "nadir_col": {"type": ["number", "null"], "description": "Image column directly beneath the towfish."},
            "range_resolution_m": {"type": ["number", "null"], "description": "Metres of SLANT range per pixel, across-track."},
            "along_track_res_m": {"type": ["number", "null"], "description": "Metres per pixel row. Without it there is no length estimate."},
            "layback_m": {"type": ["number", "null"], "description": "Horizontal tow-cable offset behind the GPS antenna."},
            "nadir_row": {"type": ["number", "null"], "description": "Reference row for along-track offsets."},
        },
        "required": ["image"],
        "additionalProperties": True,
        "x-notes": [
            "Coordinates are emitted only when latitude, longitude, heading_deg, altitude_m, "
            "nadir_col and range_resolution_m are ALL present. Otherwise localization is 'none' "
            "and a warning explains why.",
        ],
    }


def build_error_schema() -> dict[str, typing.Any]:
    """The envelope for a hard failure.

    Note the asymmetry, and tell Member 2 about it: the ghostnet package never
    raises for a missing model, missing metadata or a missing GPU. It returns a
    valid result carrying `warnings`. This schema therefore covers only
    transport-level failures once an HTTP service exists: an unreadable upload,
    a malformed request, an out-of-memory crash.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ghostnet-ai/contracts/ai-error.schema.json",
        "title": "GhostNet-AI error",
        "type": "object",
        "properties": {
            "error": {
                "type": "string",
                "enum": ["bad_request", "unreadable_image", "internal_error", "out_of_memory"],
            },
            "message": {"type": "string", "description": "Human-readable and safe to log. Never contains a filesystem path."},
            "survey_id": {"type": ["string", "null"]},
            "frame_id": {"type": ["string", "null"]},
            "contract_version": {"type": "string", "const": CONTRACT_VERSION},
        },
        "required": ["error", "message", "contract_version"],
        "additionalProperties": False,
        "x-notes": [
            "Degraded conditions are NOT errors. No weights, no GPU and no navigation metadata "
            "all return a valid ai-output payload with `warnings` set. Member 2 should render "
            "warnings, not treat them as failures.",
        ],
    }


SCHEMAS = {
    "ai-input.schema.json": build_input_schema,
    "ai-output.schema.json": build_output_schema,
    "ai-error.schema.json": build_error_schema,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if any schema is stale")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, build in SCHEMAS.items():
        text = json.dumps(build(), indent=2) + "\n"
        path = OUT_DIR / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print("wrote contracts/" + name)

    if args.check:
        if stale:
            print("STALE (re-run without --check): " + ", ".join(stale))
            return 1
        print("contracts/ are up to date with ghostnet.contract v" + CONTRACT_VERSION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
