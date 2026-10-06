# SIH26057 GhostNet-AI — Member 1 Complete Dataset Library
## Basic → Advanced | Download Sources | Roles | Verification Rules

> Use this as the practical dataset acquisition plan for the AI/ML member.
> No single public SSS dataset covers every SIH target class. Combine verified sources by role and preserve original labels/provenance.

## 1. Target problem
Target supported man-made objects include ghost/entangled fishing nets, shipwrecks, pipes, cylinders and other debris. The model also needs natural SSS backgrounds: rocks, sand ripples, ridges, shadows, noise and dropout regions.

## 2. Priority
- **P0:** directly useful for the initial SIH pipeline
- **P1:** strong supporting datasets
- **P2:** advanced robustness/pretraining/domain-generalization sources

---

## 3. P0 — GOMMDP (NOAA Gulf of Mexico Marine Debris Project)

### Why use it
NOAA's record describes more than 7,100 marine-debris items identified/mapped in over 1,500 square nautical miles of the northern Gulf of Mexico. The data include item location, dimensions, depth and type identified by sidescan sonar.

### Best use
- broad marine-debris reference
- debris type research
- GIS/geolocation schema
- dimensions/depth reference
- validation/reference for the marine-debris problem

### Critical limitation
This is primarily a marine-debris map/location/GIS accession, not a ready YOLO image/annotation dataset. Do **not** interpret 7,100 records as 7,100 labeled training images.

### Sources
NOAA NCEI:
https://www.ncei.noaa.gov/archive/archive-management-system/OAS/bin/prd/jquery/accession/details/176605

Data.gov:
https://catalog.data.gov/dataset/the-gulf-of-mexico-marine-debris-project-gommdp-debris-maps-and-locations-in-the-coastal-w

### Role
**P0 — broad marine-debris/geospatial reference**

---

## 4. P0 — Ghost Pot / GhostVision

### What it provides
Real Side-Scan Sonar imagery manually annotated for derelict crab pots ("ghost pots"). Current Hugging Face release reports 6,674 images and JSONL annotations.

### Best use
- fishing/ghost gear
- anthropogenic sonar targets
- real SSS detection
- related debris/gear experiments

### Critical limitation
A **ghost pot/crab pot is not a ghost net**. Never silently relabel crab pots as ghost nets.

### Sources
Zenodo:
https://zenodo.org/records/20056679

Hugging Face:
https://huggingface.co/datasets/PINGEcosystem/sss-crab-pot-detection-ds

### Role
**P0 — ghost/fishing gear-related data**

---

## 5. P0 — SubPipe

### What it provides
Real SSS submarine pipeline inspection data.

Reported release:
- 10,030 SSS images
- 6,335 object annotations
- 5,000 LF images
- 5,030 HF images
- COCO and YOLO annotations

### Best use
- pipe/pipeline
- object detection
- resolution/frequency variation
- sonar robustness
- inference/edge experiments

### Sources
Zenodo:
https://zenodo.org/records/12666132

GitHub:
https://github.com/remaro-network/SubPipe-dataset

### Download advice
Start with `SubPipeMini` or `SubPipeMini2` before the full archive.

### Role
**P0 — pipe + SSS detection**

---

## 6. P0 — AI4Shipwrecks

### What it provides
Real SSS shipwreck images with expert binary labels. The official record describes 286 high-resolution SSS images collected with an Iver3 AUV and EdgeTech 2205 dual-frequency SSS.

### Best use
- shipwreck detection
- segmentation
- object-detection conversion
- SSS preprocessing
- natural/background comparison
- anomaly-detection research

### Sources
University of Michigan Deep Blue:
https://deepblue.lib.umich.edu/data/concern/data_sets/8623hz41x

Project:
https://umfieldrobotics.github.io/ai4shipwrecks/

DOI:
https://doi.org/10.7302/dmf4-x492

### Role
**P0 — shipwreck + SSS background**

---

## 7. P1 — Marine-PULSE

### What it provides
Side-Scan Sonar engineering/seabed data. The Zenodo record reports:
- 323 pipeline/cable images
- 134 residual-mound images
- 88 seabed-surface images
- 82 engineering-platform images

### Best use
- pipe/cable
- engineering structures
- seabed/background
- cross-instrument/domain variation

### Sources
https://zenodo.org/records/7922705
https://doi.org/10.3390/rs15194873

### Role
**P1 — engineering/pipe/seabed support**

---

## 8. P1 — SeabedObjects Ship/Airplane

### What it provides
The repository reports 385 ship sonar images and 62 airplane sonar images.

### Best use
- additional artificial sonar objects
- domain diversity
- transfer-learning experiments
- natural-vs-artificial research

### Source
https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset

### Limitation
Do not relabel ship/airplane into ghost-net/pipe/cylinder.

### Role
**P1 — related artificial-object SSS data**

---

## 9. P2 — Large-Scale SSS Seafloor Sediments

### What it provides
A large SSS pretraining dataset. Current Zenodo record reports 434,164 384×384 patches covering many seafloor types such as rocky bottoms, sand ripples, mud, corals, vegetation and artificial reefs.

### Best use
- self-supervised pretraining
- natural seafloor learning
- background diversity
- natural-vs-artificial robustness

### Sources
https://zenodo.org/records/10209445

Tools:
https://github.com/DeeperSense/deepersense-seafloorscan

### Limitation
Not a ready ghost-net detector dataset.

### Role
**P2 — natural-background/pretraining**

---

## 10. P2 — BSH/PINTA SSS Data Hub

### What it provides
Real investigation-site SSS packages, including processed and sometimes raw SSS data, JSF files, GeoTIFF mosaics and target lists.

### Example sources
Portal: https://pinta.bsh.de — sites **O-1.3**, **N-3.8**, **N-3.5** (tab *Daten*).
(BSH's linking policy asks for the portal root, not a deep link.)

### Best use
- raw/processed SSS parser development
- natural/background data
- metadata/file-format experiments
- generalization testing

### Limitation
These are site investigation packages, not automatically annotated marine-debris training sets.

### Role
**P2 — raw/processed SSS research**

---

## 11. P2 — China Offshore SSS-AI

### What it provides
A multi-region SSS dataset for cross-regional seafloor target recognition. Current public Zenodo release reports 3,255 total images, a 3,241-image benchmark subset and a 967.3 MB public ZIP release.

### Best use
- cross-region robustness
- domain shift
- general SSS recognition
- external evaluation

### Sources
https://zenodo.org/records/20048164

Code:
https://github.com/Lorddu/China-Offshore-SSS-AI-code

### Limitation
Inspect the actual class schema before using any class as a GhostNet-AI target.

### Role
**P2 — domain generalization**

---

## 12. P2 — AquaScan-1K

### What it provides
A Side-Scan Sonar dataset with 1,000 images and human-target bounding boxes, collected over multiple depths/lakebed types/angles and frequencies.

### Best use
- general SSS detector pretraining
- robustness
- resolution/frequency experiments

### Limitation
Humans are not marine-debris labels.

### Source
https://zenodo.org/records/17628597

### Role
**P2 — general SSS robustness/pretraining**

---

## 13. P2 — OpenSonarDatasets

This is a discovery catalog, not a single dataset.

### Source
https://github.com/remaro-network/OpenSonarDatasets

Use it to find more open sonar datasets.

For every discovered source:
1. Open original source.
2. Verify SSS modality.
3. Verify license.
4. Inspect classes.
5. Inspect annotations.
6. Inspect metadata.
7. Record provenance.

### Role
**P2/P3 — dataset discovery**

---

# 14. Final Dataset Role Map

| Dataset | Main role | Direct ghost-net ground truth? |
|---|---|---|
| GOMMDP | Broad marine-debris/GIS reference | No |
| GhostVision/Ghost Pot | Fishing/ghost gear | No; crab pot ≠ ghost net |
| SubPipe | Pipe/pipeline | No |
| AI4Shipwrecks | Shipwreck + SSS background | No |
| Marine-PULSE | Pipe/cable/engineering/seabed | No |
| SeabedObjects | Ship/airplane sonar objects | No |
| Large SSS Seafloor | Natural background/pretraining | No |
| BSH/PINTA | Raw/processed SSS + natural data | No |
| China Offshore SSS-AI | Cross-region robustness | Check actual labels |
| AquaScan-1K | General SSS robustness | No |
| OpenSonarDatasets | Discovery catalog | N/A |

---

# 15. Ghost-Net Data Strategy

This is the hardest class.

Use:

```text
Real fishing/ghost-gear data
+
Natural SSS
+
Hard negatives
+
Synthetic/procedural ghost-net examples
+
Human review
```

Do not call crab-pot ground truth "ghost-net ground truth."

Evaluate any synthetic-data benefit using held-out real SSS.

---

# 16. "All Debris" Strategy

Do not blindly merge every dataset.

Create logical groups:

```text
marine_debris_reference/
shipwrecks/
pipes/
engineering/
fishing_gear/
natural_seafloor/
hard_negatives/
synthetic_ghost_net/
```

Preserve the source dataset and original class.

---

# 17. Class Mapping

Create:

```text
data/provenance/class_mapping.csv
```

Example:

```csv
source_dataset,source_class,target_class,decision
AI4Shipwrecks,shipwreck,shipwreck,accepted
SubPipe,pipeline,pipe,accepted
Marine-PULSE,pipeline,pipe,reviewed
GhostPot,crab_pot,ghost_pot,accepted_related
GhostPot,crab_pot,ghost_net,rejected
AquaScan-1K,human,human,rejected_from_debris_model
```

---

# 18. Dataset Inventory

Create:

```text
data/provenance/data_sources.csv
```

Recommended columns:

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
format
image_count
annotation_count
annotation_type
classes
resolution
frequency
metadata_available
gps_available
raw_log_available
role
selected_for_training
selected_for_validation
selected_for_test
notes
```

---

# 19. Download Procedure

For EVERY dataset:

```text
Original source
→ license
→ citation
→ small sample
→ verify SSS
→ inspect image format
→ inspect labels
→ inspect metadata/GPS
→ inspect resolution
→ run loader
→ record provenance
→ then download/use full data
```

Do not download huge archives before checking the structure.

---

# 20. Recommended First Download

Start with:

```text
1. AI4Shipwrecks
2. SubPipeMini2
3. Marine-PULSE
4. GhostVision/Ghost Pot
5. A natural SSS source
6. GOMMDP for debris/GIS reference
```

Then build:

```text
YOLO11-N baseline
```

Do NOT immediately download every P2 source.

---

# 21. Natural Background Bank

Build:

```text
natural_background/
├── rocks/
├── sand/
├── ripples/
├── ridges/
├── mud/
├── coral/geology/
└── other_seabed/
```

Only use labels supported by the actual source.

---

# 22. Hard-Negative Bank

Build:

```text
hard_negatives/
├── rock_as_pipe/
├── ridge_as_wreck/
├── shadow_as_net/
├── noise_as_debris/
└── dropout/
```

Track:

```text
source
wrong_prediction
correct_interpretation
model_version
reason
date_added
```

---

# 23. Real vs Synthetic Separation

Every sample should have:

```text
data_type = real
```

or:

```text
data_type = synthetic
```

Never leak synthetic samples into a real-world final test set.

---

# 24. Train / Validation / Test

Prefer survey/location-level separation:

```text
Survey A → train
Survey B → train
Survey C → validation
Survey D → final test
```

Do not split adjacent sonar frames from the same survey across train and test.

---

# 25. Cross-Dataset Testing

After the first model works, test generalization:

```text
Train source A+B
→ test source C
```

or use a completely unseen survey/location.

Report domain-shift results honestly.

---

# 26. Dataset Inspection Scripts

Create:

```text
scripts/inspect_dataset.py
scripts/visualize_samples.py
```

Inspection should report:

```text
total images
annotations
classes
image dimensions
corrupt files
missing labels
missing metadata
GPS availability
source distribution
```

Visual inspection should show:

```text
SSS image
+
ground truth
+
class
+
source
```

---

# 27. Dataset Versioning

Maintain:

```text
dataset_v1
dataset_v2
dataset_v3
```

Record:

```text
source list
sample counts
class mapping
annotation changes
train/val/test split
hard negatives
synthetic data
date
code version
```

Do not silently change the dataset between experiments.

---

# 28. Large Dataset Storage Guidance

Do not put giant datasets into the normal Git repository.

Git/GitHub should contain:

```text
source code
schemas
configs
scripts
documentation
small examples
```

Use appropriate storage for:

```text
raw sonar
large datasets
large model weights
processed corpora
```

---

# 29. Dataset Licensing

Before using a dataset in:

```text
public GitHub
model redistribution
public demo package
commercial deployment
```

re-check the original source license and attribution requirements.

Academic-use permission does not automatically mean unrestricted redistribution/commercial use.

---

# 30. Final Dataset Build

After baseline:

```text
Baseline
 ↓
False-positive analysis
 ↓
Natural background expansion
 ↓
Hard-negative mining
 ↓
Sonar-specific augmentation
 ↓
Ghost-net synthetic experiment
 ↓
Second-stage verification
 ↓
Confidence calibration
 ↓
Final held-out evaluation
```

---

# 31. Sources / Download Pages

## Marine debris / broad reference

GOMMDP — NOAA NCEI:
https://www.ncei.noaa.gov/archive/archive-management-system/OAS/bin/prd/jquery/accession/details/176605

GOMMDP — Data.gov:
https://catalog.data.gov/dataset/the-gulf-of-mexico-marine-debris-project-gommdp-debris-maps-and-locations-in-the-coastal-w

## Fishing / ghost gear

Ghost Pot/GhostVision — Zenodo:
https://zenodo.org/records/20056679

Ghost Pot/GhostVision — Hugging Face:
https://huggingface.co/datasets/PINGEcosystem/sss-crab-pot-detection-ds

## Pipe / engineering

SubPipe — Zenodo:
https://zenodo.org/records/12666132

SubPipe — GitHub:
https://github.com/remaro-network/SubPipe-dataset

Marine-PULSE — Zenodo:
https://zenodo.org/records/7922705

## Shipwreck

AI4Shipwrecks — Deep Blue:
https://deepblue.lib.umich.edu/data/concern/data_sets/8623hz41x

AI4Shipwrecks — Project:
https://umfieldrobotics.github.io/ai4shipwrecks/

AI4Shipwrecks — DOI:
https://doi.org/10.7302/dmf4-x492

## Additional sonar objects

SeabedObjects:
https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset

AquaScan-1K:
https://zenodo.org/records/17628597

China Offshore SSS-AI:
https://zenodo.org/records/20048164

China Offshore code:
https://github.com/Lorddu/China-Offshore-SSS-AI-code

## Natural / large SSS

Large-scale SSS seafloor:
https://zenodo.org/records/10209445

DeeperSense tools:
https://github.com/DeeperSense/deepersense-seafloorscan

BSH/PINTA examples — portal: https://pinta.bsh.de
(sites **O-1.3**, **N-3.8**, **N-3.5**; linking policy asks for the root, not a deep link)

## Discovery

OpenSonarDatasets:
https://github.com/remaro-network/OpenSonarDatasets

---

# 32. Final Recommendation

### Download/inspect first

```text
GOMMDP
GhostVision/Ghost Pot
SubPipeMini2
AI4Shipwrecks
Marine-PULSE
Natural SSS
```

### Add later when justified

```text
SeabedObjects
Large-scale SSS Seafloor
BSH/PINTA
China Offshore SSS-AI
AquaScan-1K
Other OpenSonarDatasets sources
```

### Ghost-net special path

```text
Ghost/fishing gear
+
real natural SSS
+
procedural/copy-paste ghost-net synthesis
+
hard negatives
```

Then validate on real held-out SSS.

---

# 33. Important Accuracy/Truthfulness Rule

Do not write:

> "We trained on 7,100 NOAA ghost-net images."

The NOAA GOMMDP record says more than 7,100 debris items were identified and mapped using sidescan sonar, but the accession is primarily maps/location/geographic data rather than 7,100 labeled object-detection images.

Say:

> "We use GOMMDP as a marine-debris and geospatial reference and combine directly annotated SSS datasets, natural-seafloor data, hard negatives and validated synthetic data for model training."

---

# 34. Final Dataset Definition

> **GhostNet-AI uses a multi-source Side-Scan Sonar corpus combining marine-debris references, shipwrecks, pipelines/engineering objects, fishing-gear-related targets, natural seafloor, hard negatives and—when required—synthetic ghost-net examples. Every sample keeps source, class and license/provenance information.**

The objective is not to collect the maximum number of images. It is to build a **relevant, diverse, correctly labeled, leakage-safe and provenance-preserving SSS dataset** for separating anthropogenic debris from natural seafloor.
