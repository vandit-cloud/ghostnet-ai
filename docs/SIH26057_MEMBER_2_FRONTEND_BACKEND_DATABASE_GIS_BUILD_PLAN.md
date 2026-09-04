# SIH26057 — GhostNet-AI
# MEMBER 2 — FRONTEND + BACKEND + DATABASE + GIS BUILD PLAN

> **Owner:** Member 2
> **Primary responsibility:** Web application + FastAPI backend + PostgreSQL/PostGIS + GIS + dashboard + upload/processing UI + detection/review UI + reports + real-time connection + integration with Member 1 AI service.
>
> **Goal:** Build the complete user-facing product around Member 1's AI/ML pipeline and connect it through a stable API/database contract.

---

# 1. Your Responsibility in the 2-Member Team

## Member 2 owns

```text
FRONTEND
   ↓
FASTAPI BACKEND
   ↓
DATABASE / POSTGIS
   ↓
FILE / RESULT MANAGEMENT
   ↓
GIS
   ↓
REPORTS
   ↓
REAL-TIME UPDATES
   ↓
MEMBER 1 AI INTEGRATION
```

## Member 1 owns

```text
DATASET
SONAR PREPROCESSING
AI / ML
NATURAL vs ARTIFICIAL VERIFICATION
CONFIDENCE / UNCERTAINTY
UNKNOWN HANDLING
GEOTAGGING LOGIC
AI OUTPUT JSON
```

Do not duplicate Member 1's model/training work.

Your job is to make the AI usable as a real web application.

---

# 2. Product Goal

Build a web application where an operator can:

```text
Login / enter application
        ↓
Create/select survey
        ↓
Upload SSS image/log
        ↓
Upload/associate metadata
        ↓
Validate
        ↓
Start AI processing
        ↓
Monitor progress
        ↓
View detections
        ↓
View sonar evidence
        ↓
View GIS location
        ↓
View confidence / uncertainty
        ↓
Review uncertain detections
        ↓
Generate JSON/CSV report
```

The UI should feel like a professional marine survey/AI analysis application, not a static dashboard.

---

# 3. Technology Stack

## Frontend

Recommended:

```text
React
or
Next.js
```

Use:

```text
TypeScript
```

Recommended supporting technologies:

```text
React Query / TanStack Query
Zustand or equivalent state management
React Hook Form
Zod or equivalent validation
```

Choose equivalent libraries when justified.

## GIS

Use one:

```text
Leaflet
or
MapLibre
```

For advanced 3D later:

```text
MapLibre-compatible 3D
or
deck.gl / Three.js where justified
```

Do not make 3D mandatory for the first working version.

## Backend

```text
Python 3.11+
FastAPI
Pydantic
SQLAlchemy
Alembic
```

## Database

```text
PostgreSQL
PostGIS
```

Use PostGIS when spatial queries/geometries are needed.

## Real-time

Prefer:

```text
WebSocket
or
Server-Sent Events (SSE)
```

## File storage

Initial local development can use:

```text
local filesystem
```

Production-ready architecture should use an object/file storage abstraction so the storage provider can be replaced later.

## Testing

Frontend:

```text
Vitest / Jest
React Testing Library
Playwright where appropriate
```

Backend:

```text
pytest
httpx
```

## API documentation

```text
FastAPI OpenAPI / Swagger
```

## Deployment

```text
Docker
Docker Compose for local development
```

---

# 4. Frontend Application Structure

Recommended:

```text
src/
├── app/
├── components/
├── features/
│   ├── auth/
│   ├── surveys/
│   ├── upload/
│   ├── processing/
│   ├── detections/
│   ├── sonar/
│   ├── map/
│   ├── review/
│   ├── reports/
│   └── dashboard/
├── services/
├── api/
├── state/
├── hooks/
├── types/
├── utils/
└── tests/
```

Keep domain logic in feature modules.

Do not place all logic in one giant page component.

---

# 5. Backend Structure

Recommended:

```text
backend/
├── app/
│   ├── api/
│   │   ├── auth/
│   │   ├── surveys/
│   │   ├── files/
│   │   ├── processing/
│   │   ├── detections/
│   │   ├── maps/
│   │   ├── reports/
│   │   └── health/
│   │
│   ├── models/
│   ├── schemas/
│   ├── services/
│   │   ├── survey_service.py
│   │   ├── processing_service.py
│   │   ├── detection_service.py
│   │   ├── report_service.py
│   │   └── ai_service.py
│   │
│   ├── repositories/
│   ├── workers/
│   ├── storage/
│   ├── realtime/
│   ├── core/
│   └── main.py
│
├── migrations/
├── tests/
└── requirements/
```

Keep:

```text
router
→ service
→ repository
→ database
```

Do not put complex business logic directly inside API route handlers.

---

# 6. First Task — Freeze the Contract With Member 1

Before integration, agree on:

```text
1. AI input format
2. AI output format
3. Error format
4. Model version format
5. Processing status format
```

Member 1 should provide something equivalent to:

```text
image
+
frame_id
+
survey_id
+
metadata
↓
AI
↓
normalized detection JSON
```

Your backend must not depend on internal YOLO/PyTorch implementation details.

---

# 7. AI Input Contract

Send:

```json
{
  "survey_id": "SURVEY-001",
  "frame_id": "PING-18452",
  "image_reference": "...",
  "metadata": {
    "timestamp": "...",
    "latitude": null,
    "longitude": null,
    "heading": null,
    "depth": null,
    "range": null
  }
}
```

The exact values depend on the available data.

Do not invent missing metadata.

---

# 8. AI Output Contract

Expect:

```json
{
  "survey_id": "SURVEY-001",
  "frame_id": "PING-18452",
  "detections": [
    {
      "detection_id": "D-00027",
      "class": "ghost_net",
      "raw_score": 0.91,
      "calibrated_confidence": 0.93,
      "uncertainty": "low",
      "bbox": [320, 180, 190, 120],
      "mask": null,
      "latitude": 20.123456,
      "longitude": 70.123456,
      "position_error_m": 4.5,
      "localization": "frame-level",
      "dimensions": {
        "width": 3.2,
        "length": 8.4,
        "status": "estimated"
      },
      "review_status": "pending",
      "model_version": "ghostnet-yolo11s-v1",
      "evidence_summary": {}
    }
  ]
}
```

Fields may be null.

Do not reinterpret a missing field as zero.

---

# 9. Error Contract

Member 1 should return structured errors.

Example:

```json
{
  "status": "failed",
  "frame_id": "PING-100",
  "error_code": "INVALID_FRAME",
  "message": "Frame could not be processed."
}
```

Your backend should convert service errors into consistent API errors.

Never expose raw stack traces to frontend users.

---

# 10. Page Map

Build these core pages first:

```text
/auth/login

/app/dashboard
/app/surveys
/app/surveys/new
/app/surveys/:surveyId
/app/surveys/:surveyId/process
/app/sonar
/app/sonar/:detectionId
/app/detections
/app/detections/:detectionId
/app/map
/app/review
/app/review/:detectionId
/app/reports
/app/reports/:reportId
```

Advanced pages can come later.

---

# 11. Page 1 — Login

## UI

```text
GhostNet-AI
Marine Sonar Intelligence

Username/email
Password

[Login]

[Forgot Password]
```

## States

```text
Idle
Submitting
Invalid credentials
Server unavailable
Success
```

For the initial basic version, use the authentication mechanism defined by the project architecture.

Later, add full company-grade auth/RBAC.

---

# 12. Page 2 — Dashboard

Purpose:

> Give the operator an immediate survey overview.

## Top

```text
Current Survey
Processing Status
Last Updated
```

## KPIs

```text
Frames Processed
Candidates
Confirmed Artificial
High Priority
Needs Review
Rejected Natural
```

These values must come from the backend.

## Main sections

```text
Detection Trend
Class Distribution
Recent Detections
Map Preview
Processing Status
```

## Real-time

Update relevant KPIs when new detections arrive.

Do not reload the entire page.

---

# 13. Page 3 — Surveys

Show:

```text
Survey ID
Name
Source
Sonar Type
Files
Processed
Detections
Processing Status
Created At
```

## Actions

```text
Open
Process
View
Report
Archive
```

Use pagination for many surveys.

---

# 14. Page 4 — New Survey / Upload

## Workflow

```text
Create/select survey
↓
Upload SSS file
↓
Upload/associate metadata
↓
Validate
↓
Preview
↓
Start processing
```

## Upload UI

Support:

- drag-and-drop
- browse
- file list
- size
- format
- validation result

## Validation

Check:
- file type
- file size
- supported content
- metadata readability
- image readability
- coordinate validity where present

Never silently invent GPS.

---

# 15. Page 5 — Survey Detail

Show:

```text
Survey summary
File list
Processing status
Map
Detection count
Review count
Quality summary
```

Actions:

```text
Start / Continue Processing
View Detections
Open Map
Generate Report
```

---

# 16. Page 6 — Live Processing

Show:

```text
VALIDATING
DECODING
PREPROCESSING
DETECTION
VERIFICATION
CALIBRATION
GEOTAGGING
SAVING
```

Show:

```text
Frames processed
Frames failed
Detections
Current stage
Processing status
```

If exact percent is measurable:

```text
37%
```

Otherwise use stage-based status.

Do not fabricate progress.

---

# 17. Processing Job Lifecycle

Use:

```text
QUEUED
VALIDATING
PROCESSING
PARTIAL
COMPLETED
FAILED
CANCELLED
```

Store server-side job status.

If browser refreshes while a job is running:

```text
Refresh
↓
Same processing page
↓
Frontend asks backend for job status
↓
Current job state restored
```

The browser must NOT restart the processing job.

---

# 18. Page 7 — Detection Results

Display a list/grid/table of detections.

Columns:

```text
Detection ID
Class
Confidence
Uncertainty
Priority
Location
Review Status
Timestamp
```

Click a row:

```text
→ Detection Detail
```

Filters:

```text
Class
Confidence
Priority
Review Status
Survey
Date
```

Search by detection ID/survey/class where applicable.

---

# 19. Page 8 — Detection Detail

Show:

```text
Detection ID
Class
AI confidence
Calibrated confidence
Uncertainty
Status
```

Then:

```text
Sonar evidence
Detection overlay
Location
Position error
Dimensions
Evidence
Priority
Model version
Review status
```

Actions:

```text
View on Map
View Sonar
Open Review
Generate/Include in Report
```

---

# 20. Page 9 — Sonar Investigation

Use a serious investigation workspace.

Basic version:

```text
┌───────────────────┬─────────────────────┐
│ Sonar Image       │ Detection Details   │
│                   │                     │
│ Original          │ Class               │
│ Processed         │ Confidence          │
│ AI Overlay        │ Uncertainty         │
│ Bounding Box      │ Evidence             │
│ Mask (if any)     │ Location             │
└───────────────────┴─────────────────────┘
```

Later enhancement:

```text
Sonar
↔ GIS
↔ Detection Details
```

Keep the architecture ready for this.

---

# 21. Page 10 — GIS Map

Use:

```text
Leaflet
or
MapLibre
```

Show:

- survey track if available
- survey bounds
- detection markers
- selected detection
- class filters
- priority filters

Marker click:

```text
Marker
→ Detection detail
```

Detection click:

```text
Detection
→ center map
→ highlight marker
```

Use actual coordinates.

---

# 22. Map Data

Backend map API should return only data required by the current viewport/filter where practical.

For large datasets consider:

```text
bounding-box queries
pagination
clustering
```

Do not send thousands of markers to the browser unnecessarily.

---

# 23. Basic 3D Strategy

3D is a future/advanced layer, not a blocker for the basic build.

Initial:

```text
High-quality 2D GIS
```

Design the map abstraction so a future 3D renderer can use the same detection/location API.

When real bathymetry/depth exists, 3D can visualize it.

Never fake measured seafloor data.

---

# 24. Page 11 — Review

Show uncertain detections.

Categories:

```text
Pending
Unknown
Accepted Artificial
Rejected Natural
```

Review workspace:

```text
Sonar image
Map location
Confidence
Uncertainty
Evidence
```

Actions:

```text
Accept Artificial
Reject Natural
Mark Unknown
Add Note
Save
```

Backend persists the review.

---

# 25. Page 12 — Reports

Support:

```text
CSV
JSON
```

Optional later:

```text
PDF
```

Report types:

```text
Full Survey
Filtered Detections
Selected Detection
```

Report generation can be a background job.

---

# 26. Dashboard ↔ Backend ↔ AI Flow

When user clicks Start Processing:

```text
Frontend
  ↓
POST /surveys/{id}/process
  ↓
Backend creates job
  ↓
Backend sends frames to Member 1 AI
  ↓
AI returns detection JSON
  ↓
Backend validates result
  ↓
Database stores result
  ↓
Realtime event emitted
  ↓
Frontend updates
```

No frontend-to-database direct access.

---

# 27. Database Design

Basic entities:

```text
surveys
survey_files
sonar_frames
sonar_metadata
processing_jobs
detections
reports
```

Later expansion:

```text
users
roles
permissions
detection_evidence
detection_reviews
alerts
model_versions
datasets
audit_logs
```

Do not overbuild the schema before the core workflow works.

---

# 28. Survey Table

```text
id
name
source
sonar_type
status
created_at
updated_at
```

Possible status:

```text
UPLOADED
VALIDATING
PROCESSING
PARTIAL
COMPLETED
FAILED
ARCHIVED
```

---

# 29. Survey File Table

```text
id
survey_id
filename
storage_reference
format
size
checksum
validation_status
metadata_status
created_at
```

Never trust filename alone.

---

# 30. Sonar Frame Table

```text
id
survey_id
file_id
frame_id
ping_id
timestamp
image_reference
latitude
longitude
heading
depth
range
resolution
quality_status
metadata_source
```

Allow nullable fields when unavailable.

---

# 31. Detection Table

```text
id
survey_id
frame_id
source_file_id
class
raw_score
calibrated_confidence
uncertainty
bbox/mask reference
latitude
longitude
position_error_m
localization_method
depth
width
length
area
priority
review_status
model_version
evidence_summary
created_at
updated_at
```

Use PostGIS geometry when spatial operations are required.

---

# 32. Processing Job Table

```text
id
survey_id
type
status
stage
progress
started_at
completed_at
error_summary
retry_count
created_at
```

Do not restart the same job merely because a browser refresh happened.

---

# 33. Report Table

```text
id
survey_id
type
format
status
filters
storage_reference
created_at
completed_at
error_summary
```

---

# 34. Database Relationships

```text
Survey
 ├── Survey Files
 │     └── Sonar Frames
 │            └── Detections
 ├── Processing Jobs
 └── Reports
```

Use foreign keys and constraints.

---

# 35. Database Migrations

Use:

```text
Alembic
```

Never manually modify production schema without migration tracking.

Every schema change should be reproducible.

---

# 36. Basic API Endpoints

## Surveys

```text
POST /api/v1/surveys
GET /api/v1/surveys
GET /api/v1/surveys/{survey_id}
PATCH /api/v1/surveys/{survey_id}
```

## Files

```text
POST /api/v1/surveys/{survey_id}/files
GET /api/v1/surveys/{survey_id}/files
```

## Processing

```text
POST /api/v1/surveys/{survey_id}/process
GET /api/v1/jobs/{job_id}
POST /api/v1/jobs/{job_id}/cancel
```

## Detections

```text
GET /api/v1/detections
GET /api/v1/detections/{detection_id}
```

## Map

```text
GET /api/v1/maps/surveys/{survey_id}/detections
```

## Review

```text
POST /api/v1/detections/{detection_id}/review
GET /api/v1/detections/{detection_id}/reviews
```

## Reports

```text
POST /api/v1/reports
GET /api/v1/reports
GET /api/v1/reports/{report_id}
GET /api/v1/reports/{report_id}/download
```

## Health

```text
GET /api/v1/health
GET /api/v1/health/liveness
GET /api/v1/health/readiness
```

---

# 37. API Rules

Every endpoint must have:

```text
Input schema
Output schema
Validation
Error handling
HTTP status code
Authentication requirement
```

Use consistent error responses.

Example:

```json
{
  "error": {
    "code": "SURVEY_NOT_FOUND",
    "message": "Survey was not found.",
    "request_id": "..."
  }
}
```

---

# 38. Pagination

For list APIs:

```text
GET /detections?page=1&page_size=50
```

or cursor pagination where appropriate.

Never assume a database will always contain only a few rows.

---

# 39. Filtering

Backend should support filtering for:

```text
survey
class
confidence
priority
review status
date range
geographic region
```

Avoid fetching all records and filtering everything only in the browser.

---

# 40. GIS Spatial Queries

When PostGIS is enabled, support:

```text
detections within survey area
detections inside bounding box
detections within radius
```

Use spatial indexes.

Only implement queries actually needed by the product.

---

# 41. Basic Real-Time

Use:

```text
WebSocket
or
SSE
```

Events may include:

```text
job.updated
frame.processed
detection.created
detection.updated
report.completed
```

Example:

```json
{
  "event": "detection.created",
  "survey_id": "SURVEY-001",
  "detection_id": "D-00027"
}
```

Frontend then fetches/updates the relevant data.

---

# 42. Reconnect

When connection is lost:

```text
OFFLINE / RECONNECTING
```

Then:

```text
reconnect
→ query current job/state
→ reconcile missed events
→ continue
```

Do not restart processing just because WebSocket disconnected.

---

# 43. Refresh Behavior — Mandatory

Browser refresh:

```text
F5
→ same current route
→ restore required server state
```

Examples:

```text
/detections/D-00027
```

Refresh:

→ stay on D-00027.

Processing page refresh:

→ stay on processing page  
→ restore job status.

Map refresh:

→ restore map when practical.

---

# 44. State Persistence

Preserve where practical:

```text
selected survey
search
filters
selected detection
active tab
date range
map center
map zoom
pagination
```

Route/query parameters may be used for shareable/filterable state.

Do not put sensitive data into URLs.

---

# 45. Browser Navigation

Back/forward should behave naturally.

Example:

```text
Detection List
→ Detection A
→ Map
→ Back
```

should return to the previous meaningful context.

Do not always redirect to Dashboard.

---

# 46. Loading States

Every API-driven section should have a loading state.

Examples:

```text
Loading surveys...
Loading detections...
Loading map...
Generating report...
Connecting...
```

Use skeletons/spinners appropriately.

---

# 47. Empty States

Examples:

```text
No detections found.
No reports generated yet.
No survey files uploaded.
No review items pending.
```

Provide useful next actions where appropriate.

---

# 48. Error States

Examples:

```text
Unable to load detections.
[Retry]
```

```text
Processing failed for this frame.
Survey processing can continue.
```

Do not expose stack traces.

---

# 49. Security — Basic Build Requirements

Even the first version must:

```text
Validate uploads
Validate API inputs
Use parameterized DB access
Protect DB credentials
Keep secrets out of frontend
Do not expose stack traces
```

The later company-grade plan can add the full authentication/RBAC/security hardening layer.

---

# 50. File Upload Safety

Backend must:

```text
Validate size
Validate supported format
Validate actual content where practical
Sanitize filenames
Use safe storage paths
Prevent path traversal
Reject unsupported files
Clean temporary files
```

Do not execute uploaded content.

---

# 51. Backend ↔ AI Integration

Recommended architecture:

```text
FastAPI
   ↓
AI service adapter
   ↓
Member 1 inference module/service
```

Do not hard-code YOLO logic into unrelated backend routes.

This makes it easy to replace:

```text
YOLO11-N
→ YOLO11-S
→ another detector
```

without rewriting the application.

---

# 52. AI Result Validation

Before saving Member 1's output:

Check:

```text
required identifiers
valid class
confidence range
bbox bounds
valid coordinates if supplied
valid dimensions
model version
```

If an invalid result arrives:

```text
Reject/flag result
log error
do not corrupt database
continue where safe
```

---

# 53. Report Generation

Report data should come from authoritative database records.

CSV fields may include:

```text
detection_id
survey_id
frame_id
classification
confidence
uncertainty
latitude
longitude
position_error_m
width
length
priority
review_status
model_version
timestamp
```

JSON should preserve structured information.

Do not generate reports directly from frontend state.

---

# 54. Report Consistency

A report should identify:

```text
survey
generation time
filter criteria
model version where relevant
data provenance where relevant
```

The exported report should match the records the user sees.

---

# 55. Basic Performance Requirements

Measure:

```text
API response time
database query time
map load time
dashboard update time
report generation time
AI request time
```

Use:

```text
pagination
database indexes
lazy loading
map clustering
targeted API requests
```

---

# 56. Avoid Full-Page Reloads

This is mandatory.

Wrong:

```text
Refresh map
→ reload app
→ dashboard reset
→ go Home
```

Correct:

```text
Refresh map
→ fetch map data
→ map updates
→ remain on same page
```

Same rule applies to:

- dashboard widgets
- detection list
- AI results
- reports
- processing status

---

# 57. Basic UX Design Direction

The application should visually feel like:

```text
Marine Operations Center
+
Sonar Analysis Tool
+
AI/GIS Platform
```

Use:

```text
dark ocean/navy background
subtle cyan/teal accents
high contrast
clear data hierarchy
professional cards/panels
```

Avoid excessive neon, game-like effects, or decorative UI.

The UI should make these answers obvious:

```text
WHAT?
Where?
Confidence?
Why?
What next?
```

---

# 58. Advanced UI Foundation

Even though this is the basic build, structure components so these can be added later:

```text
3D GIS
Sonar ↔ GIS split view
advanced evidence panel
animated processing pipeline
live system health
advanced review workspace
```

Do not build a completely different frontend later.

---

# 59. Dashboard Information Hierarchy

Priority order:

```text
1. Active hazards
2. Survey processing status
3. Map/location
4. Sonar evidence
5. Confidence
6. Review state
7. Analytics
8. System information
```

The visual design should reflect this order.

---

# 60. Frontend Component List

Create reusable components:

```text
AppShell
Sidebar
TopBar
StatusIndicator
KpiCard
SurveySelector
UploadDropzone
FileValidationCard
ProcessingProgress
DetectionTable
DetectionCard
DetectionDetail
SonarViewer
MapView
MapControls
FilterBar
ReviewPanel
ReportCard
ReportDownload
Chart
Toast
Modal
Drawer
EmptyState
ErrorState
LoadingSkeleton
```

Do not duplicate equivalent components.

---

# 61. Responsive Basic Design

Support:

```text
Desktop
Laptop
Tablet
Mobile
```

Desktop:

```text
sidebar + main workspace
```

Tablet:

```text
collapsible navigation
```

Mobile:

```text
stacked content
touch-friendly controls
```

Do not simply shrink the desktop layout.

---

# 62. Accessibility Basics

Implement:

```text
semantic controls
keyboard support
visible focus
accessible labels
reasonable contrast
non-hover-only actions
```

Do not rely on color alone for critical statuses.

---

# 63. Backend Testing

Test:

```text
survey creation
file upload
validation
job creation
job status
detection retrieval
map query
review
report generation
health endpoints
```

Use test database data.

---

# 64. Frontend Testing

Test:

```text
upload
loading states
error states
empty states
filters
detection selection
map interaction
report download
refresh/state restoration
responsive layout
```

---

# 65. Integration Testing

Critical integration:

```text
Frontend
→ FastAPI
→ AI Adapter
→ Member 1 AI
→ Database
→ Realtime
→ Frontend
```

Test with a real sample input and real Member 1 output.

---

# 66. Development Order

Follow this order:

```text
1. Repository setup
2. Database schema
3. FastAPI skeleton
4. API contracts
5. Survey APIs
6. File upload
7. Processing job model
8. AI adapter
9. Detection persistence
10. Detection APIs
11. Basic dashboard
12. Upload UI
13. Processing UI
14. Detection UI
15. GIS map
16. Reports
17. Review
18. Real-time updates
19. End-to-end testing
```

Do not spend days on visual polish before the backend/data flow works.

---

# 67. Temporary Mocking During Parallel Development

While Member 1 is still training the model, you may use **contract-valid test JSON** to build the application.

Rules:

```text
Clearly mark as test/development data.
Use the exact final JSON schema.
Do not present mock data as real AI output.
Replace mock adapter with Member 1 service during integration.
```

This allows both members to work in parallel.

---

# 68. Git / Branch Strategy for Two Members

Use:

```text
main
develop
member1-ai
member2-app
```

Member 1 works primarily on:

```text
member1-ai
```

Member 2 works primarily on:

```text
member2-app
```

Integrate through the agreed contracts.

Before merging:
- run tests
- check API compatibility
- verify sample end-to-end workflow

---

# 69. Handoff Required From Member 1

You must receive:

```text
model file
preprocessing code
inference code
metadata/geotagging code where assigned
output schema
sample input
sample output
error schema
model version
setup instructions
evaluation results
known limitations
```

Do not make assumptions about missing fields.

---

# 70. Handoff Required To Member 1

You provide:

```text
final AI input schema
final API request schema
supported metadata format
expected error schema
test sample inputs
integration feedback
```

Do not ask Member 1 to redesign his AI just because the frontend changed.

---

# 71. Basic Security / Production Upgrade Later

After the basic workflow is stable, the same application can receive:

```text
full authentication
RBAC
secure sessions
rate limiting
advanced upload security
audit logs
health monitoring
structured logs
correlation IDs
backup/restore
CI/CD
container hardening
disaster recovery
advanced state persistence
advanced 3D
```

These should extend the current architecture rather than replace it.

---

# 72. Definition of Done — Member 2

Your part is complete when:

```text
[ ] Frontend runs
[ ] Backend runs
[ ] Database runs
[ ] Survey can be created
[ ] SSS file can be uploaded
[ ] Metadata can be associated
[ ] Validation works
[ ] Processing job can start
[ ] Member 1 AI can be called
[ ] AI output is validated
[ ] Detections persist
[ ] Detection list works
[ ] Detection detail works
[ ] Sonar viewer works
[ ] GIS map works
[ ] Dashboard reflects actual data
[ ] Review flow works
[ ] JSON report works
[ ] CSV report works
[ ] Real-time updates work where implemented
[ ] Browser refresh preserves route/job state
[ ] Errors/loading/empty states work
[ ] Integration tests pass
```

---

# 73. Final Demo Flow Owned By Member 2

Your application must be able to demonstrate:

```text
Open Dashboard
↓
Create Survey
↓
Upload SSS data
↓
Upload metadata
↓
Validate
↓
Start Processing
↓
Show live processing
↓
Receive Member 1 detection
↓
Store result
↓
Display sonar detection
↓
Display GIS marker
↓
Open detection detail
↓
Show confidence/evidence
↓
Review uncertain result
↓
Generate report
↓
Download JSON/CSV
```

---

# 74. Final Integration Test

Use one real sample from Member 1.

Test:

```text
SSS sample
→ Member 1 AI
→ AI output JSON
→ FastAPI
→ PostgreSQL
→ GIS
→ Dashboard
→ Report
```

If this path works, the two-member project has a functional core.

---

# 75. Final Rule for Member 2

Your job is NOT:

> "Make a beautiful dashboard."

Your job is:

> **Build a reliable application that turns Member 1's sonar-AI output into a usable marine intelligence workflow.**

The critical chain is:

```text
USER
→ WEB APP
→ FASTAPI
→ AI SERVICE
→ DATABASE
→ REAL-TIME
→ GIS
→ SONAR VIEW
→ REPORT
```

Build the foundation so the later company-grade master plan can be added to this same codebase without rebuilding it.

