# SIH26057 — GhostNet-AI Final A–Z Master Build Plan

> **Integrated master document:** original SIH26057 technical plan + identified missing requirements + production engineering + security + advanced UI/UX + real-time behavior + reliability + observability + final acceptance criteria.
>
> Generated: 2026-08-29

## How to use this document

This file is the **master source for implementation planning**. The original plan is preserved below. The added integrated sections close the gaps identified during review, especially around advanced UI/UX, 3D GIS, component-level refresh, security, authentication/authorization, observability, health monitoring, resilient real-time behavior, accessibility, state preservation, model/data versioning, and production acceptance.

**Important:** requirements that depend on real data remain conditional on what the actual dataset can support. Do not fabricate data, metrics, coordinates, or capabilities.


---

# SIH26057 — Full Build-Ready Plan + Review, Jugaad Tricks & Timeline

> PART A is your original plan (unchanged). PART B adds the gaps to close. PART C adds legit jugaad tricks. PART D is the 6-member timeline.

---

# PART A — ORIGINAL BUILD PLAN


## 1. Project Goal

Build an end-to-end **software-only AI system** for Side-Scan Sonar (SSS) imagery that:

**SSS image/log → preprocessing → AI detection/segmentation → natural-vs-artificial verification → confidence/uncertainty → geotagging → priority → dashboard → JSON/CSV report**

The system is designed around the exact SIH26057 requirements supplied by the team.

### Important scope

We do **not** need to manufacture:

- Sonar hardware
- AUV/UUV
- Boat
- Towed sonar

Existing sonar systems are the **data source**. Our project is the software intelligence layer.

---

# 2. Official PS Requirements We Must Satisfy

The system must support:

- Object detection / semantic segmentation of man-made objects.
- Examples mentioned in the PS: shipwrecks, pipes, cylinders and entangled debris nets.
- Speckle-noise handling.
- Varying pixel resolutions.
- Acoustic-shadow challenges.
- Data dropouts caused by heave, pitch and roll.
- Confidence score from 0–100%.
- Sonar metadata parsing.
- Latitude/longitude localization.
- Bounding dimensions.
- Classification.
- JSON/CSV anomaly reports.
- Upload and visualization dashboard.
- Efficient deployment, potentially on an edge device/onboard marine drone.
- No heavy cloud dependency for the core system.

---

# 3. Product Concept

Working name:

## GhostNet-AI

### Product message

> We do not merely detect sonar anomalies. We verify whether they are anthropogenic, estimate how trustworthy the detection is, localize the hazard, prioritize it and generate an actionable report.

---

# 4. Full System Architecture

```text
Side-Scan Sonar Image / Log
            │
            ▼
     Data Validation
            │
            ▼
    Sonar Preprocessing
            │
            ▼
     Primary Detector
       YOLO11-S
            │
            ▼
     Candidate Regions
            │
            ▼
 Natural / Artificial Verification
       EfficientNet-B0
            │
            ├───────────────┐
            ▼               ▼
 Acoustic Shadow      Image / Context
 Analysis             Features
            │               │
            └───────┬───────┘
                    ▼
          Confidence Calibration
                    │
             ┌──────┴──────┐
             ▼             ▼
          Known         Unknown
             │             │
             ▼             ▼
        Geotagging     Human Review
             │
             ▼
       Priority Engine
             │
             ▼
          Database
             │
      ┌──────┴────────┐
      ▼               ▼
  Dashboard       JSON / CSV
                      │
                      ▼
                 Optional PDF
```

---

# 5. Recommended Technology Stack

## AI / Computer Vision

- Python 3.11+
- PyTorch
- YOLO11-N for baseline
- YOLO11-S as main candidate
- YOLO segmentation or U-Net if segmentation labels are available
- EfficientNet-B0 for optional second-stage verification
- OpenCV
- NumPy
- Pandas
- scikit-learn

## Advanced

- SAM 2.1 for optional interactive/refined segmentation
- ONNX Runtime
- TensorRT if suitable NVIDIA hardware exists

## Backend

- FastAPI
- PostgreSQL
- PostGIS if spatial queries are needed

## Frontend

- React / Next.js
- Leaflet or MapLibre

## Deployment

- Docker
- Local/offline inference
- ONNX for portable inference

---

# 6. DATA ACQUISITION & COLLECTION PLAN

This is one of the most important parts of the project.

The AI cannot predict from nothing. It needs **Side-Scan Sonar imagery plus, where available, sonar metadata**.

## 6.1 Data Source Priority

Use sources in this order:

### Priority 1 — Official SIH-provided resources

First verify whether SIH26057 provides:

- Dataset
- Sample sonar imagery
- Raw sonar logs
- Ping files
- Coordinate files
- Metadata
- Annotation files
- API/data access
- Reference datasets

If SIH provides data, use it as the primary benchmark whenever licensing/usage terms permit.

### Priority 2 — Public SSS datasets

Search for publicly available Side-Scan Sonar datasets containing:

- Marine debris
- Ghost nets
- Shipwrecks
- Pipes
- Cylinders
- Other anthropogenic objects
- Natural seafloor backgrounds

For each dataset record:

```text
Dataset name
Source URL
Sonar modality
Image format
Resolution
Classes
Number of images
Bounding boxes?
Segmentation masks?
Metadata?
GPS?
License
Citation
```

### Priority 3 — Research datasets

Use datasets released with peer-reviewed marine robotics / sonar research where the license permits the intended use.

Search research papers for:

- Side-scan sonar debris datasets
- SSS marine litter datasets
- ghost-net sonar datasets
- shipwreck sonar datasets
- underwater object detection datasets
- sonar segmentation datasets

### Priority 4 — Own sonar collection

Do this only if required and feasible.

A real collection setup could use:

```text
Boat / AUV / UUV
       ↓
Side Scan Sonar
       ↓
Sonar log
       +
GPS / navigation
       ↓
Raw sonar + metadata
```

For the SIH prototype, **do not buy hardware unless the official requirements force it**.

---

# 7. What Data Do We Actually Need?

## A. Positive examples

Where available:

- Ghost nets
- Fishing gear
- Shipwrecks
- Pipes
- Cylinders
- Man-made debris
- Other anthropogenic objects

Use only classes actually supported by the dataset/labels.

## B. Hard negative examples

This is critical.

Collect:

- Rocks
- Sand ripples
- Natural ridges
- Natural seabed structures
- Acoustic shadows
- Noise
- Data-dropout regions

Why?

Because the central challenge is:

> **Natural seafloor topology can look like artificial debris in sonar.**

---

# 8. How We Collect Data From Public Sources

Create a data acquisition spreadsheet first.

Example:

| Dataset | SSS? | Debris? | Natural? | Boxes? | Masks? | GPS? | License |
|---|---|---|---|---|---|---|---|
| Dataset A | Yes | Yes | Yes | Yes | No | Yes | Verify |
| Dataset B | Yes | Yes | Yes | No | Yes | No | Verify |

Do not download blindly.

For every dataset:

1. Open the official source.
2. Read the license.
3. Download a small sample first.
4. Inspect image modality.
5. Inspect labels.
6. Inspect metadata.
7. Check whether it is genuinely Side-Scan Sonar.
8. Check whether classes match our target.
9. Record provenance.
10. Only then integrate it.

---

# 9. Data Provenance

Create:

```text
data_sources.csv
```

Example fields:

```text
dataset_id
dataset_name
source
paper
download_date
license
sonar_type
resolution
classes
annotation_type
metadata_available
gps_available
commercial_use_allowed
notes
```

Never lose track of where an image came from.

---

# 10. Raw Data Folder Structure

Recommended:

```text
data/
├── raw/
│   ├── sih/
│   ├── public/
│   └── research/
│
├── metadata/
│   ├── raw/
│   └── normalized/
│
├── annotations/
│   ├── raw/
│   └── normalized/
│
├── processed/
│   ├── train/
│   ├── val/
│   └── test/
│
├── hard_negatives/
│
├── provenance/
│
└── README.md
```

---

# 11. Data Format We Want

For each sonar frame:

```text
frame_id
survey_id
image_path
timestamp
latitude
longitude
heading
depth
range
ping_id
resolution
sonar_type
```

Example:

```csv
frame_id,survey_id,image_path,timestamp,latitude,longitude,heading,depth,range,ping_id
PING_001,SURVEY_A,images/PING_001.png,2026-01-10T10:30:15,20.123456,70.123456,72.5,18.2,50,1
```

Only populate fields that genuinely exist in the source.

---

# 12. How Raw Sonar Data Becomes Training Data

Conceptually:

```text
Raw sonar log
      │
      ▼
Decode sonar frames
      │
      ▼
Extract ping/frame
      │
      ├── Image
      │
      └── Metadata
              │
              ▼
        Normalize format
              │
              ▼
          Annotation
              │
              ▼
       Training dataset
```

If the source is already image + annotation files, skip raw-log decoding.

---

# 13. Annotation Strategy

We need consistent rules.

Possible labels:

```text
ghost_net
shipwreck
pipe
cylinder
other_debris
natural
unknown
```

But **only create classes that the actual dataset supports**.

If a dataset only labels "debris", do not invent ghost-net labels.

## Annotation types

### Bounding box

```text
x_min
y_min
x_max
y_max
class
```

### Segmentation

Pixel-level mask.

Use segmentation only when reliable masks exist or we have enough time to annotate them ourselves.

---

# 14. Annotation Quality Control

Before training:

1. Randomly sample annotations.
2. Check class correctness.
3. Check box/mask boundaries.
4. Check missing objects.
5. Check natural objects incorrectly labelled as debris.
6. Check duplicate annotations.
7. Check class imbalance.

Create:

```text
annotation_audit.csv
```

---

# 15. Train/Validation/Test Split

DO NOT randomly split consecutive sonar frames.

Bad:

```text
Frame 100 → train
Frame 101 → train
Frame 102 → test
Frame 103 → train
```

These may be nearly identical.

Better:

```text
Survey A → Train
Survey B → Train
Survey C → Validation
Survey D → Test
```

The test set should represent an unseen survey/location when possible.

This prevents artificially inflated F1.

---

# 16. How Much Data?

There is no universal number that guarantees 80% F1.

Start with what we can legally obtain.

Recommended progression:

### MVP

A few hundred carefully labelled examples.

### Stronger model

Preferably 1,000+ labelled frames/objects if the data supports it.

### Best

Multiple surveys/environments with hard negatives.

**Quality and diversity are more important than simply counting images.**

---

# 17. Baseline AI

Start simple.

## Model 1

### YOLO11-N

Purpose:

- establish baseline
- check dataset
- find errors quickly

Measure:

- Precision
- Recall
- F1
- mAP
- inference time

Then move to:

## Model 2

### YOLO11-S

Use this as the main candidate if it gives a useful accuracy/speed tradeoff.

---

# 18. Main AI Pipeline

```text
SSS image
   ↓
Preprocessing
   ↓
YOLO11-S
   ↓
Candidate object
   ↓
Crop
   ↓
EfficientNet-B0
   ↓
Natural / Artificial
   ↓
Acoustic-shadow/context features
   ↓
Confidence calibration
   ↓
Final decision
```

---

# 19. Natural-vs-Artificial Verification

This is the main differentiation.

Stage 1:

> "Something suspicious is here."

Stage 2:

> "Is it actually man-made?"

Example:

```text
YOLO:
Candidate confidence = 91%

Verification:
Artificial probability = 94%

Shadow/context:
Strong consistency

Final:
Confirmed artificial anomaly
```

Do not just average arbitrary percentages. Calibrate and validate the final scoring method.

---

# 20. Acoustic-Shadow Analysis

Where the SSS data supports it:

Extract:

- object size
- shadow size
- shadow length
- object-to-shadow relationship
- local contrast
- texture
- shape/context

Concept:

```text
Object
  +
Acoustic shadow
  +
Local background
       ↓
Evidence
```

This helps address the PS requirement around acoustic shadows.

Do not assume every object has a clean shadow.

---

# 21. Hard-Negative Mining

One of our strongest techniques.

Loop:

```text
Train
 ↓
Run validation
 ↓
Collect false positives
 ↓
Find why they are wrong
 ↓
Add difficult natural examples
 ↓
Retrain
 ↓
Measure improvement
```

Examples:

- Rock mistaken for pipe
- Natural ridge mistaken for wreck
- Shadow mistaken for net
- Noise mistaken for object

---

# 22. Sonar Preprocessing

Build configurable experiments.

Potential methods:

- Speckle/noise reduction
- Intensity normalization
- Contrast normalization
- CLAHE where appropriate
- Resolution normalization
- Tiling
- Invalid/dropout masking

Do not assume every filter helps.

Measure:

```text
Baseline F1
+
Preprocessing F1
```

Keep only improvements.

---

# 23. Heave, Pitch and Roll

These motion effects can distort sonar imagery.

Our software strategy:

1. Detect image-quality problems.
2. Use available navigation/metadata when possible.
3. Use realistic augmentation to make the model robust.
4. Mask invalid regions.
5. Do not invent motion correction when required sensor data is unavailable.

If actual motion compensation data is provided, build a correction module.

---

# 24. Confidence + Uncertainty

Do not simply display raw model probability as "accuracy".

Use calibrated confidence.

Example UI:

```text
Confidence: 92%
Data Quality: High
Uncertainty: Low
```

For uncertain candidates:

```text
UNKNOWN ANOMALY
Human verification required
```

This is safer and more realistic.

---

# 25. Target Metrics

There is no official requirement in the supplied PS saying:

> "F1 must be X%."

Our internal target:

### Minimum target

**80% F1**

### Strong

**85%+ F1**

### Excellent

**90%+ F1**

Also report:

- Precision
- Recall
- F1
- mAP
- false positives per image
- inference latency
- class-wise performance

Never invent metrics.

---

# 26. How to Reach 80%+ F1

Order of improvement:

1. Correct labels.
2. Remove train/test leakage.
3. Build strong baseline.
4. Inspect false positives.
5. Add hard negatives.
6. Use realistic sonar augmentation.
7. Tune detection threshold using validation data.
8. Add second-stage classifier if it improves F1.
9. Add shadow/context features if they improve held-out performance.
10. Calibrate confidence.
11. Test on untouched data.

---

# 27. Geotagging

Use deterministic code.

```text
SSS frame
   ↓
Frame/Ping ID
   ↓
Metadata lookup
   ↓
Latitude/Longitude
   ↓
Detection record
```

If the sonar geometry supports more precise object location:

```text
Vessel/Sonar GPS
+
Heading
+
Range
+
Bearing
+
Depth
      ↓
Object location
```

If the metadata only supports frame-level GPS, report frame-level localization honestly.

Do not claim "exact object coordinates" when the source data cannot support that precision.

---

# 28. Database

## Detection

```text
id
survey_id
frame_id
timestamp
class
confidence
uncertainty
latitude
longitude
depth
width
length
area
priority
model_version
review_status
evidence_summary
source_file
```

## Survey

```text
id
name
source
sonar_type
metadata_file
processing_status
created_at
```

---

# 29. Dashboard

## Page 1 — Upload

```text
Upload SSS image/log
Upload metadata
       ↓
Analyze
```

## Page 2 — Detection

Show:

- original sonar
- boxes
- masks
- class
- confidence
- uncertainty
- evidence

## Page 3 — Map

Markers:

- High priority
- Medium
- Low
- Unknown

## Page 4 — Reports

Buttons:

- Download CSV
- Download JSON
- Optional PDF

---

# 30. Survey Summary

Make the dashboard show:

```text
1,284 frames processed

37 candidates

21 natural formations rejected

12 confirmed artificial anomalies

4 high-priority hazards

8 human-review cases
```

Numbers above are examples only. The live dashboard must use actual results.

This is much more impressive than only showing bounding boxes.

---

# 31. Priority Engine

Possible inputs:

- calibrated confidence
- class
- estimated dimensions
- persistence across frames
- available location/context
- data quality

Output:

```text
Critical
High
Medium
Review
```

Always show the reason.

---

# 32. Human-in-the-Loop

For uncertain detections:

```text
Accept Artificial
Reject Natural
Unknown
```

Store feedback.

Later:

```text
Human feedback
      ↓
Verified hard examples
      ↓
Training dataset
      ↓
Next model version
```

Do not claim automatic online retraining unless it is genuinely implemented.

---

# 33. Edge AI

After accuracy is stable:

```text
PyTorch model
      ↓
ONNX
      ↓
ONNX Runtime
      ↓
CPU / Edge device
```

Optional:

```text
ONNX
 ↓
TensorRT
 ↓
NVIDIA edge device
```

Measure:

- model size
- latency
- memory
- images/sec

The goal is to support the PS's edge-deployment direction.

---

# 34. Free / Low-Cost Strategy

Core system:

- PyTorch
- OpenCV
- YOLO
- EfficientNet
- FastAPI
- PostgreSQL
- React
- Leaflet/MapLibre
- ONNX

No paid AI API should be required.

Use public data only when licensing permits the intended use.

---

# 35. Demo Reliability / “Jugaad” Features

These are legitimate reliability features, not fake results.

## Offline Mode

Core AI works without internet.

## Pre-validated Demo Samples

Keep real previously processed examples for predictable demonstration.

Clearly label them as preloaded/demo data.

## Batch Survey Demo

Show many frames, not just one.

## Error Recovery

Failed frames are logged instead of crashing the entire survey.

## Unknown Mode

Low-confidence cases go to human review.

## Cached Results

Useful for stable demo performance.

---

# 36. Unique / Winning Features

Do not compete by saying:

> "We use YOLO."

Other teams can do that.

Our differentiation:

### 1. Natural-vs-Artificial Verification

### 2. Acoustic-Shadow / Context Evidence

### 3. Calibrated Confidence + Uncertainty

### 4. Hard-Negative Learning

### 5. Unknown-Anomaly Handling

### 6. Human-in-the-Loop

### 7. Geotagged Actionable Reports

### 8. Edge/Offline Inference

---

# 37. What Not to Build First

Do NOT begin with:

- fancy dashboard
- chatbot
- mobile app
- login system
- paid API integration
- huge model
- complicated microservices

First prove:

> **SSS input → reliable AI output**

---

# 38. Development Phases

## Phase 0 — Requirements/Data

- Verify official SIH resources.
- Verify dataset licenses.
- Inspect actual SSS modality.
- Identify available labels.
- Identify metadata.
- Build data inventory.

## Phase 1 — Dataset

- Download/obtain data.
- Normalize.
- Annotate/audit.
- Build leakage-safe split.

## Phase 2 — Baseline

- YOLO11-N.
- Measure F1.
- Error analysis.

## Phase 3 — Main AI

- YOLO11-S.
- Compare performance/speed.

## Phase 4 — False Positive Reduction

- Hard-negative mining.
- Natural/artificial classifier.
- Shadow/context experiments.

## Phase 5 — Reliability

- Confidence calibration.
- Unknown detection.
- Human review.

## Phase 6 — Geospatial

- Metadata parser.
- Geotagging.
- PostGIS.

## Phase 7 — Product

- FastAPI.
- Database.
- Dashboard.
- JSON/CSV.

## Phase 8 — Edge

- ONNX.
- Performance optimization.

## Phase 9 — Final

- Untouched test set.
- Freeze model.
- Prepare demo.
- Prepare presentation.

---

# 39. Team Roles

## ML Lead

- Dataset
- Training
- Evaluation
- Hard-negative mining

## Sonar/CV Lead

- Preprocessing
- Acoustic-shadow analysis
- Image-quality analysis
- Geospatial interpretation

## Backend Lead

- FastAPI
- Database
- Processing pipeline
- Reports

## Frontend Lead

- Dashboard
- Map
- Upload
- Review interface

## QA/DevOps

- Docker
- Offline demo
- Integration
- Testing
- Performance

For 3–4 people, combine roles.

---

# 40. Minimum Viable Product

MVP is complete when:

```text
SSS input
   ↓
AI detection
   ↓
Class + confidence
   ↓
Metadata parsing
   ↓
Location
   ↓
Database
   ↓
Dashboard
   ↓
JSON/CSV
```

Only after this works should advanced features be added.

---

# 41. Final Demo Flow

1. Upload an SSS survey/log.
2. Upload metadata.
3. Run processing.
4. Show sonar preprocessing.
5. Show detections.
6. Show natural formations rejected.
7. Open a confirmed debris result.
8. Show confidence and evidence.
9. Show geotag on map.
10. Show priority.
11. Download JSON/CSV.
12. Demonstrate an uncertain/unknown case.
13. Show human-review workflow.
14. Show baseline vs improved F1.
15. Demonstrate offline operation if possible.

---

# 42. Example Report

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
  "priority": "high",
  "review_status": "pending",
  "model_version": "v1.0"
}
```

Example only. Real output must reflect actual data.

---

# 43. Judge Questions and Answers

### Why not only YOLO?

Because the key challenge is distinguishing artificial debris from natural sonar features. We add verification and sonar/context evidence.

### How do you measure accuracy?

Using a held-out survey/location-level test set with Precision, Recall, F1, mAP and false-positive analysis.

### How do you avoid data leakage?

We split by survey/location rather than adjacent sonar frames.

### What happens when AI is uncertain?

It produces an Unknown/Human Review result instead of forcing a classification.

### How do you geotag?

We map frame/ping IDs to sonar metadata using deterministic code.

### Can it work without internet?

Yes. The core inference pipeline is local; cloud APIs are optional.

### What is your main innovation?

Natural-vs-artificial verification, hard-negative learning, uncertainty handling and sonar-specific evidence such as acoustic-shadow/context analysis.

---

# 44. Research/Search Strategy

Do not search only:

> "Best YOLO model for sonar."

Search for weaknesses:

### Acoustic shadows

```text
side scan sonar acoustic shadow geometry distinguish man-made objects from rocks machine learning
```

### False positives

```text
side scan sonar false positives natural seabed rocks debris hard negative mining deep learning
```

### Domain shift

```text
side scan sonar marine debris detection domain adaptation different sonar sensors environments
```

### Uncertainty

```text
uncertainty estimation object detection side scan sonar false positive human in the loop
```

### Augmentation

```text
side scan sonar data augmentation speckle noise acoustic shadow heave pitch roll deep learning
```

### Edge

```text
side scan sonar object detection edge deployment AUV real time YOLO ONNX TensorRT
```

### Unknown objects

```text
open set recognition side scan sonar underwater debris unknown object detection
```

The objective is to find **failure modes that other teams ignore**, not simply copy the most popular model.

---

# 45. Differentiation Strategy

A basic team might build:

```text
SSS → YOLO → bounding boxes → map
```

Our target:

```text
SSS
 ↓
Quality assessment
 ↓
Detection
 ↓
Natural/Artificial verification
 ↓
Acoustic-shadow/context evidence
 ↓
Confidence calibration
 ↓
Unknown detection
 ↓
Human review
 ↓
Geotagging
 ↓
Priority
 ↓
Edge inference
 ↓
Actionable report
```

The key pitch:

> **"We don't just detect anomalies; we determine whether the anomaly is actually man-made and whether the AI should be trusted."**

---

# 46. Accuracy Improvement Experiment

Never invent these numbers. Use real measurements.

Example experiment structure:

```text
Baseline YOLO
       ↓
F1 = X
       ↓
+ Hard Negatives
       ↓
F1 = Y
       ↓
+ Verification
       ↓
F1 = Z
       ↓
+ Shadow/Context
       ↓
Final F1 = W
```

Also compare:

- false positives
- recall
- precision
- inference time

This creates evidence for our innovation.

---

# 47. Master Prompt for an AI Coding Agent

Copy this into your coding AI:

> You are the lead software/ML engineer for SIH26057. Build a production-quality, modular, software-only Side-Scan Sonar marine debris detection platform.
>
> Do not invent datasets, labels, metadata fields, SIH requirements, or performance metrics. First inspect the repository and create a development plan.
>
> The system must ingest Side-Scan Sonar imagery/logs plus available metadata, validate and preprocess the data, run a lightweight object detection/segmentation model, output class and confidence, map detections to supported metadata coordinates, store results, and generate JSON/CSV reports.
>
> After the MVP works, implement a natural-vs-artificial verification layer, hard-negative mining workflow, calibrated confidence and uncertainty handling, Unknown/Human Review flow, acoustic-shadow/context features where the data supports them, priority scoring, dashboard, and optional ONNX edge inference.
>
> Keep the core system local/offline. Do not make paid APIs or cloud LLMs a dependency.
>
> Use clean modular interfaces so the detector can be replaced.
>
> Add automated tests for:
> - data parsing
> - metadata parsing
> - geotagging
> - report generation
> - API endpoints
> - preprocessing
>
> Add an evaluation script that reports:
> - Precision
> - Recall
> - F1
> - mAP
> - false positives
> - inference time
>
> Use a leakage-safe held-out test set split by survey/location where possible.
>
> Never fabricate metrics.
>
> Before implementing advanced features, create a baseline and measure whether the feature improves validation performance.
>
> Prefer the simplest solution that improves measured performance.
>
> Document:
> - setup
> - data format
> - data acquisition
> - annotation
> - training
> - evaluation
> - inference
> - API
> - dashboard
> - deployment
> - offline demo
>
> First task: inspect available data/resources and produce a data inventory. Do not start building the full UI until the first real SSS data can be loaded and a baseline inference pipeline works.

---

# 48. First Tasks — Start Here

Before building the complete application:

1. Verify SIH26057 official resources/data.
2. Find compatible SSS datasets.
3. Verify licensing.
4. Inspect at least 50–100 representative samples if available.
5. Identify actual classes.
6. Identify annotation format.
7. Identify metadata format.
8. Determine whether GPS exists.
9. Determine whether raw ping logs are available.
10. Create the normalized data schema.
11. Build a small reproducible dataset subset.
12. Run YOLO11-N baseline.
13. Record the first real metrics.
14. Start error analysis.

## Golden rule

**Do not spend days building the dashboard before proving that the AI can work on the actual SSS data.**

The project should be driven by measured experiments, not assumptions.


---
---

# PART B — GAPS TO CLOSE (Added After Review)

> The plan above is strong on architecture and process. These are the seven holes a judge will still find. They are ordered by priority. The first two block everything else — do them first.

## B1. Lock ONE annotation format (do this before anything else)

The datasets arrive in different formats: SCTD is Pascal VOC XML, AI4Shipwrecks is segmentation masks, KLSG and Marine-PULSE are classification-only.

Decision: **standardize everything to YOLO-seg (polygon) format.**

Conversion map:

```text
SCTD (VOC XML)          → YOLO boxes (use voc2coco → coco2yolo)
AI4Shipwrecks (masks)   → YOLO-seg polygons (mask → polygon)
Marine-PULSE (class)    → hand-draw boxes for pipe/cylinder
KLSG (class)            → hand-draw boxes for wreck/plane; seafloor = negatives
Synthetic ghost nets    → generated already in YOLO-seg
```

One person owns conversion. Until this is finished, the ML lead cannot train and the whole team is blocked. This is the true critical path.

## B2. Specify the ghost-net synthetic pipeline (this is your novelty)

The PS names "entangled debris nets" but **no public SSS dataset contains them.** This is not a weakness if you handle it openly — it is your differentiation.

Concrete plan:

- Method: **diffusion-based generation** (stronger and more impressive to judges than CycleGAN). Fallback: copy-paste augmentation (see J2).
- Rule: synthetic images stay **≤ 50–60%** of the training mix (beyond this, accuracy drops — proven in the literature).
- Required experiment (this becomes your winning slide):

```text
Train WITHOUT synthetic  → F1 = A
Train WITH synthetic      → F1 = B
Show B > A on held-out real data
```

Never claim the synthetic pipeline "works" without this before/after number.

## B3. Pick one confidence-calibration method

The PS demands a real 0–100% score. Raw model probability is NOT calibrated.

Use **temperature scaling** (simple, standard, defensible). Show a reliability diagram before/after. When a judge asks "is your 92% a real probability?", you have a real answer.

## B4. Report lat/long + error radius, not "exact location"

The PS says "exact location," but side-scan sonar physically cannot give exact object coordinates (layback, heading, slant-range and flat-seabed errors stack to several meters).

Change the report schema to include an error radius:

```json
"latitude": 20.123456,
"longitude": 70.123456,
"position_error_m": 4.5,
"localization": "frame-level"
```

Stating this honestly scores points. Claiming false precision loses them the moment a judge asks.

## B5. Build a test slice per PS challenge word

The PS lists specific failure conditions. Build a mini test set for each and show you survive it:

```text
Challenge slice        What it proves
-----------------      --------------------------------
Speckle-noise set   →  denoising module works
Low-resolution set  →  multi-resolution robustness
Acoustic-shadow set →  shadow handling, not confusion
Motion-dropout set  →  invalid-region masking works
```

This answers the PS directly, instead of one generic mAP number every other team will show.

## B6. Wire the "unknown / human-review" path into the LIVE demo

Judges may hand you unseen data at the finale. Your fallback (anomaly / unknown → human review) already exists in the plan but must be **visible on screen** during the demo, not buried in a paragraph. Show a low-confidence detection routing to the review queue in real time.

## B7. Map the 6 members to a week-by-week timeline

Roles exist; a schedule does not. See PART D.

---

# PART C — JUGAAD FEATURES & TRICKS (Legit, Not Fake)

> These are clever, low-cost engineering moves that solve the real problems in this PS. Every one is honest — none fabricates results. They exist to make a small-data, no-hardware hackathon project look and behave like a robust product.

## The core problem → jugaad tricks table

```text
PROBLEM                          JUGAAD / TRICK TO SOLVE IT
-------------------------------  --------------------------------------------------
No ghost-net data                J2 copy-paste synthesis + J3 anomaly detector
Small dataset, overfitting       J1 KLSG seafloor = infinite hard negatives
                                 J4 heavy sonar-style augmentation
False positives from rocks       J5 classical pre-filter before ML (free, fast)
"Exact dimensions" required      J6 shadow-length → object height (classical, free)
No GPS metadata in some data     J7 synthetic XTF-style ping headers
No Jetson / edge hardware        J8 ONNX-CPU latency demo = "edge proof"
Free uncertainty score           J9 test-time augmentation ensemble
Flaky finale Wi-Fi / crashes     J10 offline mode + cached golden-path demo
```

## J1. Turn KLSG seafloor into an infinite hard-negative bank

KLSG has **578 pure seafloor images.** These are free "natural background" — rocks, ripples, ridges. Mine your own false positives during training and keep feeding these in. This directly attacks the PS's central line: "separates natural seafloor topology from artificial anomalies." Costs nothing, biggest single accuracy lever.

## J2. Copy-paste augmentation for the classes you lack

Instead of only diffusion, cut real objects (a wreck, a pipe, a cylinder) out of KLSG/Marine-PULSE and paste them onto real natural-seabed crops at random scale/rotation, then blend with sonar speckle. Instant labeled positives on realistic backgrounds. For ghost nets: paste procedural net/mesh textures with speckle. Cheap, fast, and it works.

## J3. Anomaly detector as a safety net for unseen debris

Train a small **autoencoder on natural seabed only.** Anything it reconstructs badly is "not natural" = candidate anomaly. This catches debris types you have zero labels for (including ghost nets) without training on them. It becomes your "Unknown Anomaly" pathway and is a strong novelty talking point.

## J4. Sonar-specific augmentation, not generic augmentation

Generic flips aren't enough. Simulate the actual PS challenges:

```text
+ speckle noise injection      (mimics real sonar grain)
+ random shadow elongation     (mimics acoustic shadows)
+ column dropouts / blackout   (mimics heave/pitch/roll dropouts)
+ resolution up/down-sampling  (mimics varying pixel resolution)
+ intensity/contrast jitter    (mimics range/gain variation)
```

Now your model has "seen" every failure mode in the PS, from a tiny real dataset.

## J5. Cheap classical pre-filter before the ML model

Before YOLO even runs, drop obvious non-objects with simple rules: minimum blob size, aspect-ratio limits, intensity threshold. Removes a chunk of rock-cluster false positives for near-zero compute — helps precision and speeds up the pipeline on edge.

## J6. Shadow-length → object height (free "dimensions" output)

The PS wants bounding dimensions. Use classic sonar geometry: object height ≈ (shadow length × sonar altitude) / slant range. You get a real height/size estimate from the acoustic shadow with zero ML. Judges love this because it shows genuine sonar understanding, not just "we ran YOLO."

## J7. Synthetic XTF-style ping headers when metadata is missing

Some datasets have no GPS. Don't fake results — instead generate **realistic ping/coordinate headers in the correct XTF-like schema** so your geotagging engine is provably correct end-to-end. Clearly label these as simulated navigation. Your parser then works on real XTF the moment real data appears.

## J8. "Edge proof" without buying a Jetson

No hardware budget? Export to **ONNX and run on CPU with a thread cap**, then report latency / FPS / model size / memory. This honestly demonstrates the edge/offline requirement of the PS. If you can borrow a Jetson later, add TensorRT INT8 numbers — but CPU-ONNX alone satisfies "no heavy cloud dependency."

## J9. Free uncertainty via test-time augmentation

Run the same image through the model 3–5 times with small augmentations; spread of predictions = uncertainty, with no extra training. Feeds directly into your confidence + human-review logic. Cheap reliability story.

## J10. Bulletproof demo kit (wins finales)

```text
✓ Offline mode        — core AI runs with Wi-Fi unplugged
✓ Golden-path samples — pre-processed real examples that always work
✓ Recorded backup     — screen-recording of a full clean run
✓ Fixed random seed   — reproducible detections every time
✓ Error recovery      — one bad frame is logged, survey continues (no crash)
✓ Batch survey view   — process many frames, show the summary dashboard
```

The demo — not the mAP — is what actually wins SIH. Prepare it like a product launch.

---

# PART D — 6-MEMBER TIMELINE

> Front-load everyone onto data in weeks 1–2. The classic SIH loss is three people polishing a UI while the AI has no data.

## Roles (one owner each)

```text
1. ML / Detection Lead       YOLO11-seg, training, split, evaluation
2. Data & Annotation Lead    datasets, licensing, format conversion, synthetic
3. Sonar CV / Preprocessing  denoise, CLAHE, slant-range, shadow, verifier
4. Backend & Geotagging      FastAPI, DB, XTF parse, geotag, JSON/CSV, priority
5. Frontend Lead             dashboard, map, upload, review UI
6. Integration / DevOps      Docker, ONNX edge, integration, testing, DEMO
```

For weeks 1–2, roles 4/5/6 aren't blocked yet → they help annotate.

## Week-by-week

```text
Week 1  ─ ALL: verify sih.gov.in data, pull datasets, licenses, inventory
          Lock JSON schema + model-output format (two contracts)
Week 2  ─ ALL: annotation → YOLO-seg (B1). Data lead: start synthetic (B2)
          ML lead: YOLO11-n baseline on whatever is ready
Week 3  ─ ML: YOLO11-s main model, first real metrics
          CV: preprocessing + shadow features. Backend: XTF parser + geotag
Week 4  ─ CV: EfficientNet verifier + hard negatives (J1). Backend: DB + reports
          Frontend: dashboard skeleton on real detections
Week 5  ─ ML: calibration (B3) + anomaly detector (J3)
          Test slices per challenge (B5). Frontend: map + review UI (B6)
Week 6  ─ Integration: ONNX edge (J8), Docker, offline mode
          Freeze model on untouched test set. Demo kit (J10) + deck
```

## Two contracts to lock on day one

```text
Backend ⇄ Frontend : the JSON report schema
ML ⇄ Backend       : the model-output format
```

Agree these in week 1 and all six people build in parallel without blocking each other.


---


# PART E — FINAL INTEGRATED PRODUCT / PRODUCTION / UI-UX SPECIFICATION

> This section adds the requirements that were not explicit or sufficiently detailed in the original plan. The original plan remains the technical source of truth for the SIH26057 AI/sonar/data workflow. This section closes the product, frontend, security, reliability, real-time, observability, accessibility, and production-engineering gaps.

## E1. Final System Scope

The final system is a **software-only, production-style Side-Scan Sonar marine debris intelligence platform**.

It must connect, where supported by the actual data:

```text
SSS Image / Raw Sonar Log
        ↓
Data Validation
        ↓
Sonar Decode / Frame Extraction
        ↓
Quality Assessment
        ↓
Sonar Preprocessing
        ↓
Primary Detection / Segmentation
        ↓
Natural-vs-Artificial Verification
        ↓
Acoustic-Shadow / Context Evidence
        ↓
Confidence Calibration
        ↓
Uncertainty / Unknown Handling
        ↓
Geotagging + Position Error
        ↓
Persistence / Duplicate Handling
        ↓
Priority Engine
        ↓
Database / PostGIS
        ↓
Real-Time Dashboard
        ↓
GIS + Sonar Investigation Workspace
        ↓
Human Review
        ↓
JSON / CSV / Optional PDF
        ↓
Offline / Edge Deployment
```

### Important scope rule

The core product is **software intelligence**. Do not add physical sonar, AUV, UUV, boat, or other hardware as a mandatory dependency unless the official competition requirements explicitly require it.

---

# E2. Non-Negotiable Engineering Principles

1. Do not build a static or fake demo.
2. Do not claim an AI capability is real until it is connected to an actual model or explicitly labeled as development/simulation.
3. Do not fabricate datasets, labels, GPS, confidence, accuracy, latency, or system status.
4. Prefer deterministic and reproducible processing wherever practical.
5. Keep the core inference path local/offline where possible.
6. Build modular interfaces so models and data sources can be replaced.
7. Every feature must handle success, loading, empty, error, and recovery states where applicable.
8. A failed frame must not unnecessarily crash the entire survey.
9. Never make a full-page reload the default response to a local user action.
10. Preserve user context during local updates.
11. Security is a system requirement, not a final polish step.
12. UI polish must never hide scientific or technical limitations.

---

# E3. Recommended Reference Architecture

```text
                  ┌───────────────────────────┐
                  │        WEB CLIENT         │
                  │ React / Next.js            │
                  │ Dashboard + GIS + Sonar   │
                  └─────────────┬─────────────┘
                                │
                      REST / WebSocket / SSE
                                │
                  ┌─────────────▼─────────────┐
                  │        BACKEND API        │
                  │ FastAPI                   │
                  │ Auth / Validation / Jobs  │
                  └──────┬─────────┬──────────┘
                         │         │
              ┌──────────▼───┐   ┌─▼────────────────┐
              │ PostgreSQL   │   │ AI/CV SERVICES   │
              │ + PostGIS    │   │ Preprocess       │
              │ Surveys      │   │ Detector         │
              │ Detections   │   │ Verifier         │
              │ Metadata     │   │ Calibration      │
              │ Review       │   │ Anomaly detector │
              └──────┬───────┘   └────────┬─────────┘
                     │                    │
                     └─────────┬──────────┘
                               ▼
                     ┌────────────────────┐
                     │ Background Jobs    │
                     │ Processing / Report│
                     │ Training / Import  │
                     └─────────┬──────────┘
                               │
                               ▼
                     ┌────────────────────┐
                     │ Local / Edge Path  │
                     │ ONNX Runtime       │
                     │ Optional TensorRT  │
                     └────────────────────┘
```

Keep this architecture modular. Do not introduce microservices merely for appearance.

---

# E4. Final Frontend Information Architecture

Recommended application areas:

```text
1. Login / Authentication
2. Mission Dashboard
3. Survey Upload
4. Live Processing
5. Sonar Investigation
6. GIS / 3D Survey Map
7. Detections
8. Human Review Queue
9. Reports
10. Analytics
11. Model & Evaluation
12. System Health
13. Alerts
14. Audit / Activity
15. Settings
```

Do not create a separate page when a focused panel, drawer, or modal would be more usable.

---

# E5. Advanced UI/UX Design Direction

Visual identity:

**Marine Operations Center + Sonar Analysis Lab + AI/GIS Command Center**

Use:

- Deep navy/oceanic background
- Dark panels
- Restrained cyan/teal accents
- High readability
- Clear status colors
- Subtle glass/depth treatment
- Sonar-inspired visualization
- Professional scientific presentation

Avoid:

- excessive neon
- game-like interfaces
- decorative 3D that carries no information
- excessive motion
- giant cards for trivial values
- fake live indicators

The UI must remain usable in a stressful investigation workflow.

---

# E6. 3D / GIS Visual Strategy

3D is allowed and encouraged where it provides functional value.

The main map experience may include:

- survey track
- sonar coverage
- detection points
- detection clusters
- selected detection
- depth where available
- geographic context
- survey bounds
- relevant layers

3D should not invent bathymetry, roads, routes, objects, or coordinates.

If the available data is not 3D:

- show a 2D GIS view, or
- use a clearly labeled visualization layer,
- but never present synthetic geometry as measured seafloor truth.

Controls:

```text
Zoom
Pan
Rotate where supported
Layer visibility
Detection filtering
Center on detection
Fit to survey
Reset view
```

---

# E7. Sonar Investigation Workspace

Provide a dedicated analysis workspace.

Recommended layout:

```text
┌──────────────────────┬────────────────────────┬─────────────────────┐
│ Sonar Image          │ GIS / 3D Map           │ Detection Details   │
│                      │                        │                     │
│ Original             │ Survey Track           │ Class               │
│ Processed            │ ● Detections           │ Confidence           │
│ AI Overlay           │ Coverage               │ Uncertainty          │
│ Mask / Box            │ Selected location      │ Evidence             │
│                      │                        │ Position error       │
│                      │                        │ Priority              │
└──────────────────────┴────────────────────────┴─────────────────────┘
```

Interactions must be synchronized:

```text
Click sonar detection
→ select corresponding detection
→ center GIS
→ update detail panel

Click GIS marker
→ select detection
→ open matching sonar evidence
```

---

# E8. Component-Level Refresh and State Preservation

This is mandatory.

Never use:

```text
User action
→ full application reload
→ Home page
```

Prefer:

```text
User action
→ targeted API request
→ targeted state update
→ keep current context
```

Examples:

### Refresh map
Update only map data.

### Refresh chart
Update only chart data.

### Refresh detection list
Update only detection list.

### Re-run AI
Update only the relevant job/result state.

### New live detection
Insert/update only affected map/list/KPI elements.

Preserve where practical:

- search
- filters
- selected detection
- map center
- zoom
- active tab
- date range
- pagination
- scroll position
- unsaved review note

Do not unexpectedly navigate the user away from their current task.

---

# E9. Loading / Empty / Error / Offline / Stale States

Every asynchronous feature must define:

```text
IDLE
↓
LOADING / PROCESSING
↓
SUCCESS
```

and failure paths:

```text
ERROR
OFFLINE
STALE
RETRY
```

Examples:

```text
Loading sonar data...
Processing 37%...
No detections match these filters.
Unable to load detections. Retry.
Connection lost. Reconnecting...
Data may be stale.
```

Avoid blank panels and unexplained spinners.

---

# E10. Real-Time Architecture

Where real-time behavior is required:

```text
Data source
→ Backend
→ Processing event
→ WebSocket / SSE
→ Frontend state store
→ affected components
```

Real-time events may include:

- job progress
- newly completed frame
- detection created
- detection updated
- review action
- alert created
- service status change

Implement:

- connection state
- automatic reconnect
- heartbeat if required
- duplicate-event protection where necessary
- stale detection
- last successful update
- safe backfill after reconnect

After reconnect, refresh only the stale state required to restore consistency.

---

# E11. Live Processing UX

Processing should visibly progress through real stages:

```text
VALIDATING
↓
DECODING
↓
PREPROCESSING
↓
DETECTION
↓
VERIFICATION
↓
CALIBRATION
↓
GEOTAGGING
↓
PRIORITIZATION
↓
SAVING
↓
COMPLETE
```

Show actual progress when measurable.

If exact progress is not measurable, show a stage-based indicator rather than a fabricated percentage.

A long-running job must not freeze the main interface.

---

# E12. AI Result Presentation

For each detection, show only metrics actually calculated.

Example:

```text
Detection ID: D-00027
Class: Ghost Net

Model confidence: 91%
Calibrated confidence: 93%
Uncertainty: Low

Evidence:
- Artificial classifier: positive
- Shadow/context evidence: supportive
- Data quality: acceptable

Location:
Lat: XX.XXXXXX
Lon: XX.XXXXXX
Position error: ±X.X m
Localization: frame-level

Priority: HIGH
Review: Pending
Model: vX.X
```

Do not label raw softmax/model probability as "accuracy".

---

# E13. Confidence and Uncertainty UX

Separate:

- model score
- calibrated confidence
- uncertainty
- final decision

Example:

```text
Raw candidate score      0.91
Calibrated confidence    0.93
Uncertainty              LOW
Final status             HIGH-CONFIDENCE ARTIFICIAL
```

For uncertain cases:

```text
UNKNOWN / REVIEW REQUIRED
```

Do not force a false classification merely to avoid the unknown state.

---

# E14. AI Evidence / Explainability

The UI should answer:

> Why did the system flag this?

Show available evidence:

- detector result
- verifier result
- shadow evidence
- local contrast
- texture/context
- data-quality indicators
- class result
- calibration result

For each evidence source, state whether it is:

- available and used
- unavailable
- inconclusive

Never display an evidence item unless it was actually computed.

---

# E15. Human-in-the-Loop Review

Create a dedicated review queue:

```text
UNKNOWN
NEEDS REVIEW
ACCEPTED ARTIFICIAL
REJECTED NATURAL
```

Reviewer actions:

```text
Accept Artificial
Reject Natural
Mark Unknown
Add Note
```

Persist the decision.

Store:

- reviewer
- timestamp
- old status
- new status
- note where applicable

Human feedback may later become training data, but do not claim automatic retraining unless it is genuinely implemented.

---

# E16. Geospatial Truthfulness

Every location record should distinguish:

```text
latitude
longitude
position_error_m
localization_method
metadata_source
```

Possible localization states:

- frame-level
- ping-level
- geometry-derived
- surveyed/verified
- simulated/demo

Never claim centimeter-level or exact object localization when the source data does not support it.

---

# E17. GIS Filter Synchronization

Filters should synchronize across views when appropriate.

Example:

```text
Select "Ghost Net"
→ map shows ghost nets
→ detection list filters
→ relevant KPI updates
→ charts update if designed to respond
```

Map selection should update details without destroying other filters.

---

# E18. Survey Management

A survey should have:

```text
survey_id
name
source
sonar_type
start/end time where available
coverage
processing status
metadata status
file count
processed count
detection count
review status
created_at
updated_at
```

Possible statuses:

```text
UPLOADED
VALIDATING
PROCESSING
PARTIAL
COMPLETE
FAILED
ARCHIVED
```

---

# E19. Detection Lifecycle

Use an explicit lifecycle:

```text
CANDIDATE
↓
VERIFIED ARTIFICIAL / NATURAL / UNKNOWN
↓
GEOTAGGED
↓
PRIORITIZED
↓
REVIEWED
↓
REPORTED
```

Do not silently overwrite historical decisions.

---

# E20. Duplicate / Repeated Detection Handling

If multiple adjacent frames see the same object, avoid counting it as many independent hazards without explanation.

Where supported, implement:

```text
frame detections
→ spatial/temporal grouping
→ persistent object candidate
→ one survey-level detection
```

Store the relationship between:

- source frames
- grouped detection
- representative location
- confidence rule
- evidence summary

Do not implement sophisticated tracking unless the data supports it; otherwise mark detections as frame-level.

---

# E21. Priority Engine UX

Priority may use actual supported inputs such as:

- calibrated confidence
- class
- estimated dimensions
- persistence
- data quality
- location/context where justified

Display:

```text
Priority: HIGH

Reasons:
✓ High calibrated confidence
✓ Large estimated extent
✓ Persistent across frames
```

Never hide the reason behind a mysterious score.

---

# E22. Data Quality Panel

Expose the PS-specific quality challenges:

```text
Speckle noise
Resolution
Acoustic shadow
Dropout
Motion distortion
Metadata completeness
```

Example:

```text
SONAR QUALITY
Noise:        LOW
Resolution:   GOOD
Dropout:      2.4%
Shadow:       DETECTED
Metadata:     COMPLETE
Overall:      ACCEPTABLE
```

Values must come from actual calculations.

---

# E23. Security Architecture

Security requirements:

### Authentication
- secure password hashing
- login
- logout
- session/token expiration
- protected routes
- refresh mechanism where used

### Authorization
Use RBAC or another explicit permission model.

Example:

```text
ADMIN
OPERATOR
REVIEWER
VIEWER
```

Backend must enforce permissions. Hiding frontend buttons is not sufficient.

### API security
- authentication
- authorization
- validation
- rate limiting
- request-size limits
- CORS configuration
- secure error responses
- safe logging

### Secrets
Never hardcode:
- passwords
- API keys
- signing secrets
- database credentials

Use environment variables / secret storage.

---

# E24. Secure Sonar File Upload

Treat uploads as untrusted input.

Validate:

- allowed type
- extension
- actual content where practical
- file size
- archive behavior if archives are supported
- path safety
- metadata parsing failures

Do not trust:

- filename
- coordinates
- metadata values
- embedded scripts
- claimed content type

Store uploaded files outside publicly executable paths.

---

# E25. Database Security

Use:

- least-privilege DB account
- parameterized queries / ORM-safe queries
- migrations
- constraints
- transaction boundaries
- indexes
- encrypted connections in production where appropriate
- backups
- restore testing

Never expose direct database access to the browser.

---

# E26. Audit Trail

Log important actions such as:

- login/security events where appropriate
- survey creation
- upload
- processing start/stop
- detection review
- report generation
- model selection
- configuration changes
- administrative actions

An audit record should contain enough information to reconstruct the action without exposing secrets.

---

# E27. Observability

Implement structured logs for:

- API errors
- processing errors
- failed frames
- AI inference
- report generation
- real-time connection issues
- authentication/security events
- performance timing

Prefer correlation/request IDs.

Do not log passwords, raw tokens, or other secrets.

---

# E28. Health Monitoring

Provide machine-readable health endpoints and a UI status view where useful.

Example:

```text
API           ONLINE
DATABASE      ONLINE
AI ENGINE     ONLINE
GIS           ONLINE
PROCESSOR     ACTIVE
REAL-TIME     LIVE
STORAGE       HEALTHY
```

Statuses must reflect actual service checks.

---

# E29. Reliability and Recovery

Implement:

- bounded retries
- timeouts
- idempotent operations where appropriate
- partial-failure handling
- failed-frame queue/log
- job cancellation where practical
- automatic reconnect for live connections
- recovery after restart
- backup and restore

Do not use infinite retry loops.

---

# E30. Background Jobs

Use background processing for expensive tasks:

- large survey processing
- AI inference batches
- report generation
- dataset imports
- training/evaluation when integrated into the platform

Jobs should expose:

```text
job_id
type
status
created_at
started_at
completed_at
progress/state
error_summary
retry_count
```

---

# E31. Performance Requirements

Measure instead of guessing.

Important metrics:

- preprocessing latency
- detector latency
- verifier latency
- total frame latency
- throughput
- peak memory
- model size
- database query latency
- dashboard update latency

Optimize with:

- batching where helpful
- tiling
- indexes
- pagination
- caching where justified
- lazy loading
- map clustering
- efficient state updates

Do not optimize before measuring.

---

# E32. Caching

Cache only data where stale values are acceptable and invalidation is understood.

Examples:

- static metadata
- stable reference data
- previously completed report results
- repeated read-heavy queries

Never allow caching to show a false "LIVE" state.

Always define invalidation/update behavior.

---

# E33. Search / Filtering / Pagination

Support practical investigation tools:

- class
- confidence
- priority
- review state
- survey
- date range
- geographic area
- search text where applicable

Large detection lists must use pagination or virtualization.

Do not load the entire dataset into the browser just to filter it.

---

# E34. Responsive UX

Support:

- desktop
- laptop
- tablet
- mobile

Desktop:
- sidebar + investigation workspace

Tablet:
- collapsible navigation + adaptive panels

Mobile:
- stacked cards/panels + touch-friendly navigation

Do not merely shrink the desktop layout.

---

# E35. Accessibility

Implement:

- semantic controls
- keyboard navigation
- visible focus
- accessible labels
- readable contrast
- non-hover-only interactions
- reduced-motion support
- screen-reader-friendly status updates where useful

Important information must never be communicated by color alone.

---

# E36. Real-Time Refresh Rules

The following are mandatory product behaviors:

```text
Refresh Map
→ Map updates only

Refresh Detection List
→ Detection list updates only

Refresh Analytics
→ Analytics updates only

New detection event
→ relevant marker/list/KPI updates only

Job progress
→ progress indicator updates only

AI completion
→ result panel updates only
```

No unnecessary redirect.

---

# E37. Offline Mode

Core inference should be able to run locally where supported.

Offline UX must clearly communicate:

```text
● LOCAL INFERENCE
● INTERNET NOT REQUIRED
```

If a feature genuinely requires an external service, label it accordingly.

Offline mode should not silently use a cloud dependency.

---

# E38. Edge Deployment

Primary path:

```text
PyTorch
→ ONNX export
→ ONNX Runtime
→ CPU/edge
```

Optional:

```text
ONNX
→ TensorRT
→ supported NVIDIA edge device
```

Measure:

- model size
- latency
- memory
- images/sec

Do not claim edge deployment is proven until tested on the claimed runtime/device.

---

# E39. Demo Reliability

Use real, honest reliability techniques:

```text
Offline operation
Pre-validated sample datasets
Golden-path demo
Cached completed results where appropriate
Deterministic seeds where applicable
Graceful failed-frame handling
Recorded backup
Batch-survey demonstration
```

Clearly label preloaded/simulated data.

Never replace real AI results with fake results during the live demo without saying so.

---

# E40. Test Strategy

Testing should cover:

### Unit
- parsers
- preprocessing
- geotagging
- confidence calibration
- scoring
- report generation

### Integration
- frontend ↔ backend
- backend ↔ database
- backend ↔ AI
- processing ↔ real-time events
- GIS ↔ detection data

### End-to-end
```text
upload
→ processing
→ detection
→ geotag
→ database
→ dashboard
→ report
```

### Security
- unauthorized access
- malformed uploads
- invalid inputs
- rate limits
- token/session behavior

### Resilience
- service unavailable
- reconnect
- partial survey failure
- malformed frame
- database timeout

### UI
- desktop
- mobile
- keyboard
- loading/error/empty states

---

# E41. Regression Rule

Before merging a change:

1. Run relevant tests.
2. Check the affected workflow.
3. Check for broken existing functionality.
4. Check API compatibility.
5. Check database migration safety.
6. Check UI state preservation.
7. Check logs/errors.
8. Record performance changes when material.

Do not "fix" one page by breaking another.

---

# E42. API Contract

Lock two contracts early:

### Backend ↔ Frontend

Normalized report/detection schema.

### AI ↔ Backend

Normalized model-output schema.

Minimum detection representation should support fields such as:

```text
detection_id
survey_id
frame_id
class
raw_score
calibrated_confidence
uncertainty
bbox / mask
latitude
longitude
position_error_m
localization
dimensions
priority
review_status
model_version
source_file
evidence_summary
created_at
```

Fields must be nullable when the data source cannot provide them.

---

# E43. Model Registry / Versioning

Track:

```text
model_id
model_name
version
architecture
training_dataset_version
class schema
preprocessing version
calibration version
export format
deployment status
metrics
created_at
```

A detection must be traceable to the model version that generated it.

---

# E44. Dataset Registry

Keep:

```text
dataset_id
dataset_name
source
license
sonar_type
resolution
classes
annotation_type
metadata availability
GPS availability
download/access date
citation
commercial-use status where relevant
notes
```

This complements the existing `data_sources.csv`.

Never lose provenance.

---

# E45. Annotation / Data QA Interface

Where practical, expose:

- annotation samples
- class counts
- class imbalance
- invalid labels
- duplicate labels
- missing labels
- hard-negative examples
- review status

The dataset remains the responsibility of the data/ML workflow, but the platform should expose enough information for traceability.

---

# E46. Model Evaluation Dashboard

Show measured metrics:

```text
Precision
Recall
F1
mAP
False positives / image
Inference latency
Class-wise metrics
```

Support comparison:

```text
YOLO11-N baseline
vs
YOLO11-S
vs
+ hard negatives
vs
+ verifier
vs
+ shadow/context
```

Do not publish empty or fabricated numbers.

---

# E47. Challenge-Slice Evaluation

Create separate evaluation slices for:

```text
Speckle noise
Low resolution
Acoustic shadow
Motion/dropout
```

Show:

```text
Dataset slice
Sample count
Precision
Recall
F1
Notes
```

This ties the evaluation directly to the PS requirements.

---

# E48. Synthetic Data Governance

If synthetic ghost-net data is used:

- label every synthetic sample
- track its generator/version
- preserve the source/seed where practical
- separate synthetic vs real evaluation
- never evaluate only on synthetic data
- demonstrate impact on held-out real data
- do not claim synthetic improvement without measured evidence

Keep the synthetic proportion as an experiment variable, not an unverified universal rule.

---

# E49. Ghost-Net Synthetic Pipeline UI

When this feature is part of the implemented product, expose:

```text
REAL DATA
SYNTHETIC DATA
MIX RATIO
MODEL VERSION
HELD-OUT REAL TEST RESULT
```

Example:

```text
Without synthetic: F1 = X
With synthetic:    F1 = Y
Difference:        Y-X
```

X and Y must be real measured values.

---

# E50. Hard-Negative Mining UI

Show representative false positives:

```text
Rock → Pipe
Ridge → Wreck
Shadow → Net
Noise → Debris
```

Allow an authorized user to:

```text
Add to hard-negative set
Reject
Annotate
Record reason
```

The training system must maintain provenance of added examples.

---

# E51. Anomaly / Unknown Detection

Where implemented, the natural-seabed autoencoder or other novelty detector should feed:

```text
Known object
or
Unknown anomaly
```

Unknown results must not be forced into a known class.

The UI should make the distinction visually obvious.

---

# E52. Sonar Geometry and Dimension Estimation

If acoustic geometry supports estimation:

```text
shadow length
+
sonar altitude
+
slant range
→
estimated object height
```

Store the assumptions and units.

Never show estimated dimensions as measured ground truth.

The UI should identify:

```text
Estimated
Derived
Measured
Unknown
```

where appropriate.

---

# E53. Metadata Parsing Strategy

Support the actual formats present in the data.

Do not assume every dataset is XTF.

The parser layer should:

```text
detect format
→ parse available fields
→ normalize
→ validate
→ store source/provenance
```

If a synthetic XTF-like fixture is used for testing, mark it explicitly as simulated.

---

# E54. Scientific / Data Honesty Rules

Use these labels consistently:

- measured
- estimated
- derived
- model-predicted
- calibrated
- simulated
- unavailable
- frame-level
- approximate

Never use "exact", "guaranteed", or "real-time" unless the implementation and data justify the claim.

---

# E55. Final User Workflow

### Operator

```text
Login
→ Create/open survey
→ Upload sonar image/log
→ Upload/associate metadata
→ Validate
→ Start processing
→ Monitor live processing
→ Inspect detections
→ Inspect map
→ Review uncertain cases
→ Confirm/Reject
→ View priorities
→ Generate report
```

### Reviewer

```text
Open review queue
→ Inspect sonar evidence
→ Inspect GIS position
→ Inspect confidence/evidence
→ Accept / Reject / Unknown
→ Add note
→ Save decision
```

### Administrator

```text
Manage users
→ Roles/permissions
→ Models
→ System health
→ Audit
→ Configuration
```

---

# E56. Final Demo Screen Sequence

Recommended demo:

```text
1. Dashboard / mission overview
2. Upload SSS survey
3. Validation
4. Sonar quality assessment
5. Live processing
6. Detection appears
7. Natural-vs-artificial verification
8. Confidence + uncertainty
9. Acoustic-shadow/context evidence
10. Sonar + GIS split view
11. Geotag + position error
12. Priority
13. Unknown / human review
14. Reports
15. Evaluation metrics
16. Edge/offline proof
17. Error recovery
```

The UI should make the story visible without requiring the judge to understand the code.

---

# E57. Final A–Z Master Checklist

Use this as the final acceptance checklist.

## A — Authentication
Login, logout, sessions/tokens, password handling, protected routes.

## B — Backend
FastAPI/API architecture, validation, services, status codes, background jobs.

## C — Caching
Only justified caching, explicit invalidation, no stale-live confusion.

## D — Database
PostgreSQL/PostGIS, schema, indexes, constraints, migrations, backups.

## E — Error Handling
Frontend/backend/AI/GIS/database/network error paths.

## F — Frontend
Responsive, reusable, accessible, state-aware components.

## G — GIS
2D/3D mapping, layers, markers, clusters, spatial filtering.

## H — Health
API/database/AI/GIS/processor/realtime status.

## I — Input Validation
Frontend + backend + uploaded-file + metadata validation.

## J — Jobs
Background processing, progress, retries, cancellation/recovery where practical.

## K — Knowledge/Data
Historical data, reference information, provenance, metadata.

## L — Live
WebSocket/SSE, reconnect, live dashboard/map, stale detection.

## M — ML
Preprocessing, detector, verifier, anomaly path, calibration, evaluation.

## N — Notifications
Hazard alerts, processing failures, review alerts, in-app state.

## O — Observability
Logs, request IDs, metrics, AI/processing traces, audit trail.

## P — Performance
Latency, throughput, memory, batching, pagination, map optimization.

## Q — Query
Search, filters, sorting, date ranges, spatial queries.

## R — Reliability
Retries, timeouts, idempotency, recovery, partial failure handling.

## S — Security
Authentication, authorization, secure uploads, secrets, API protection, rate limiting, HTTPS.

## T — Time
UTC/internal consistency, timestamps, survey timeline, last updated, timezone display.

## U — UX
State preservation, targeted refresh, clear workflows, loading/error/empty/offline states.

## V — Versioning
API, model, dataset, preprocessing, calibration, database migrations.

## W — Web Quality
Responsive, browser-aware, mobile, accessibility, slow-network handling.

## X — Explainable AI
Evidence, confidence, uncertainty, supporting factors, limitations.

## Y — Analytics
KPI, trends, class distribution, model metrics, survey analytics.

## Z — Zero-Downtime / Production Mindset
Health checks, migrations, backups, rollback, deployment safety, offline path, recovery.

---

# PART F — FINAL ACCEPTANCE GATE

The project is NOT complete merely because the dashboard opens.

A release candidate must answer YES to the applicable questions below.

## Core Functionality

- Can real SSS data be loaded?
- Can the system validate it?
- Can it preprocess it?
- Can the real AI model process it?
- Can detections be stored?
- Can supported metadata be parsed?
- Can supported locations be derived?
- Can reports be generated?

## AI Quality

- Is the baseline measured?
- Is the main model measured?
- Is there leakage-safe evaluation?
- Are false positives analyzed?
- Are hard negatives used where applicable?
- Is confidence calibrated?
- Is uncertainty handled?
- Does unknown/human review work?
- Are PS-specific challenge slices measured?

## GIS

- Is the detection displayed at the supported location?
- Is localization precision honestly communicated?
- Does sonar ↔ map selection work?
- Do map filters work?
- Do layers represent real/available data?

## Real-Time

- Do relevant events update without a full reload?
- Does the connection status reflect reality?
- Does reconnect work?
- Does the application recover after temporary loss?

## UX

- Are loading states present?
- Are empty states present?
- Are error states useful?
- Does refresh preserve context?
- Does mobile layout work?
- Can the core workflow be completed without confusing navigation?

## Security

- Are protected operations actually authorized?
- Are uploads validated?
- Are secrets protected?
- Are APIs protected?
- Are sensitive errors hidden from users?

## Production / Edge

- Can the system run locally?
- Is offline inference genuinely supported where claimed?
- Has ONNX export/runtime been tested if claimed?
- Are latency/model-size measurements real?
- Can one bad frame fail without collapsing the entire survey?

## Scientific Integrity

- Are simulated values clearly labeled?
- Are estimated dimensions labeled as estimates?
- Are frame-level coordinates not falsely described as exact?
- Are model metrics based on real test data?
- Are unsupported capabilities explicitly marked unavailable?

---

# PART G — FINAL PRODUCT DEFINITION

The final product should be presented as:

> **GhostNet-AI — an end-to-end Side-Scan Sonar intelligence platform that detects suspected anthropogenic marine debris, verifies whether anomalies are likely artificial, quantifies confidence and uncertainty, localizes supported detections, prioritizes hazards, supports human review, and produces actionable structured reports — with real-time visualization and an offline/edge-capable architecture.**

The central value proposition remains:

> **We do not merely detect sonar anomalies. We verify whether they are anthropogenic, estimate how trustworthy the detection is, localize the hazard, prioritize it and generate an actionable report.**

---

# PART H — SOURCE-OF-TRUTH ORDER

When requirements conflict, use this order:

1. Official SIH26057 problem statement and official competition requirements.
2. Verified actual dataset capabilities and licensing.
3. Measured experiment results.
4. This integrated plan.
5. UI/UX and production best practices.

Never override a real data limitation merely to make a demo look better.

---

# PART I — IMPLEMENTATION PRIORITY

Build in this order:

```text
P0 — Data availability / licensing / schema
P1 — SSS loading + preprocessing
P2 — AI baseline
P3 — AI main model
P4 — False-positive reduction
P5 — Confidence / uncertainty
P6 — Geotagging
P7 — Database/API
P8 — Core dashboard
P9 — GIS + sonar investigation
P10 — Real-time processing
P11 — Human review / alerts
P12 — Reports
P13 — Security hardening
P14 — Testing / observability
P15 — ONNX / offline / edge
P16 — Advanced 3D polish
```

Do not reverse this order merely to make the early prototype visually impressive.

---

# PART J — FINAL "DONE MEANS DONE" RULE

A feature is complete only when:

```text
IMPLEMENTED
+
CONNECTED
+
VALIDATED
+
ERROR-HANDLED
+
TESTED
+
SECURED WHERE REQUIRED
+
DOCUMENTED WHERE NEEDED
+
MEASURED WHERE MEASUREMENT IS RELEVANT
```

Never mark a feature complete because only its UI exists.

