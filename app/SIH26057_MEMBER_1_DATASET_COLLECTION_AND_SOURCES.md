# SIH26057 — GhostNet-AI
# MEMBER 1 — DATASET COLLECTION, VERIFICATION & SOURCE PLAN

> Practical dataset starting point for Member 1.
>
> The goal is to find, verify, download, organize, and prepare **real Side-Scan Sonar (SSS)** data for the GhostNet-AI pipeline.
>
> **Important:** A related marine/sonar dataset is not automatically a ghost-net dataset. Never relabel an object merely to fit the problem statement.

---

# 1. Dataset Strategy

No single public dataset should be assumed to provide all of:

- Ghost nets
- Shipwrecks
- Pipes
- Cylinders
- Natural seafloor
- SSS metadata/GPS
- High-quality annotations

Use a multi-source strategy:

```text
                    FINAL SSS CORPUS
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    Shipwrecks          Pipes           Fishing/Ghost
        │               /Engineering         Gear
        └──────────────────┼──────────────────┘
                           ▼
                  Natural Seafloor
                           │
                           ▼
                    Hard Negatives
                           │
                           ▼
                  Synthetic Ghost Nets
                           │
                           ▼
                   Training / Testing
```

Preserve source/class provenance for every sample.

---

# 2. Priority 0 — Official SIH Resources

Before external sources, check the official SIH26057 materials for:

```text
SSS images
Raw sonar logs
Ping files
Coordinates
Metadata
Annotations
Reference samples
```

If official data exists and use is permitted, treat it as the primary benchmark.

Do not replace official test data with public data without documenting that difference.

---

# 3. Dataset 1 — AI4Shipwrecks

## What it provides

Real Side-Scan Sonar imagery of shipwrecks with expert binary segmentation labels.

The dataset contains **286 high-resolution SSS images**. It was collected during 2022–2023 in NOAA Thunder Bay National Marine Sanctuary using an Iver3 AUV equipped with an EdgeTech 2205 dual-frequency ultra-high-resolution side-scan sonar and a 3D bathymetric system.

## Use it for

```text
Shipwreck positives
Shipwreck segmentation
Natural/other background
SSS preprocessing
Anomaly-detection experiments
Object-detection experiments
```

## Do not use it as

```text
ghost_net labels
pipe labels
cylinder labels
```

unless the actual source annotations support those classes.

## Download / official source

Dataset:

https://deepblue.lib.umich.edu/data/concern/data_sets/8623hz41x

Project:

https://umfieldrobotics.github.io/ai4shipwrecks/

DOI:

https://doi.org/10.7302/dmf4-x492

License reported by the repository:

CC BY 4.0.

## Recommended role

```text
SHIPWRECK POSITIVE
+
NATURAL / OTHER SSS BACKGROUND
```

---

# 4. Dataset 2 — SubPipe

## What it provides

SubPipe is a Side-Scan Sonar dataset for submarine pipeline inspection.

Reported release contents:

```text
10,030 SSS images
5,000 low-frequency images
5,030 high-frequency images
6,335 object annotations
COCO annotations
YOLO annotations
```

Reported image sizes:

```text
LF: 2500 × 500
HF: 5000 × 500
```

## Use it for

```text
Pipeline detection
Object detection
Multi-resolution experiments
LF/HF variation
Training/inference pipeline testing
```

## Limitation

This is a **pipeline** dataset, not a ghost-net dataset.

Do not convert pipeline labels into ghost-net labels.

## Download / official source

https://zenodo.org/records/12666132

Available archives include:

```text
SubPipe.zip
SubPipeMini.zip
SubPipeMini2.zip
```

Start with a smaller archive if local storage/download time is limited.

## Recommended role

```text
PIPE POSITIVE
+
SSS DETECTION
+
MULTI-RESOLUTION DATA
```

---

# 5. Dataset 3 — Marine-PULSE

## What it provides

Marine-PULSE is a Side-Scan Sonar dataset focused on marine engineering structures.

The Zenodo record reports:

```text
323 pipeline/cable images
134 underwater residual mound images
88 seabed-surface images
82 engineering-platform images
```

The data includes multiple SSS instruments.

## Use it for

```text
Pipeline/cable examples
Engineering structures
Seabed/background
Cross-instrument/domain variation
Classification/transfer-learning experiments
```

## Limitation

Do not relabel engineering structures as ghost nets.

## Download / official source

https://zenodo.org/records/7922705

Paper:

https://doi.org/10.3390/rs15194873

## Recommended role

```text
PIPE / CABLE
+
ENGINEERING STRUCTURES
+
NATURAL SEABED
+
DOMAIN DIVERSITY
```

---

# 6. Dataset 4 — Ghost Pot / GhostVision

## What it provides

Real SSS imagery manually annotated for **derelict crab pots ("ghost pots")** from Delaware's Inland Bays and Delaware Bay.

It is specifically designed around automated detection of derelict fishing gear.

## Use it for

```text
Ghost/fishing gear related detection
Marine anthropogenic gear
Transfer learning
Related debris experiments
Hard-negative/related-object experiments
```

## Critical limitation

A:

```text
derelict crab pot
```

is NOT:

```text
ghost net
```

Therefore:

```text
ghost_pot → ghost_pot
```

is valid.

```text
ghost_pot → ghost_net
```

is NOT valid unless you have a defensible relabeling procedure and independent ground truth.

## Download / source

https://zenodo.org/records/20056679

## Recommended role

```text
GHOST GEAR / FISHING GEAR
```

This is the closest currently verified public source in this stack to the fishing-gear portion of your problem, but it is not a ghost-net ground-truth set.

---

# 7. Dataset 5 — SeabedObjects Ship/Airplane

## What it provides

The repository reports:

```text
385 ship sonar images
62 airplane sonar images
```

and describes the dataset as real sidescan sonar imagery, with academic-use wording in the repository.

## Use it for

```text
Large artificial sonar objects
Sonar appearance diversity
Transfer learning
Natural-vs-artificial experiments
```

## Limitation

Do not rename ship/airplane labels into ghost-net, pipe, or cylinder.

## Download / source

https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset

## Recommended role

```text
RELATED ARTIFICIAL OBJECTS
+
DOMAIN DIVERSITY
```

---

# 8. Dataset 6 — FLSMDD / Marine Debris Sonar References

A research repository used in sonar-image experiments references FLSMDD and related sonar datasets.

Use this as a **secondary lead**, not as an automatically approved training source.

## Investigate it for

```text
Marine-debris sonar data
Classification
Transfer learning
Domain diversity
```

## Before using it

Verify the original source for:

```text
exact modality
license
classes
annotations
download source
```

Do not assume a derivative repository has redistribution rights for the original data.

## Reference

https://github.com/Jorwnpay/TGRS_BETL

---

# 9. Dataset 7 — AquaScan-1K

## What it provides

AquaScan-1K is a real Side-Scan Sonar dataset with:

```text
1,000 high-resolution SSS images
single class: human
bounding boxes
multiple depths
multiple lakebed types
multiple scanning angles
455–1075 kHz operating frequencies
```

## Use it for

```text
General SSS object detection
Low-contrast target experiments
Resolution robustness
Domain/generalization experiments
```

## Limitation

Do NOT use human labels as marine-debris labels.

## Source / download

https://zenodo.org/records/17628597

---

# 10. Dataset 8 — Healy Submarine Volcano SSS Data

## What it provides

This repository contains:

```text
Side-scan sonar mosaics
Geological structures
Bathymetry
Selected images/video
```

## Use it for

```text
Natural seafloor
Geological texture
Natural anomalies
Hard negatives
Background diversity
```

## Limitation

Geological structures are not automatically anthropogenic debris.

## Source / download

https://zenodo.org/records/19000370

---

# 11. OpenSonarDatasets — Discovery Catalog

This is a **dataset discovery catalog**, not one dataset.

Use it to find additional open sonar datasets:

https://github.com/remaro-network/OpenSonarDatasets

For every newly discovered dataset:

```text
Open original source
→ verify SSS modality
→ verify license
→ inspect labels
→ inspect metadata
→ record provenance
```

Do not treat the catalog entry alone as license verification.

---

# 12. Final Dataset Role Map

| Dataset | Main role | Ghost-net ground truth? |
|---|---|---|
| AI4Shipwrecks | Shipwreck + SSS background | No |
| SubPipe | Pipeline/object detection | No |
| Marine-PULSE | Pipeline/cable + engineering + seabed | No |
| Ghost Pot/GhostVision | Derelict crab pots / fishing gear | No, not directly |
| SeabedObjects | Ship/airplane sonar objects | No |
| FLSMDD lead | Marine-debris-related experiments | Only if source labels support it |
| AquaScan-1K | General SSS detection robustness | No |
| Healy | Natural/geological SSS | No |

---

# 13. What We Need for the Ghost-Net Class

The problem specifically mentions entangled debris nets.

Do not claim the Ghost Pot dataset solves that class.

Use:

```text
Related real fishing-gear data
+
Natural SSS backgrounds
+
Synthetic/procedural ghost-net examples
+
Hard-negative mining
+
Human review
```

Then evaluate against real held-out data whenever available.

---

# 14. Recommended First Download Set

## Start with these four

```text
1. AI4Shipwrecks
2. SubPipe
3. Marine-PULSE
4. Ghost Pot / GhostVision
```

Then add:

```text
5. SeabedObjects
6. Natural/geological SSS
7. FLSMDD if independently verified
8. AquaScan-1K if useful for robustness
```

Do not download every dataset before testing the pipeline.

---

# 15. Download Procedure

For EVERY dataset:

```text
1. Open original/official source
2. Read license
3. Check citation requirements
4. Download a small sample
5. Confirm it is actually SSS
6. Inspect image format
7. Inspect annotation format
8. Inspect classes
9. Inspect metadata/GPS
10. Check image dimensions/resolution
11. Record provenance
12. Test loading
13. Only then download/integrate the full set
```

---

# 16. Dataset Inventory

Create:

```text
data/provenance/data_sources.csv
```

Recommended fields:

```text
dataset_id
dataset_name
source_url
doi
paper_url
download_date
license
citation_required
sonar_modality
sonar_instrument
image_format
image_count
annotation_count
annotation_type
classes
resolution
frequency
metadata_available
gps_available
raw_log_available
commercial_use
research_use
selected_for_training
selected_for_validation
selected_for_test
role
notes
```

---

# 17. Class Mapping

Create:

```text
data/provenance/class_mapping.csv
```

Example:

```text
source_dataset,source_class,target_class,decision
AI4Shipwrecks,shipwreck,shipwreck,accepted
SubPipe,pipeline,pipe,accepted
GhostPot,crab_pot,ghost_pot,accepted_related
GhostPot,crab_pot,ghost_net,rejected
```

This prevents accidental false labels.

---

# 18. Provenance Per Sample

Every normalized sample should preserve:

```text
dataset_id
original_filename
original_class
normalized_class
source_path
license/source reference
```

Example:

```json
{
  "dataset_id": "SUBPIPE",
  "original_filename": "img_00123.png",
  "original_class": "pipeline",
  "normalized_class": "pipe"
}
```

---

# 19. Dataset Folder Structure

```text
data/
├── raw/
│   ├── ai4shipwrecks/
│   ├── subpipe/
│   ├── marine_pulse/
│   ├── ghost_pot/
│   └── other_verified/
│
├── metadata/
├── annotations/
├── processed/
│   ├── train/
│   ├── val/
│   └── test/
│
├── hard_negatives/
├── synthetic/
│   └── ghost_net/
└── provenance/
    ├── data_sources.csv
    └── class_mapping.csv
```

---

# 20. Natural / Artificial Groups

Use explicit logical groups:

```text
artificial/
├── shipwreck/
├── pipe/
├── cylinder/
└── other_supported/

natural/
├── rocks/
├── ripples/
├── ridges/
├── seabed/
└── geological/

related_fishing_gear/
└── ghost_pot/

synthetic/
└── ghost_net/
```

Only create a class if the actual labels/data justify it.

---

# 21. Hard-Negative Bank

Create:

```text
hard_negatives/
├── rock/
├── ridge/
├── shadow/
├── noise/
├── dropout/
└── other_false_positive/
```

For each sample record:

```text
source
false_positive_class
model_version
reason
date_added
```

Example:

```text
Rock falsely detected as pipe
```

---

# 22. Dataset Splitting

Avoid:

```text
Frame 100 → train
Frame 101 → test
```

when frames are consecutive from the same survey.

Prefer:

```text
Survey A → train
Survey B → train
Survey C → validation
Survey D → final test
```

Use unseen survey/location data for the final evaluation whenever possible.

---

# 23. Real vs Synthetic

Keep metadata separating:

```text
REAL
SYNTHETIC
```

Never allow synthetic images into the real-world test set by accident.

---

# 24. Synthetic Ghost-Net Experiment

When real ghost-net labels are insufficient:

```text
Real natural SSS
+
synthetic ghost-net object
→ training sample
```

Possible methods:

```text
Procedural/copy-paste
or
validated generative method
```

Then measure:

```text
WITHOUT synthetic → F1 = A
WITH synthetic     → F1 = B
```

on held-out real data.

Never use synthetic-only evaluation to claim real-world performance.

---

# 25. Dataset Inspection Script

Create:

```text
scripts/inspect_dataset.py
```

It should report:

```text
total images
total labels
class counts
images without labels
labels without images
image dimensions
corrupt files
duplicate filenames
missing metadata
GPS availability
```

Write:

```text
reports/dataset_audit.json
```

---

# 26. Dataset Visualization Script

Create:

```text
scripts/visualize_samples.py
```

Show:

```text
SSS image
+
ground-truth annotation
+
class
+
dataset source
```

Manually inspect representative examples before training.

---

# 27. Dataset Integrity

For important source archives/files record:

```text
filename
size
SHA256
source
download date
```

This helps reproduce the training corpus later.

---

# 28. License Rules

Before placing data into:

```text
GitHub
trained model release
public demo package
commercial deployment
```

re-check the original license and attribution conditions.

Academic-use permission does not automatically mean unrestricted commercial redistribution.

---

# 29. What NOT to Use as Main Training Data

Avoid unrelated:

```text
underwater RGB photos
fish image datasets
normal underwater video
generic object datasets
```

unless you have a clearly documented transfer-learning or robustness reason.

The core task is **Side-Scan Sonar interpretation**.

---

# 30. First Training Dataset

Start with:

```text
AI4Shipwrecks
+
SubPipe
+
Marine-PULSE
+
Ghost Pot
+
natural/background SSS
```

Normalize only the classes that are defensible.

Then:

```text
YOLO11-N
→ baseline
→ metrics
→ false-positive analysis
```

---

# 31. Expansion After Baseline

Use the measured errors to decide what to add:

```text
Baseline
 ↓
False positives
 ↓
Hard negatives
 ↓
Natural background expansion
 ↓
Sonar-specific augmentation
 ↓
Ghost-net synthetic experiment
 ↓
Second-stage verification
 ↓
Calibration
 ↓
Final held-out test
```

---

# 32. What Member 2 Needs From Member 1

Member 2 does not need the complete training corpus.

Give:

```text
sample_input/
sample_output/
class_schema.json
ai-output.schema.json
metadata_example.json
```

Member 2 calls the AI service; the frontend/backend should not depend on training-data locations.

---

# 33. Dataset Acceptance Checklist

A dataset is accepted only after:

```text
[ ] Original source identified
[ ] License verified
[ ] Citation recorded
[ ] Genuine SSS confirmed
[ ] Classes inspected
[ ] Annotation format inspected
[ ] Annotation quality inspected
[ ] Resolution recorded
[ ] Metadata inspected
[ ] GPS availability recorded
[ ] Duplicate/leakage risk checked
[ ] Provenance recorded
[ ] Intended role assigned
```

---

# 34. Recommended Immediate Action

Do this in order:

```text
DAY 1
↓
Open AI4Shipwrecks
Open SubPipe
Open Marine-PULSE
Open Ghost Pot
↓
Read source/license pages
↓
Download only small samples
↓
Inspect structure
↓
Fill data_sources.csv
↓
Create class_mapping.csv
↓
Test loaders
↓
Only then download full data
```

---

# 35. Sources / Download Links

## Primary sources

### AI4Shipwrecks
https://deepblue.lib.umich.edu/data/concern/data_sets/8623hz41x

Project:
https://umfieldrobotics.github.io/ai4shipwrecks/

DOI:
https://doi.org/10.7302/dmf4-x492

### SubPipe
https://zenodo.org/records/12666132

### Marine-PULSE
https://zenodo.org/records/7922705

DOI:
https://doi.org/10.3390/rs15194873

### Ghost Pot / GhostVision
https://zenodo.org/records/20056679

## Secondary sources

### SeabedObjects
https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset

### FLSMDD research reference
https://github.com/Jorwnpay/TGRS_BETL

### AquaScan-1K
https://zenodo.org/records/17628597

### Healy submarine volcano SSS data
https://zenodo.org/records/19000370

### OpenSonarDatasets
https://github.com/remaro-network/OpenSonarDatasets

---

# 36. Final Dataset Definition

For this project, the final training corpus should be described honestly as:

> **A multi-source Side-Scan Sonar corpus combining real shipwreck, pipeline/engineering, fishing-gear-related, natural-seafloor, and hard-negative data, with synthetic ghost-net examples added only where necessary and evaluated against real held-out data. Every sample retains its original source and label provenance.**

Do not call it a "ghost-net dataset" unless the ground-truth labels actually represent ghost nets.

---

# 37. Final Rule

**Find → verify → license → inspect → map classes → normalize → split safely → train baseline → analyze errors → expand.**

Do not:

```text
Download everything
→ rename classes
→ merge blindly
→ train
→ claim accuracy
```

The dataset is the foundation of the entire GhostNet-AI system.
