import enum


class SurveyStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class FileValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobStage(str, enum.Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    DECODING = "DECODING"
    PREPROCESSING = "PREPROCESSING"
    DETECTION = "DETECTION"
    VERIFICATION = "VERIFICATION"
    CALIBRATION = "CALIBRATION"
    GEOTAGGING = "GEOTAGGING"
    SAVING = "SAVING"
    DONE = "DONE"


class Uncertainty(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    UNKNOWN = "unknown"
    ACCEPTED_ARTIFICIAL = "accepted_artificial"
    REJECTED_NATURAL = "rejected_natural"


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportType(str, enum.Enum):
    FULL_SURVEY = "full_survey"
    FILTERED_DETECTIONS = "filtered_detections"
    SELECTED_DETECTION = "selected_detection"


class ReportFormat(str, enum.Enum):
    CSV = "csv"
    JSON = "json"


class ReportStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
