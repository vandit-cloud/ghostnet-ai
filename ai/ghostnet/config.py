"""Runtime configuration for the GhostNet-AI inference package.

Every path is resolved relative to this file, then overridable by environment
variable, so the package behaves identically on Windows, Linux, in Docker and
on Member 2's machine. No absolute paths are ever baked in.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# ai/ghostnet/config.py -> ai/ghostnet -> ai
PACKAGE_ROOT = Path(__file__).resolve().parent
AI_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = AI_ROOT.parent


def _env_path(var: str, default: Path) -> Path:
    """Environment override wins; otherwise the repo-relative default."""
    raw = os.environ.get(var)
    return Path(raw).expanduser().resolve() if raw else default


def _read_json(path: Path) -> dict:
    """Read a small JSON sidecar, or {} when it is missing or unreadable.

    Provenance must never be the thing that fails an inference run, so every
    failure here degrades to "unknown" rather than raising. A corrupt sidecar
    leaves the version fields at their sentinels, which reads as "we do not
    know" -- the one honest answer available.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def resolve_device(preference: str = "auto") -> str:
    """Pick a torch device without importing torch until we must.

    'auto' -> cuda when genuinely usable, else cpu. Member 2's laptop or a CI
    runner may have no GPU at all; inference must still run, just slower.
    """
    if preference != "auto":
        return preference
    if os.environ.get("GHOSTNET_DEVICE"):
        return os.environ["GHOSTNET_DEVICE"]
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@dataclass
class Settings:
    # --- paths -------------------------------------------------------------
    models_dir: Path = field(default_factory=lambda: _env_path("GHOSTNET_MODELS_DIR", AI_ROOT / "models"))
    data_dir: Path = field(default_factory=lambda: _env_path("GHOSTNET_DATA_DIR", AI_ROOT / "data"))
    weights_path: Path | None = None

    # --- inference ---------------------------------------------------------
    device: str = field(default_factory=resolve_device)
    imgsz: int = 640
    #: Frames per model call in detect_batch. 8 is where this GPU stops idling
    #: (see _predict_many): 3.6 frames/s at batch 1, 64 at batch 8. Higher
    #: barely helps and costs VRAM, of which there is 4 GB.
    batch_size: int = 8
    # 4 GB VRAM is the binding constraint on this machine.
    batch: int = 4
    # FP16 halves activation memory, which is what actually buys headroom here.
    half: bool = True

    # Deliberately low: the calibrated-confidence policy in infer.py decides
    # what is actually reported. Filtering twice hides recall problems.
    raw_conf_threshold: float = 0.10
    iou_threshold: float = 0.50
    max_detections: int = 300

    # --- decision policy ---------------------------------------------------
    # Floors applied to CALIBRATED confidence when deciding what reaches a
    # human reviewer. They are asymmetric on purpose: an artificial anomaly is
    # actionable and a miss is expensive, so it gets a low bar; a 'natural'
    # call is context rather than a task, so it only earns screen space when
    # the model is fairly sure.
    #
    # IMPORTANT: evaluation scripts must set both to 0.0. Metrics computed on
    # policy-filtered output measure recall after the very filter that damaged
    # it -- the "filtering twice hides recall problems" trap noted above.
    review_floor_artificial: float = 0.20
    review_floor_natural: float = 0.45

    # --- tile-edge artifacts ----------------------------------------------
    #: Suppress detections that are thin strips welded to a frame border.
    #: See decision.is_edge_sliver for what this costs and why it is on.
    suppress_edge_slivers: bool = True
    #: How close to the border counts as touching it, in pixels. A YOLO box on
    #: the border lands on 0 or W-1, so this only absorbs rounding.
    edge_touch_px: int = 2
    #: Max thickness perpendicular to the border, as a fraction of that axis.
    #: The observed artifacts are 34-38 px in a 640 px tile: 5-6%.
    edge_sliver_max_thickness: float = 0.08
    #: Min extent parallel to the border, as a fraction of that axis. A real
    #: object clipped by a seam is rarely also a near-full-length strip.
    edge_sliver_min_extent: float = 0.40

    # Uncertainty band edges on calibrated confidence.
    uncertainty_low_edge: float = 0.75
    uncertainty_medium_edge: float = 0.45

    # --- versioning (§34: every inference identifies its provenance) -------
    model_id: str = "ghostnet-yolo11s"
    #: Filled in from the weights actually loaded -- see __post_init__. The
    #: literal below is what a payload reports when there are no weights at
    #: all, which is a real state (Member 2 can build the whole app before a
    #: model exists) and should be visibly labelled as such rather than
    #: claiming a version.
    model_version: str = "v0-stub"
    dataset_version: str = "none"
    #: Named filter from ghostnet.preprocess, applied before inference.
    #: "none" is deliberate and load-bearing: despeckling a model trained on
    #: raw frames costs 13% of mAP50. Change it only alongside a model trained
    #: the same way.
    preprocessing: str = "none"
    calibration_version: str = "none"

    def __post_init__(self) -> None:
        if self.weights_path is None:
            # GHOSTNET_WEIGHTS wins, then the promoted model, then nothing.
            #
            # The default used to be nothing at all, which meant detect()
            # returned empty detections plus a warning on any machine where
            # someone had not set an environment variable -- including Member
            # 2's, where the whole point is that the package works on import.
            # A trained run is promoted by copying it to models/trained/ and
            # refitting the calibrator against that path, so this default is
            # the model the project actually ships rather than whichever
            # experiment happened to be newest.
            env = os.environ.get("GHOSTNET_WEIGHTS")
            if env:
                self.weights_path = Path(env).expanduser().resolve()
            else:
                promoted = AI_ROOT / "models" / "trained" / "ghostnet.pt"
                self.weights_path = promoted if promoted.exists() else None
        else:
            self.weights_path = Path(self.weights_path)
        # Name the model in every payload it produces.
        #
        # This read "v0-stub" on every detection the project has ever emitted,
        # including the ones written into report.csv and handed to Member 2 --
        # so a stored result could not be traced back to the run that made it,
        # which is the entire purpose of a provenance block. The run name is
        # recoverable from the weights path (experiments/<run>/weights/best.pt),
        # and a promoted file falls back to its own stem.
        sidecar = (
            _read_json(Path(self.weights_path).with_suffix(".json"))
            if self.weights_path is not None
            else {}
        )

        if self.model_version == "v0-stub" and self.weights_path is not None:
            w = Path(self.weights_path)
            # A promoted file is a COPY, so its own name says nothing about
            # which run made it -- ghostnet.pt could be any of them. The
            # sidecar written at promotion time is the only thing that
            # knows, and it carries the source path and a hash so the claim
            # is checkable rather than asserted.
            if sidecar.get("model_version"):
                self.model_version = str(sidecar["model_version"])
            elif w.parent.name == "weights" and w.parent.parent.name:
                self.model_version = w.parent.parent.name
            else:
                self.model_version = w.stem

        # The DATASET is read from the sidecar, never from whichever build
        # happens to be sitting in data/processed right now.
        #
        # Those two diverge the moment anyone re-runs build_dataset.py, which
        # is exactly what staging a newly annotated class does. Reading the
        # live build_report.json would then stamp this model with a dataset it
        # was never trained on -- and a provenance block that is confidently
        # wrong is worse than one that admits ignorance, because nothing
        # downstream can tell the two apart.
        if self.dataset_version == "none" and sidecar.get("dataset_version"):
            self.dataset_version = str(sidecar["dataset_version"])

        # CALIBRATION, by contrast, is read live, because the temperature file
        # on disk is the one actually being applied to these scores. Naming the
        # temperature and the split it was fitted on puts the correction in the
        # payload itself, where a stored detection keeps it; decision.py's
        # mismatch warning only reaches whoever is watching at the time.
        if self.calibration_version == "none":
            cal = _read_json(Path(self.models_dir) / "calibrator" / "temperature.json")
            if cal.get("temperature") is not None:
                try:
                    self.calibration_version = "T%.4f-%s-n%s" % (
                        float(cal["temperature"]),
                        cal.get("fitted_on", "unknown"),
                        cal.get("n_predictions", "?"),
                    )
                except (TypeError, ValueError):
                    pass  # leave the sentinel; an unparseable file is "unknown"

        if self.device == "cpu":
            self.half = False  # fp16 on CPU is slower, not faster

    def quantize(self) -> int:
        """Ultralytics >= 8.4 replaced the boolean `half` with `quantize`,
        which takes a bit width: 16 for FP16, 32 for FP32. Passing `half`
        still works but warns on every call. Translate here so the rest of
        the package keeps the readable boolean."""
        return 16 if self.half else 32

    def provenance(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "dataset_version": self.dataset_version,
            "preprocessing_version": self.preprocessing,
            "calibration_version": self.calibration_version,
        }


SETTINGS = Settings()
