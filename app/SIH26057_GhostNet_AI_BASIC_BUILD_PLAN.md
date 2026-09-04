# SIH26057 — GhostNet-AI Basic Build Plan
## Problem-Statement-Focused Core Solution

> This is the **starting build plan**. It contains only the core system needed to solve the supplied SIH26057 problem statement and establish the complete working pipeline.
>
> Advanced company-grade features such as advanced security, RBAC, CI/CD, detailed observability, advanced 3D UX, extensive audit systems, advanced state persistence, sophisticated deployment hardening, etc. should be added later from the separate company-grade master plan.
>
> **Rule:** build this core foundation cleanly so advanced features can be added later without changing the core architecture.

---

# 1. Problem We Are Solving

Side-Scan Sonar (SSS) produces large amounts of acoustic imagery of the seafloor. Manual inspection is slow and error-prone, especially because natural rocks, sand ripples, ridges, acoustic shadows, noise, varying resolution, and vehicle-motion-related dropouts can resemble man-made debris.

The software must automatically:

```text
SSS image/log
→ preprocess
→ detect/segment suspicious objects
→ distinguish man-made objects from natural background
→ calculate confidence
→ read available sonar metadata
→ localize the detection
→ classify it
→ show it on a dashboard/map
→ generate JSON/CSV report
```

The system is software-only. Existing sonar systems are the data source.

---

# 2. Core SIH Requirements

The basic build must support:

1. Object detection or semantic segmentation.
2. Man-made classes supported by the actual training data, such as:
   - ghost nets / entangled debris
   - shipwrecks
   - pipes
   - cylinders
   - other man-made debris
3. Speckle/noise handling.
4. Different image resolutions.
5. Acoustic-shadow challenges.
6. Data dropouts related to sonar/vehicle motion.
7. 0–100% confidence output.
8. Sonar metadata parsing.
9. Latitude/longitude localization where metadata supports it.
10. Bounding dimensions where supportable.
11. Classification.
12. JSON/CSV anomaly reports.
13. Upload and visualization dashboard.
14. Efficient local inference with no heavy cloud dependency.

---

# 3. Basic Product Goal

Build a working application that lets an authorized operator:

```text
Upload SSS data
→ process it
→ see AI detections
→ inspect the sonar evidence
→ see detection location on GIS map
→ view confidence/classification
→ download JSON/CSV report
```

The basic product should prove the central value:

> **Automated identification and localization of likely anthropogenic marine debris in Side-Scan Sonar imagery.**

---

# 4. Basic Architecture

```text
                    WEB FRONTEND
               React / Next.js
                        │
                 REST API / SSE
                        │
                        ▼
                 FASTAPI BACKEND
                 │              │
                 │              │
                 ▼              ▼
            PostgreSQL        AI/CV
             + PostGIS       Pipeline
                 │              │
                 └──────┬───────┘
                        ▼
                  JSON / CSV
```

Basic AI flow:

```text
SSS image/log
      ↓
Data validation
      ↓
Frame extraction if needed
      ↓
Preprocessing
      ↓
Primary AI detection/segmentation
      ↓
Candidate detection
      ↓
Natural/artificial verification
      ↓
Confidence
      ↓
Metadata/geolocation
      ↓
Store result
      ↓
Dashboard + GIS
      ↓
JSON/CSV
```

---

# 5. Recommended Basic Technology Stack

## Frontend

- React or Next.js
- Leaflet or MapLibre for GIS
- Standard charting library where required

## Backend

- Python
- FastAPI

## AI/Computer Vision

- Python 3.11+
- PyTorch
- YOLO11-N for baseline
- YOLO11-S as main candidate
- YOLO segmentation or U-Net when suitable labels exist
- OpenCV
- NumPy
- Pandas
- scikit-learn

## Optional second-stage verification

- EfficientNet-B0

## Database

- PostgreSQL
- PostGIS where spatial queries are needed

## Local inference

- PyTorch initially
- ONNX later after the basic model is working

## Deployment

- Docker when the core application is stable

---

# 6. Dataset Plan — Basic

The model requires real Side-Scan Sonar data.

## Data source priority

### 1. Official SIH resources

Check first for:
- SSS imagery
- raw sonar logs
- ping files
- coordinates
- metadata
- annotations

### 2. Public SSS datasets

Look for:
- marine debris
- ghost nets
- shipwrecks
- pipes
- cylinders
- natural seafloor

### 3. Research datasets

Use compatible research datasets where licensing permits.

### 4. Own sonar data

Only if required and feasible. Hardware is not part of the basic software requirement.

---

# 7. Basic Dataset Classes

Only use classes that are genuinely supported by the available labels.

Possible classes:

```text
ghost_net
shipwreck
pipe
cylinder
other_debris
natural
unknown
```

Do not invent labels when the dataset does not contain them.

---

# 8. Basic Dataset Preparation

Create:

```text
data/
├── raw/
├── metadata/
├── annotations/
├── processed/
│   ├── train/
│   ├── val/
│   └── test/
└── provenance/
```

For each source, record:

```text
dataset_name
source
license
sonar_type
resolution
classes
annotation_type
metadata_available
gps_available
citation
```

---

# 9. Annotation

Use one normalized annotation format for training.

Preferred basic target:

```text
YOLO box
or
YOLO segmentation
```

Use segmentation only where reliable masks exist or can be created.

Before training, check:
- class correctness
- missing annotations
- bad boxes/masks
- duplicates
- class imbalance

---

# 10. Train/Validation/Test Split

Do NOT randomly split adjacent sonar frames.

Prefer survey/location-based separation:

```text
Survey A → Train
Survey B → Train
Survey C → Validation
Survey D → Test
```

The test set should represent an unseen survey/location where possible.

---

# 11. Basic AI Pipeline

## Stage 1 — Detection

Start with:

```text
YOLO11-N
```

Purpose:
- establish baseline
- validate data
- find dataset problems

Measure:

```text
Precision
Recall
F1
mAP
Inference time
```

Then evaluate:

```text
YOLO11-S
```

Use YOLO11-S as the main candidate only if it gives a useful accuracy/speed tradeoff.

---

# 12. Basic Sonar Preprocessing

The preprocessing pipeline should address the challenges in the problem statement.

Possible operations:

```text
Raw SSS
 ↓
Noise/speckle reduction
 ↓
Intensity normalization
 ↓
Contrast normalization
 ↓
Resolution normalization
 ↓
Tiling if required
 ↓
Invalid/dropout masking
 ↓
AI input
```

Do not assume every filter improves the model.

Compare validation performance before keeping a preprocessing method.

---

# 13. Acoustic Shadow

Where the data supports it, inspect:

- object size
- shadow size
- shadow length
- object/shadow relationship
- local contrast
- texture
- shape/context

Basic concept:

```text
Object
+
Acoustic shadow
+
Local background
→ additional evidence
```

Do not assume every target has a clean shadow.

---

# 14. Natural vs Artificial Verification

This is the key basic improvement over simple object detection.

The system should conceptually perform:

```text
AI sees suspicious region
        ↓
Candidate
        ↓
Is it likely man-made?
        ↓
YES → artificial object
NO  → natural/rejected
UNCERTAIN → review/unknown
```

The verification can use the second-stage EfficientNet-B0 model when the dataset supports it.

The final decision must be based on validated logic, not arbitrary percentage averaging.

---

# 15. Confidence

The application must show a confidence score from 0–100%.

Basic result:

```text
Class:
Ghost Net

Confidence:
93%

Status:
High Confidence
```

Do not call raw model probability "accuracy".

If calibration is implemented, show calibrated confidence separately.

---

# 16. Unknown / Uncertain Result

If the system cannot confidently classify a candidate:

```text
UNKNOWN / REVIEW

Confidence: 48%

Human verification required
```

Do not force every candidate into a known class.

---

# 17. Geotagging

Basic flow:

```text
Frame / Ping
    ↓
Metadata lookup
    ↓
Latitude / Longitude
    ↓
Detection record
```

If available:

```text
GPS
+
Heading
+
Range
+
Bearing
+
Depth
→ improved object location
```

If only frame-level coordinates are available, report frame-level localization.

Do not claim precision the source data cannot support.

---

# 18. Basic Detection Record

Store at minimum:

```text
detection_id
survey_id
frame_id
class
confidence
latitude
longitude
depth (if available)
width
length
source_file
model_version
review_status
timestamp
```

Add a position-error field when localization accuracy can be estimated.

---

# 19. Basic Database

Minimum tables:

```text
surveys
survey_files
sonar_frames
sonar_metadata
detections
processing_jobs
reports
```

Basic relationships:

```text
Survey
  ↓
Survey Files
  ↓
Sonar Frames
  ↓
Detections
```

Reports reference the relevant survey/detections.

Use PostGIS geometry for detections when spatial queries are needed.

---

# 20. Basic Backend APIs

The basic backend should provide capabilities equivalent to:

```text
POST /api/surveys
GET  /api/surveys
GET  /api/surveys/{id}

POST /api/surveys/{id}/files
GET  /api/surveys/{id}/files

POST /api/surveys/{id}/process
GET  /api/jobs/{id}

GET  /api/detections
GET  /api/detections/{id}

GET  /api/maps/surveys/{id}/detections

POST /api/reports
GET  /api/reports/{id}
```

Every endpoint must validate input and return clear errors.

---

# 21. Basic Processing Job

For a survey:

```text
Uploaded
→ Validating
→ Processing
→ Complete
```

If a frame fails:

```text
Frame failed
→ record error
→ continue other frames where safe
```

Do not stop the entire survey because one image is invalid.

---

# 22. Basic Frontend Pages

The initial application should contain these core screens.

## Page 1 — Dashboard

Show:

- current survey
- files/frames processed
- total candidates
- confirmed artificial detections
- detections by class
- basic map
- recent detections
- processing status

Purpose:

> Quickly understand the current survey.

---

## Page 2 — Upload Survey

Sections:

```text
Create/select survey
↓
Upload SSS image/log
↓
Upload/associate metadata
↓
Validation
↓
Start processing
```

Show:
- filename
- type
- size
- validation state
- metadata availability

---

## Page 3 — Processing

Show:

```text
Processing survey...

Frames processed: X / Y

Stage:
Preprocessing
Detection
Verification
Geotagging
Saving
```

Show actual progress when measurable.

---

## Page 4 — Detection Results

Show:

- sonar image
- bounding boxes
- segmentation mask where available
- class
- confidence
- status

Clicking a detection should open its details.

---

## Page 5 — Detection Detail

Show:

```text
Detection ID
Class
Confidence
Status
Latitude
Longitude
Position information
Dimensions
Timestamp
Source file
Model version
```

Actions:

```text
View on Map
View Sonar
Generate/Include in Report
```

---

## Page 6 — GIS Map

Show:

- survey area
- survey track when available
- detection markers
- class filters
- selected detection

Marker click:

```text
Map marker
→ Detection details
→ Corresponding sonar evidence
```

The map must use real coordinates when available.

---

## Page 7 — Reports

Show:

```text
Survey summary
Total detections
Classification counts
Location data
Dimensions
Confidence
```

Actions:

```text
Download CSV
Download JSON
```

---

# 23. Basic Sonar Viewer

The viewer should allow:

```text
Original
Processed
AI Overlay
```

Basic interactions:

- zoom
- pan
- select detection
- fit image

The AI overlay must correspond to actual model output.

---

# 24. Basic Dashboard ↔ GIS Interaction

At minimum:

```text
Click dashboard detection
→ center/select map marker

Click map marker
→ open detection detail
```

Filtering the detection class should affect the displayed detections.

---

# 25. Basic Real-Time Behavior

The problem asks for real-time visualization during processing.

For the basic implementation, use SSE or WebSocket where practical.

Example:

```text
Backend processes frame
↓
Detection generated
↓
Event sent to frontend
↓
Detection list updates
↓
Map marker appears
↓
KPI updates
```

The whole page does not need to reload.

---

# 26. Basic Refresh Rule

Even in the basic version:

```text
Refresh map
→ update map

Refresh detection list
→ update list

Refresh processing status
→ update status
```

Do not send the user to Home because a component was refreshed.

Browser refresh should return to the same route/page when the application can restore it normally.

---

# 27. Basic Loading / Empty / Error States

### Loading
```text
Loading detections...
```

### Empty
```text
No detections found.
```

### Error
```text
Unable to load detections.
[Retry]
```

### Processing
```text
Processing...
```

Do not leave blank panels.

---

# 28. Basic Report Schema

Example:

```json
{
  "detection_id": "D-00027",
  "survey_id": "SURVEY-001",
  "frame_id": "PING-18452",
  "classification": "ghost_net",
  "confidence": 0.93,
  "latitude": 20.123456,
  "longitude": 70.123456,
  "dimensions": {
    "width": 3.2,
    "length": 8.4
  },
  "review_status": "pending",
  "model_version": "v1.0"
}
```

This is an example structure. Actual output must contain real values.

---

# 29. Basic Evaluation

The model must be evaluated using real held-out data.

Report:

```text
Precision
Recall
F1
mAP
False positives
Inference time
```

Also compare baseline vs improvements.

Never invent metrics.

---

# 30. Basic PS Challenge Testing

Create test subsets where possible for:

```text
Speckle noise
Low resolution
Acoustic shadows
Motion/dropout
```

The purpose is to verify that the software addresses the exact challenges named in the PS.

---

# 31. Basic Offline Requirement

The core AI pipeline should not require a paid cloud AI API.

Target:

```text
Local machine
→ load model
→ preprocess
→ inference
→ results
```

Cloud services may be optional, not required for core inference.

---

# 32. Basic Security Boundary

For the initial build:

- Never hardcode secrets.
- Validate uploaded files.
- Validate API inputs.
- Do not expose database credentials to the frontend.
- Keep the backend authoritative for data changes.
- Do not expose raw server exceptions to users.

Advanced authentication/RBAC/security hardening can be added later from the company-grade plan.

---

# 33. Basic Development Order

Build exactly in this order:

```text
1. Verify data
2. Prepare dataset
3. Normalize annotations
4. Train/evaluate baseline
5. Build preprocessing
6. Build main AI model
7. Add natural/artificial verification
8. Add confidence/unknown
9. Add metadata/geotagging
10. Add database
11. Add FastAPI
12. Build upload page
13. Build processing page
14. Build detection viewer
15. Build GIS map
16. Build dashboard
17. Build reports
18. Connect real-time updates
19. Test complete end-to-end flow
```

Do not start with advanced visual effects before the AI/data pipeline works.

---

# 34. Basic End-to-End Acceptance Test

The basic system is working when this complete path succeeds:

```text
Upload real SSS data
        ↓
Validate
        ↓
Preprocess
        ↓
AI detects candidate
        ↓
Natural/artificial verification
        ↓
Confidence
        ↓
Metadata lookup
        ↓
Latitude/longitude when supported
        ↓
Database record
        ↓
Detection displayed on sonar viewer
        ↓
Marker displayed on GIS map
        ↓
Dashboard statistics update
        ↓
JSON/CSV generated
```

---

# 35. Basic Demo Flow

For the initial demo:

```text
1. Open dashboard
2. Create/select survey
3. Upload SSS image/log
4. Add metadata
5. Start processing
6. Show preprocessing
7. Show AI detection
8. Show natural/artificial decision
9. Show confidence
10. Show sonar evidence
11. Show GIS location
12. Show detection details
13. Show survey summary
14. Download JSON
15. Download CSV
```

---

# 36. Basic Success Criteria

The initial build should prove:

### Data
- Real SSS data loads.
- Supported metadata can be parsed.
- Actual labels/data are used.

### AI
- Detection/segmentation works.
- Natural background is handled.
- Confidence is shown.
- Uncertain cases can remain unknown.

### GIS
- Supported detection coordinates appear on the map.
- Marker/detail synchronization works.

### Backend
- Processing works through an API.
- Results persist in the database.

### Frontend
- Upload works.
- Processing works.
- Sonar results work.
- Map works.
- Dashboard works.
- Reports work.

### Reports
- JSON works.
- CSV works.

### Real-time
- Processing/detection updates can reach the dashboard without unnecessarily reloading the complete page.

---

# 37. What This Basic Plan Deliberately Does NOT Require Yet

Do not block the initial build on:

```text
Advanced 3D terrain
Advanced RBAC
Enterprise authentication architecture
Complex microservices
Advanced audit systems
Advanced CI/CD
Advanced disaster-recovery infrastructure
Sophisticated caching
Advanced model registry UI
Synthetic ghost-net generation
Advanced autoencoder unknown detection
Complex edge hardware
TensorRT optimization
Advanced animations
Complex mobile application
Chatbot
```

These belong to the later enhancement stage unless the available data/time makes them immediately useful.

---

# 38. Later Expansion Compatibility

The basic architecture must be designed so the later company-grade plan can add:

```text
Advanced security
RBAC
Detailed audit
Advanced observability
Model registry
Dataset registry
Hard-negative UI
Synthetic-data workflow
Autoencoder unknown detection
Calibration dashboard
Advanced human review
3D GIS
Advanced real-time resilience
State persistence
CI/CD
Backup/restore
Edge optimization
```

without rewriting the core:

```text
SSS
→ AI
→ Database
→ API
→ Dashboard
→ GIS
→ Reports
```

---

# 39. Golden Rule

> **First build a complete, working core solution for the actual SIH problem. Then enhance the same codebase with the separate company-grade master plan.**

Do not create a second unrelated application for the advanced features.

The basic version is the foundation.

The advanced version is an incremental expansion of the same foundation.
