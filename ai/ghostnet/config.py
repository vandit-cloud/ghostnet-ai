"""Runtime configuration for the GhostNet-AI inference package.

Every path is resolved relative to this file, then overridable by environment
variable, so the package behaves identically on Windows, Linux, in Docker and
on Member 2's machine. No absolute paths are ever baked in.
"""

from __future__ import annotations

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

    # Uncertainty band edges on calibrated confidence.
    uncertainty_low_edge: float = 0.75
    uncertainty_medium_edge: float = 0.45

    # --- versioning (§34: every inference identifies its provenance) -------
    model_id: str = "ghostnet-yolo11s"
    model_version: str = "v0-stub"
    dataset_version: str = "none"
    preprocessing_version: str = "v0"
    calibration_version: str = "none"

    def __post_init__(self) -> None:
        if self.weights_path is None:
            env = os.environ.get("GHOSTNET_WEIGHTS")
            self.weights_path = Path(env).expanduser().resolve() if env else None
        else:
            self.weights_path = Path(self.weights_path)
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
            "preprocessing_version": self.preprocessing_version,
            "calibration_version": self.calibration_version,
        }


SETTINGS = Settings()
