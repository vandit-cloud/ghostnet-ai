# SIH26057 — GhostNet-AI
# MEMBER 1 — AI / ML + SONAR / COMPUTER VISION + DATA BUILD PLAN

> **Owner:** Member 1  
> **Primary responsibility:** Dataset + Sonar preprocessing + AI/ML + natural/artificial verification + confidence/uncertainty + geotagging logic + AI output contract  
> **Goal:** Build the complete intelligence pipeline independently so Member 2 can connect it to the FastAPI, database, GIS and frontend.

---

# 1. Your Responsibility in the 2-Member Team

## Member 1 owns

```text
DATA
  ↓
ANNOTATION / NORMALIZATION
  ↓
SONAR PREPROCESSING
  ↓
AI DETECTION / SEGMENTATION
  ↓
NATURAL vs ARTIFICIAL VERIFICATION
  ↓
CONFIDENCE / UNCERTAINTY
  ↓
UNKNOWN HANDLING
  ↓
GEOTAGGING LOGIC
  ↓
AI OUTPUT JSON
```

## Member 2 owns

```text
FASTAPI
DATABASE / POSTGIS
FRONTEND
DASHBOARD
GIS UI
UPLOAD UI
REPORT UI
REAL-TIME UI
```

You do **not** need to build the complete frontend.

You do **not** need to build the complete backend.

You must provide a stable AI/data interface that Member 2 can call.

---

# 2. Problem You Must Solve

The Side-Scan Sonar (SSS) imagery contains natural seafloor structures that may look like artificial debris.

The AI must help identify man-made anomalies such as supported examples:

- ghost nets / entangled debris
- shipwrecks
- pipes
- cylinders
- other anthropogenic debris

while dealing with:

- speckle/noise
- varying pixel resolution
- acoustic shadows
- invalid/dropout regions
- heave/pitch/roll-related image degradation

The output must support:

- classification
- confidence
- uncertainty where implemented
- bounding box or segmentation mask
- supported dimensions
- supported latitude/longitude
- source frame/ping information
- model version

---

# 3. Technology Stack

## Core language

```text
Python 3.11+
```

## Deep Learning

```text
PyTorch
Ultralytics YOLO
YOLO11-N  → baseline
YOLO11-S  → main candidate
```

## Segmentation options

Use only when supported by available labels:

```text
YOLO segmentation
or
U-Net
```

Optional advanced refinement:

```text
SAM 2.1
```

Do not add SAM unless it provides measurable value.

## Verification model

```text
EfficientNet-B0
```

Use as a second-stage natural/artificial verifier if experiments show it improves false-positive performance.

## Computer Vision

```text
OpenCV
NumPy
Pandas
scikit-learn
```

## Calibration

```text
temperature scaling
```

Use validation data for calibration.

## Optional anomaly detection

```text
small autoencoder
```

Train on natural seabed only when the unknown-anomaly feature is actually implemented.

## Export / Edge

```text
ONNX
ONNX Runtime
```

Optional:

```text
TensorRT
```

only when suitable NVIDIA hardware exists.

## Metadata / Geo processing

Use Python libraries appropriate to the actual source formats.

Do not assume every dataset is XTF.

## Experiment tracking

At minimum:

```text
CSV/JSON experiment logs
Git
versioned config files
```

An experiment tracker may be added if useful, but is not mandatory.

---

# 4. Final AI Pipeline

The baseline target architecture is:

```text
SSS image/log
       ↓
Data validation
       ↓
Frame extraction if needed
       ↓
Sonar quality assessment
       ↓
Sonar preprocessing
       ↓
YOLO11-N / YOLO11-S
       ↓
Candidate region
       ↓
Crop
       ↓
Natural / Artificial verification
       ↓
Acoustic-shadow / context evidence
       ↓
Confidence calibration
       ↓
Known / Unknown / Review
       ↓
Geotagging
       ↓
Dimension estimation where supportable
       ↓
Priority inputs
       ↓
Normalized AI output JSON
```

The pipeline must be modular so the primary detector can be replaced without rewriting the rest.

---

# 5. Phase 0 — Inspect Actual Data Before Coding the Model

Do this first.

## Verify

1. Official SIH resources.
2. Available SSS images.
3. Raw sonar logs if available.
4. Metadata.
5. GPS/coordinates.
6. Ping/frame information.
7. Annotation format.
8. Actual supported classes.
9. Resolution.
10. Licensing.

## Output

Create:

```text
data_inventory.csv
```

with fields such as:

```text
dataset_id
dataset_name
source
sonar_type
format
resolution
classes
annotation_type
metadata_available
gps_available
license
citation
notes
```

Do not train before understanding what the data actually contains.

---

# 6. Dataset Acquisition

Use this priority:

```text
1. Official SIH resources
2. Public SSS datasets
3. Research datasets
4. Own collection only if required/feasible
```

For each source:

```text
Download small sample
→ verify SSS modality
→ inspect labels
→ inspect metadata
→ verify license
→ record provenance
→ integrate
```

Do not download datasets blindly.

---

# 7. Positive Data

Use actual supported classes.

Possible classes:

```text
ghost_net
shipwreck
pipe
cylinder
other_debris
```

Do not invent a class simply because it appears in the problem statement.

If a dataset only provides a generic debris label, preserve that limitation.

---

# 8. Natural / Hard-Negative Data

This is one of your most important responsibilities.

Collect difficult natural examples:

```text
rocks
sand ripples
natural ridges
natural seabed structures
acoustic shadows
noise
dropout regions
```

Use these to teach the detector what NOT to classify as debris.

False positives should become hard-negative examples.

---

# 9. Dataset Structure

Create:

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

# 10. Annotation Standard

Standardize training annotations into one format.

Preferred:

```text
YOLO detection
or
YOLO-segmentation
```

Possible source conversions:

```text
VOC XML
→ YOLO boxes

Segmentation masks
→ YOLO polygons

Classification-only source
→ manually annotate boxes only when feasible
```

Do not fabricate labels.

---

# 11. Annotation Quality Control

Before training:

```text
Random sample
→ verify class
→ verify box/mask
→ check missing objects
→ check duplicates
→ check natural/debris confusion
→ check imbalance
```

Create:

```text
annotation_audit.csv
```

Track corrections.

---

# 12. Leakage-Safe Dataset Split

Do NOT randomly split adjacent sonar frames.

Bad:

```text
Frame 100 → train
Frame 101 → test
Frame 102 → train
```

Prefer:

```text
Survey A → Train
Survey B → Train
Survey C → Validation
Survey D → Test
```

Use unseen survey/location data for the final test whenever possible.

This protects the credibility of your reported F1.

---

# 13. Baseline Model — YOLO11-N

Your first model must be simple.

Purpose:

- prove the dataset works
- detect annotation problems
- establish a measurable baseline

Measure:

```text
Precision
Recall
F1
mAP
Inference time
False positives
```

Save results:

```text
experiments/baseline_yolo11n/
```

---

# 14. Main Model — YOLO11-S

Evaluate:

```text
YOLO11-N
vs
YOLO11-S
```

Choose YOLO11-S as the main model only if its accuracy/speed tradeoff is useful.

Record:

```text
model version
training config
dataset version
metrics
inference time
model size
```

Never choose a larger model merely because it sounds better.

---

# 15. Sonar Preprocessing

Build preprocessing as configurable functions.

Possible steps:

```text
Input
 ↓
Speckle/noise reduction
 ↓
Intensity normalization
 ↓
Contrast normalization
 ↓
CLAHE if validated
 ↓
Resolution normalization
 ↓
Tiling if required
 ↓
Dropout/invalid-region masking
 ↓
AI input
```

Do not assume every preprocessing step improves performance.

Run experiments:

```text
Baseline
vs
Preprocessing A
vs
Preprocessing B
vs
Preprocessing combination
```

Keep only changes that improve held-out validation performance.

---

# 16. Sonar Quality Assessment

Where measurable, calculate or classify:

```text
Noise quality
Resolution quality
Dropout/invalid regions
Metadata completeness
Potential motion distortion
```

Output a quality object:

```json
{
  "overall_status": "acceptable",
  "noise": "low",
  "dropout": 0.02,
  "metadata_complete": true
}
```

Do not create unsupported measurements.

---

# 17. Heave / Pitch / Roll Strategy

Do not pretend to correct motion if the necessary sensor data is unavailable.

Use:

```text
1. image-quality detection
2. available navigation metadata
3. realistic augmentation
4. invalid-region masking
```

If actual motion-compensation data exists, a proper correction module can be added.

---

# 18. Sonar-Specific Augmentation

Use augmentations that imitate actual PS conditions:

```text
Speckle noise
Shadow elongation
Column dropouts / blackout
Resolution changes
Intensity variation
Contrast variation
```

Do not rely only on generic image flips/crops.

Measure whether augmentation improves validation/test robustness.

---

# 19. Classical Pre-Filter

Before expensive ML inference, an optional lightweight pre-filter can remove obvious non-object regions.

Possible rules:

```text
minimum blob size
aspect-ratio constraints
intensity constraints
invalid-region exclusion
```

Use it only if experiments show:
- improved precision,
- reduced false positives,
- or faster inference.

Do not remove true positives through overly aggressive filtering.

---

# 20. Natural-vs-Artificial Verification

This is your major differentiation.

Stage 1:

```text
"Something suspicious is here."
```

Stage 2:

```text
"Is it likely man-made?"
```

A second-stage verifier can use:

```text
Candidate crop
→ EfficientNet-B0
→ artificial/natural score
```

Then combine validated evidence.

Do NOT simply average arbitrary percentages.

---

# 21. Acoustic Shadow / Context Analysis

Where data supports it, extract:

```text
object size
shadow size
shadow length
object-to-shadow relationship
local contrast
texture
shape/context
```

Concept:

```text
Candidate
+
Shadow evidence
+
Local context
→ supporting evidence
```

Some objects may not have a clean visible shadow.

Do not force shadow evidence when unavailable.

---

# 22. Hard-Negative Mining

Use an iterative loop:

```text
Train model
 ↓
Run validation
 ↓
Find false positives
 ↓
Analyze why
 ↓
Add difficult natural examples
 ↓
Retrain
 ↓
Compare metrics
```

Examples:

```text
Rock → Pipe
Ridge → Wreck
Shadow → Net
Noise → Debris
```

Keep provenance for each hard-negative sample.

---

# 23. Synthetic Ghost-Net Data

Ghost-net data may be limited.

If synthetic generation is used:

```text
Real SSS background
+
synthetic/procedural ghost-net appearance
+
sonar-style degradation
→ synthetic training example
```

Potential methods:

```text
Diffusion-based generation
or
copy-paste / procedural mesh augmentation
```

Use synthetic data only as a training experiment.

Evaluate:

```text
WITHOUT synthetic → F1 = A
WITH synthetic     → F1 = B
```

Use held-out real data for the comparison.

Never report synthetic-only test performance as real-world performance.

---

# 24. Unknown-Anomaly Path

Optional but strongly useful.

Possible implementation:

```text
Autoencoder trained on natural seabed
→ reconstruction error
→ anomaly candidate
```

This can identify candidates outside known classes.

Output:

```text
known_class
or
unknown_anomaly
```

Unknown is not automatically "ghost net".

Unknown means:

> suspicious, but not confidently classified into a supported class.

---

# 25. Confidence Calibration

Raw model probability must not automatically be called a trustworthy 0–100% probability.

Use:

```text
temperature scaling
```

on validation data where implemented.

Create:

```text
uncalibrated confidence
vs
calibrated confidence
```

Evaluate calibration using an appropriate calibration analysis/reliability diagram.

Store:

```text
raw_score
calibrated_confidence
calibration_version
```

---

# 26. Uncertainty

If implemented with test-time augmentation:

```text
Same input
→ small controlled augmentations
→ multiple predictions
→ prediction spread
→ uncertainty estimate
```

Output:

```text
Low
Medium
High
```

or a numeric uncertainty metric if properly defined.

Do not present an arbitrary uncertainty value.

---

# 27. Known / Unknown / Review Logic

Recommended basic logic:

```text
High-confidence supported class
→ KNOWN / ARTIFICIAL

Strong evidence against artificial
→ NATURAL / REJECTED

Insufficient confidence or conflicting evidence
→ UNKNOWN / REVIEW
```

Thresholds must be determined from validation experiments.

Do not choose thresholds only to make demo numbers look good.

---

# 28. Geotagging

Your job is the **geotagging computation/parser**.

Basic:

```text
frame_id / ping_id
→ metadata lookup
→ latitude / longitude
```

Enhanced when data supports it:

```text
GPS
+
heading
+
range
+
bearing
+
depth
→ improved object location
```

Never claim more precision than the source permits.

---

# 29. Position Error

When supportable, output:

```text
position_error_m
```

Example:

```json
{
  "latitude": 20.123456,
  "longitude": 70.123456,
  "position_error_m": 4.5,
  "localization": "frame-level"
}
```

The exact numeric value must come from the implemented method or real metadata; never invent it.

---

# 30. Sonar Dimension Estimation

When actual sonar geometry supports it:

```text
shadow length
+
sonar altitude
+
slant range
→ estimated object height
```

Clearly label dimensions as:

```text
measured
estimated
derived
unknown
```

Never present an estimated dimension as direct ground-truth measurement.

---

# 31. Metadata Parsing

Support only the formats actually encountered.

Pipeline:

```text
Detect format
→ parse
→ normalize
→ validate
→ preserve provenance
```

Potential inputs:

```text
CSV
JSON
ping headers
XTF or XTF-like data where actually available
image metadata
```

Do not assume every dataset is XTF.

For synthetic testing fixtures, label them as simulated.

---

# 32. AI Output Contract With Member 2

Freeze this contract early.

Your service should return conceptually:

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
      "bbox": [100, 120, 300, 240],
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
      "model_version": "v1.0",
      "evidence_summary": []
    }
  ]
}
```

Fields may be `null` when the data cannot provide them.

Do not change this contract casually after Member 2 begins integration.

---

# 33. AI Service Interface

Recommended interface:

```python
result = analyze_frame(
    image_path=image_path,
    metadata=metadata
)
```

or an HTTP inference endpoint such as:

```text
POST /ai/v1/infer
```

Inputs:

```text
image
frame_id
survey_id
metadata
processing configuration
```

Outputs:

```text
normalized detection JSON
```

Keep model internals hidden behind this interface.

---

# 34. Model Versioning

Every inference should identify:

```text
model_id
model_version
dataset_version
preprocessing_version
calibration_version
```

Suggested directory:

```text
models/
├── yolo11n_baseline/
├── yolo11s_main/
├── verifier/
├── calibrator/
└── anomaly/
```

Do not overwrite a model version used to generate historical results.

---

# 35. Experiment Structure

Create:

```text
experiments/
├── baseline/
├── preprocessing/
├── yolo11n/
├── yolo11s/
├── hard_negative/
├── verifier/
├── shadow_context/
├── calibration/
├── synthetic/
├── unknown/
└── edge/
```

Each experiment should record:

```text
date
code version
dataset version
model version
configuration
metrics
observations
decision
```

---

# 36. Evaluation Metrics

For each meaningful experiment record:

```text
Precision
Recall
F1
mAP
False positives / image
Inference latency
Throughput
Model size
Memory
Class-wise metrics
```

Never invent values.

Your internal target may use:

```text
80%+ F1 = minimum internal goal
85%+ = strong
90%+ = excellent
```

but actual performance must be measured.

---

# 37. Challenge-Specific Test Sets

Create separate test slices where possible:

```text
Speckle-noise slice
Low-resolution slice
Acoustic-shadow slice
Motion/dropout slice
```

For each slice measure:

```text
Precision
Recall
F1
False positives
Notes
```

This directly demonstrates robustness against the PS challenges.

---

# 38. Final Model Comparison

Create one report:

```text
Baseline YOLO11-N
        ↓
+ preprocessing
        ↓
YOLO11-S
        ↓
+ hard negatives
        ↓
+ natural/artificial verifier
        ↓
+ shadow/context
        ↓
+ calibration
```

Compare:

```text
F1
Precision
Recall
False positives
Latency
```

The final model should be selected using evidence, not visual appearance.

---

# 39. Local / Offline Inference

The AI should run locally.

Target:

```text
Input
→ local preprocessing
→ local model
→ local result
```

Do not make a paid AI API a dependency.

A cloud option may exist later, but the core intelligence path should remain local.

---

# 40. ONNX / Edge Preparation

After the main AI pipeline is stable:

```text
PyTorch model
→ ONNX
→ ONNX Runtime
```

Measure:

```text
Model size
Latency
Memory
Images/sec
```

Optional:

```text
ONNX
→ TensorRT
```

Only claim a specific edge device is supported after actual testing.

---

# 41. Basic Testing

You own the AI/data tests.

## Data tests
- parsing
- metadata normalization
- annotation conversion
- invalid-data handling

## Preprocessing tests
- deterministic output
- dropout masking
- image normalization

## AI tests
- model loads
- expected output schema
- inference completes
- empty-detection handling

## Geotagging tests
- frame → coordinate
- missing metadata
- invalid coordinates
- position error behavior

## Report/output tests
- JSON schema
- required fields
- null handling

---

# 42. Reproducibility

Use where practical:

```text
fixed random seeds
versioned configuration
versioned datasets
versioned model files
documented preprocessing
```

Do not claim deterministic behavior if GPU/library behavior makes it impossible.

---

# 43. Error Handling

Your AI service must not crash the entire survey because one frame is bad.

Return a structured error state:

```json
{
  "frame_id": "PING-100",
  "status": "failed",
  "error_code": "INVALID_FRAME",
  "message": "Frame could not be processed."
}
```

Member 2 can then store/display the failure while processing continues where safe.

Never return secrets or internal stack traces.

---

# 44. Resource Limits

Protect the AI service from:

- enormous images
- unsupported dimensions
- excessive batch sizes
- too many simultaneous jobs
- memory exhaustion

Return a controlled error instead of crashing the system.

---

# 45. Deliverables to Member 2

Member 2 should receive:

```text
1. trained model file
2. model configuration
3. preprocessing module
4. inference module
5. metadata parser
6. geotagging module
7. normalized output schema
8. sample input
9. sample output JSON
10. model version
11. preprocessing version
12. calibration version
13. setup instructions
14. test results
15. known limitations
```

---

# 46. Recommended Repository Structure

```text
ai/
├── models/
├── configs/
├── inference/
│   ├── detector.py
│   ├── verifier.py
│   ├── calibrator.py
│   └── anomaly.py
│
├── preprocessing/
│   ├── denoise.py
│   ├── normalize.py
│   ├── dropout.py
│   └── tiling.py
│
├── sonar/
│   ├── metadata.py
│   ├── shadow.py
│   ├── quality.py
│   └── geometry.py
│
├── geotagging/
│   ├── parser.py
│   └── locator.py
│
├── datasets/
│   ├── conversion/
│   ├── validation/
│   └── splits/
│
├── evaluation/
│   ├── metrics.py
│   ├── challenge_slices.py
│   └── compare.py
│
├── experiments/
├── tests/
├── schemas/
├── scripts/
└── README.md
```

---

# 47. What You Should NOT Build

Do not spend your time on:

```text
Frontend dashboard
Login UI
GIS visual design
Report web page
Complex backend CRUD
Admin UI
3D frontend
```

Member 2 owns these.

You may create simple scripts/notebooks for debugging, but the production UI belongs to Member 2.

---

# 48. What You MUST Give Member 2

At integration time, Member 2 must be able to do:

```text
send image
+
send metadata
↓
call AI inference
↓
receive normalized JSON
↓
store it
↓
display it
```

He should NOT need to understand:

```text
YOLO internals
PyTorch training code
preprocessing implementation
calibration implementation
```

---

# 49. Integration Contract

Freeze these three things:

## Contract A — Input

```text
image
frame_id
survey_id
metadata
```

## Contract B — AI output

```text
detection JSON schema
```

## Contract C — Error output

```text
status
error_code
message
frame_id
```

These three contracts should not change frequently.

---

# 50. 2-Member Development Schedule

## Week 1

You:

```text
Verify datasets
Check licenses
Inspect SSS samples
Identify classes
Inspect metadata
Build inventory
```

Member 2:

```text
Create repository
Create frontend skeleton
Create backend skeleton
Create database skeleton
```

---

## Week 2

You:

```text
Normalize annotations
Create train/val/test split
Begin YOLO11-N baseline
```

Member 2:

```text
Create basic API contracts
Create survey/file/database tables
Create upload page
Create dashboard skeleton
```

---

## Week 3

You:

```text
YOLO11-S
Preprocessing
First real metrics
```

Member 2:

```text
Detection API
Processing job API
Detection database
Basic detection page
```

---

## Week 4

You:

```text
Verifier
Hard negatives
Shadow/context experiments
```

Member 2:

```text
GIS map
Detection detail
Reports
```

---

## Week 5

You:

```text
Calibration
Unknown handling
Challenge-slice testing
Geotagging validation
```

Member 2:

```text
Real-time connection
Review UI
Dashboard integration
```

---

## Week 6

Both:

```text
Connect AI → Backend → Database → Frontend
Run end-to-end testing
Freeze main model
ONNX/offline proof
Prepare demo
```

---

# 51. Definition of Done — Member 1

Your part is complete when:

```text
[ ] Real SSS data can be loaded
[ ] Dataset provenance exists
[ ] Labels are normalized
[ ] Leakage-safe split exists
[ ] YOLO11-N baseline measured
[ ] YOLO11-S measured
[ ] Preprocessing tested
[ ] Natural/artificial verification tested
[ ] Hard negatives tested
[ ] Shadow/context tested where supported
[ ] Confidence implemented
[ ] Calibration implemented if selected
[ ] Unknown handling works if implemented
[ ] Geotagging works where supported
[ ] Position error is handled honestly
[ ] Output JSON is frozen
[ ] Errors are structured
[ ] Model version is recorded
[ ] Evaluation report exists
[ ] Challenge slices measured
[ ] Local inference works
[ ] Integration sample works
```

---

# 52. Final Handoff Package

Deliver one folder:

```text
member1_handoff/
├── models/
│   └── main_model/
├── code/
├── configs/
├── sample_input/
├── sample_output/
├── schemas/
│   ├── input.json
│   ├── output.json
│   └── error.json
├── evaluation/
├── data_dictionary.md
├── integration.md
├── setup.md
└── limitations.md
```

---

# 53. Final Handoff README

Your `integration.md` must explain:

```text
1. How to install dependencies
2. How to load the model
3. How to call inference
4. What input is required
5. What output is returned
6. What happens when metadata is missing
7. What errors are returned
8. Model version
9. Preprocessing version
10. Example request
11. Example response
```

Member 2 should be able to integrate without guessing.

---

# 54. Final AI Output Example

Example only:

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
      "evidence_summary": {
        "artificial_verification": "positive",
        "shadow_context": "supportive"
      }
    }
  ]
}
```

Again: **example structure only. Use actual measured/model-derived values in production.**

---

# 55. Final Rule for Member 1

Your job is NOT:

> "Make a YOLO model."

Your job is:

> **Build a reliable, testable Side-Scan Sonar intelligence pipeline that turns real sonar data into trustworthy, structured detection information that Member 2 can directly use in the product.**

The critical chain is:

```text
REAL SSS DATA
→ CLEAN / VALIDATE
→ PREPROCESS
→ DETECT
→ VERIFY NATURAL vs ARTIFICIAL
→ CALIBRATE CONFIDENCE
→ HANDLE UNKNOWN
→ GEOTAG
→ STRUCTURED JSON
→ MEMBER 2
```

Do not fabricate data.

Do not fabricate metrics.

Do not claim precision the sonar metadata cannot support.

Do not change the output contract casually.

Build the AI/data layer so it can be connected to the same project later without rewriting it.
