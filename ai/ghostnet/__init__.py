"""GhostNet-AI — Side-Scan Sonar detection pipeline (SIH26057, Member 1).

Public surface, deliberately small:

    from ghostnet import detect, detect_batch, warmup, CONTRACT_VERSION
"""

from . import preprocess, sdf, xtf
from .config import SETTINGS, Settings
from .contract import CONTRACT_VERSION, Detection, FrameResult, validate
from .infer import detect, detect_batch, load_model, warmup
from .report import csv_rows, geojson_features, write_csv, write_geojson
from .survey import SurveyFrame, detect_survey, iter_survey_frames

__version__ = "0.1.0"

__all__ = [
    # one frame
    "detect",
    "detect_batch",
    # a whole sonar file: xtf/sdf -> waterfall -> tiles -> detections
    "detect_survey",
    # tiling only, for a consumer that scores through its own pipeline
    "iter_survey_frames",
    "SurveyFrame",
    # lifecycle
    "warmup",
    "load_model",
    # output
    "write_csv",
    "csv_rows",
    "write_geojson",
    "geojson_features",
    "validate",
    "Detection",
    "FrameResult",
    "CONTRACT_VERSION",
    # config, and the two modules a caller may want directly
    "Settings",
    "SETTINGS",
    "sdf",
    "xtf",
    "preprocess",
    "__version__",
]
