"""GhostNet-AI — Side-Scan Sonar detection pipeline (SIH26057, Member 1).

Public surface, deliberately small:

    from ghostnet import detect, detect_batch, warmup, CONTRACT_VERSION
"""

from .config import SETTINGS, Settings
from .contract import CONTRACT_VERSION, Detection, FrameResult, validate
from .infer import detect, detect_batch, load_model, warmup

__version__ = "0.1.0"

__all__ = [
    "detect",
    "detect_batch",
    "warmup",
    "load_model",
    "validate",
    "Detection",
    "FrameResult",
    "Settings",
    "SETTINGS",
    "CONTRACT_VERSION",
    "__version__",
]
