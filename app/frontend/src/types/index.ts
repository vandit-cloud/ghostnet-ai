export type SurveyStatus =
  | "UPLOADED"
  | "VALIDATING"
  | "PROCESSING"
  | "PARTIAL"
  | "COMPLETED"
  | "FAILED"
  | "ARCHIVED";

export type JobStatus = "QUEUED" | "VALIDATING" | "PROCESSING" | "PARTIAL" | "COMPLETED" | "FAILED" | "CANCELLED";

export type JobStage =
  | "QUEUED"
  | "VALIDATING"
  | "DECODING"
  | "PREPROCESSING"
  | "DETECTION"
  | "VERIFICATION"
  | "CALIBRATION"
  | "GEOTAGGING"
  | "SAVING"
  | "DONE";

export type Uncertainty = "low" | "medium" | "high";
export type Priority = "low" | "medium" | "high" | "critical";
export type ReviewStatus = "pending" | "unknown" | "accepted_artificial" | "rejected_natural";
export type ReportType = "full_survey" | "filtered_detections" | "selected_detection";
export type ReportFormat = "csv" | "json";
export type ReportStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";
export type FileValidationStatus = "PENDING" | "VALID" | "INVALID";

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}

export interface Survey {
  id: string;
  name: string;
  source: string | null;
  sonar_type: string | null;
  status: SurveyStatus;
  file_count: number;
  processed_count: number;
  detection_count: number;
  review_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SurveyFile {
  id: string;
  survey_id: string;
  filename: string;
  format: string;
  size: number;
  checksum: string;
  validation_status: FileValidationStatus;
  validation_message: string | null;
  metadata_status: FileValidationStatus;
  created_at: string;
}

export interface ProcessingJob {
  id: string;
  survey_id: string;
  type: string;
  status: JobStatus;
  stage: JobStage;
  progress: number;
  frames_total: number;
  frames_processed: number;
  frames_failed: number;
  detections_found: number;
  started_at: string | null;
  completed_at: string | null;
  error_summary: string | null;
  created_at: string;
}

export interface BBox {
  x: number | null;
  y: number | null;
  w: number | null;
  h: number | null;
}

export interface Dimensions {
  width: number | null;
  length: number | null;
  area: number | null;
  status: string | null;
}

export interface Detection {
  id: string;
  detection_ref: string;
  survey_id: string;
  survey_name: string | null;
  frame_id: string;
  detection_class: string;
  raw_score: number | null;
  calibrated_confidence: number | null;
  uncertainty: Uncertainty | null;
  bbox: BBox;
  mask_reference: string | null;
  latitude: number | null;
  longitude: number | null;
  position_error_m: number | null;
  localization_method: string | null;
  depth: number | null;
  dimensions: Dimensions;
  priority: Priority;
  review_status: ReviewStatus;
  model_version: string | null;
  evidence_summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DetectionReview {
  id: string;
  detection_id: string;
  reviewer: string | null;
  decision: ReviewStatus;
  note: string | null;
  created_at: string;
}

export interface MapMarker {
  detection_id: string;
  detection_ref: string;
  detection_class: string;
  latitude: number;
  longitude: number;
  priority: Priority;
  review_status: ReviewStatus;
  calibrated_confidence: number | null;
  uncertainty: Uncertainty | null;
  position_error_m: number | null;
  depth: number | null;
  created_at: string;
}

export interface TrackPoint {
  latitude: number;
  longitude: number;
  timestamp: string | null;
  range: number | null;
}

export interface SurveyMap {
  survey_id: string;
  bounds: { min_lat: number; min_lon: number; max_lat: number; max_lon: number } | null;
  markers: MapMarker[];
  track: TrackPoint[];
}

export interface Report {
  id: string;
  survey_id: string;
  type: ReportType;
  format: ReportFormat;
  status: ReportStatus;
  filters: Record<string, unknown>;
  error_summary: string | null;
  created_at: string;
  completed_at: string | null;
}

export type SystemComponentState = "ONLINE" | "ACTIVE" | "LIVE" | "CONNECTING" | "OFFLINE" | "STALE" | "ERROR";

export interface SystemComponentStatus {
  name: string;
  state: SystemComponentState;
  detail: string | null;
}

export interface SystemStatus {
  components: SystemComponentStatus[];
  checked_at: string;
}

export interface RealtimeEvent {
  event: "job.updated" | "frame.processed" | "detection.created" | "detection.updated" | "report.completed";
  survey_id: string;
  [key: string]: unknown;
}

export type Role = "admin" | "operator" | "reviewer" | "viewer";

export interface AppUser {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface ClassCount {
  detection_class: string;
  count: number;
}

export interface PriorityCount {
  priority: Priority;
  count: number;
}

export interface ReviewFunnel {
  pending: number;
  unknown: number;
  accepted_artificial: number;
  rejected_natural: number;
}

export interface AnalyticsSummary {
  total_surveys: number;
  total_detections: number;
  total_reports: number;
  average_calibrated_confidence: number | null;
  class_distribution: ClassCount[];
  priority_distribution: PriorityCount[];
  review_funnel: ReviewFunnel;
  detection_trend: { date: string; count: number }[];
}

