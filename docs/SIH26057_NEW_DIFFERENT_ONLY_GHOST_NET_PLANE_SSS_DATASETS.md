# SIH26057 — NEW / DIFFERENT-ONLY SSS DATA SOURCES
## Ghost Net + Plane/Aircraft | Sources intentionally not repeated from the previously implemented master library

### Purpose

This file is a **new-only dataset/source pack**.

It is deliberately focused on sources I found in the latest search that were **not already present under the same source/project name in your current master file**.

It includes:
- exact plane/aircraft sonar sources
- ghost-net / fishing-net research leads
- huge unlabeled SSS pools
- raw XTF/JSF repositories
- rare aircraft archives
- research datasets
- public image-only sources
- private/request targets
- hard-negative sources
- data that can be converted into your own labels

It does **not** repeat the already-implemented common sources such as GhostVision, GhostNetZero, DFO, CSR, SeabedObjects/KLSG, KLSG-II, SonarVision, NOAA B-29, UB88, TBM Avenger, Stockton, Salish, GGGI PNW, etc.

---

# 1. TOP NEW SOURCES

| Rank | New source | Target/use | Data type | Approx. scale | Priority |
|---|---|---|---|---:|---:|
| ★★★★★ | Deep Learning for Detection of Underwater Aircraft Wrecks from US Conflicts | **Plane** | real SSS + labels | 19 aircraft / 290 labeled fragments | VERY HIGH |
| ★★★★★ | DeeperSense SeafloorScan | Unlabeled SSS / hard negatives | real SSS | **434,164 images** | VERY HIGH |
| ★★★★★ | BSH/PINTA N-09 / N-03 raw JSF sites | Unlabeled/raw SSS | raw JSF + processed targets | tens/hundreds GB | VERY HIGH |
| ★★★★★ | China Offshore SSS-AI | SSS domain-shift / hard negatives | image-only SSS | **3,255 chips** | HIGH |
| ★★★★☆ | AquaScan-1K | small-object sonar robustness | labeled SSS | **1,000 images** | HIGH |
| ★★★★☆ | Portuguese Navy/Gavia mine SSS | hard negatives / sonar transfer | labeled SSS | **1,170 real images** | HIGH |
| ★★★★☆ | USGS Grand Bay 2015-315-FA | raw SSS + background | raw Klein XTF | survey archive | HIGH |
| ★★★★☆ | MH370 Phase 2 | huge search/marine sonar domain | SSS/SAS/MBES | 5 m resolution survey products | HIGH |
| ★★★★☆ | Taganrog Bay fishing-net study | **Ghost Net** | real SSS images | image-only/research | HIGH |
| ★★★☆☆ | Jiaozhou Bay fishing-net segmentation source | **Ghost Net** | research dataset lead | fishing-net SSS | HIGH |
| ★★★☆☆ | Sciacca aircraft wreck | **Plane** | real SSS image | 1 rare aircraft case | MEDIUM |
| ★★★☆☆ | Seabee RC3 image archive | **Plane** | real SSS image | rare aircraft | MEDIUM |
| ★★★☆☆ | Project Recover 2026 SSS program | **Plane** | field survey + images | ongoing/private/research | HIGH |
| ★★★☆☆ | VIMS Chesapeake archive | Ghost gear | SSS images + field data | historical multi-year | MEDIUM |

---

# 2. PLANE / AIRCRAFT — THE MOST IMPORTANT NEW SOURCE

## 2.1 Deep Learning for Detection of Underwater Aircraft Wrecks from US Conflicts

Paper:
https://journal.caa-international.org/articles/179

PDF:
https://journal.caa-international.org/articles/179/files/681b372b2fb05.pdf

GitHub/code:
https://github.com/leiladcharacter/DL_Underwater_ACW

### Why this is different and extremely valuable

The 2025 study reports a training dataset assembled from archival and newly collected high-resolution side-scan sonar across **six countries**.

The published table gives:

| Location | Aircraft | Labeled aircraft-wreck pieces |
|---|---:|---:|
| Chuuk, Micronesia | 9 | 158 |
| Croatia | 6 | 128 |
| Maloelap, Marshall Islands | 1 | 1 |
| Denmark | 1 | 1 |
| Alaska | 1 | 1 |
| Palau | 1 | 1 |
| **TOTAL** | **19** | **290** |

Most aircraft were imaged using **600 and 1200 kHz** side-scan sonar.

The dataset covers approximately **180 km²** of survey area, with training/validation image generation from 10-cm-resolution sonar data. The paper reports 810 training images and 52 validation images created from 3.5 km² of imagery.

### Critical discovery

The authors explicitly state that the data are **not publicly available** because the work involves searching for aircraft that may contain human remains.

That makes it a **private/restricted research-data lead**, not a normal download.

### Your move

Contact the corresponding author:

`leilacharacter@shsu.edu`

Ask for:
- anonymized aircraft sonar tiles
- training-only subset
- non-sensitive aircraft fragments
- test images without exact location
- labels without geolocation
- derivative 640×640 images if raw data cannot be shared

### Why this can outperform KLSG

This source has:
- 19 unique aircraft
- six countries
- 600/1200 kHz
- heavily disarticulated wrecks
- partial debris
- real field test data
- geographic shift

This is exactly the kind of diversity needed for your `plane` class.

---

# 3. DEEPERSENSE — MASSIVE UNLABELED SSS DATA

## 3.1 A Large Scale Side-Scan Sonar Dataset of Seafloor Sediments for Self-Supervised Pretraining

Zenodo:
https://zenodo.org/records/10209445

GitHub tools:
https://github.com/DeeperSense/deepersense-seafloorscan

### Scale

**434,164 SSS images**

Image size:
**384 × 384**

The patches were made from SSS waterfalls with **192-pixel overlap**.

The source survey was collected along the coast of Catalunya.

### Contents

Examples of seafloor types:
- rocky bottom
- sand ripples
- detrital funds
- Posidonia
- Cymodocea
- mud
- coral
- artificial reefs

### File size

The current Zenodo package is distributed as split ZIP volumes totaling about **52.3 GB** for the visible package, while the repository metadata reports a much larger overall data volume.

### Why you should use it

This is not a plane/ghost-net dataset.

That is exactly why it is useful.

Use it as:

```text
434k real SSS backgrounds
        ↓
self-supervised pretraining
        ↓
domain adaptation
        ↓
hard-negative mining
        ↓
ghost-net / plane detector
```

### Best use for your model

Pretrain an SSS encoder on this before supervised fine-tuning.

Possible strategies:
- SimCLR
- MoCo
- BYOL
- MAE
- DINO-style feature learning

Or simply use the images for:
- seabed false-positive testing
- anomaly detection
- calibration stress tests

---

# 4. BSH / PINTA NEW RAW DATA TARGETS

These are real survey-scale raw sonar files and should be treated differently from small image datasets.

## 4.1 PINTA N-09.1/N-09.2/N-09.3/N-09.4

Example:
https://pinta.bsh.de/N-9.1?lang=en&tab=daten

The archive exposes raw SSS in **JSF** plus processed SSS and target lists.

Example raw packages:
- N-09-01 Part 1: **140.7 GB**
- N-09-01 Part 2: **74.8 GB**
- N-09-02 Part 1: **96.0 GB**
- N-09-02 Part 2: **75.5 GB**
- N-09-03 Part 1: **123.5 GB**
- N-09-03 Part 2: **64.7 GB**
- N-09-04 Part 1: **64.7 GB**
- N-09-04 Part 2: **122.8 GB**

Processed packages include:
- SSS result maps
- PDF sediment maps
- contact overviews
- waterfall target lists
- comparison against multibeam data
- material used for later ROV investigation

### Why this matters

The real value is:

```text
RAW JSF
  +
PROCESSED SSS
  +
TARGET LIST
  +
ROV-COMPARISON INFORMATION
```

This can support:
- self-supervised learning
- anomaly detection
- hard-negative creation
- target candidate mining
- sonar metadata parsing
- raw-to-image conversion research

### Do not download everything

Use the processed target lists first.

Then:

```text
target-rich site
    ↓
target coordinates
    ↓
select corresponding JSF lines
    ↓
process only those
```

---

# 5. PINTA N-03.6 / N-03.5 NEW SOURCE

Example:
https://pinta.bsh.de/N-3.6?lang=en

The site provides:
- processed SSS
- raw SSS
- JSF
- measurement protocol
- target list
- multibeam comparison

This is another independent survey package that can serve as a different-domain SSS pool.

---

# 6. USGS GRAND BAY — RAW KLEIN XTF

USGS CMGDS:
https://cmgds.er.usgs.gov/services/cmgds-dataset.php?id=38005

DOI:
https://doi.org/10.5066/P9374DKQ

Dataset:
`2015-315-FA_xtf.zip`

### Data

The archive is described as:

**unprocessed Klein SonarPro XTF data files**

Survey:
`2015-315-FA`

Equipment:
**Klein side-scan sonar**

Contact listed by USGS:
**Arnell S. Forde**

### Why valuable

This is a genuine raw SSS example rather than a screenshot dataset.

Use it for:
- raw-file parser testing
- image reconstruction
- background training
- sonar artifact augmentation
- metadata extraction
- edge inference stress tests

### Jugaad

Instead of looking for:

```text
ghost-net.jpg
```

you can use raw XTF:

```text
XTF
 ↓
sonar processing
 ↓
waterfall image
 ↓
automatic candidate detector
 ↓
manual review
```

That is exactly the direction your SIH pipeline requires.

---

# 7. CHINA OFFSHORE SSS-AI

Zenodo v2:
https://zenodo.org/records/20048164

### Scale

**3,255 cropped SSS image chips**

Recommended benchmark:
**3,241 images**

14 release-only images are retained outside the main benchmark because of rare/underpopulated source-region classes.

### Geographic sectors

The dataset represents Chinese marginal-sea sectors including:
- Bohai Sea
- Yellow Sea
- Taiwan Strait
- northern South China Sea

### Package

- image pixels
- file-level metadata
- class mappings
- benchmark split
- quality-control records
- metadata dictionary

It does NOT provide:
- raw SSS
- precise coordinates
- survey-line IDs
- sensitive project metadata

### Why use

This is a strong geographic-domain test.

Your model can train mostly on existing Western datasets and test:

```text
China coastal SSS
```

That gives you an excellent **cross-region generalization experiment**.

---

# 8. AQUASCAN-1K

Zenodo:
https://zenodo.org/records/17628597

### Scale

**1,000 high-resolution real SSS images**

### Target

Human search-and-rescue surrogate.

### Acquisition

- 455–1075 kHz
- multiple depths
- different lakebed types
- multiple scanning angles
- expert bounding-box annotations

### Why include it

Not a ghost-net/plane dataset.

Use it as:

```text
small-object sonar pretraining
low-contrast target benchmark
multi-frequency robustness
hard-negative source
```

The targets are intentionally small/low-contrast, which is useful for your confidence/uncertainty layer.

---

# 9. PORTUGUESE NAVY / GAVIA MINE SSS DATASET

Figshare:
https://figshare.com/articles/dataset/_i_Side-scan_sonar_imaging_for_Mine_detection_i_/24574879

DOI:
10.6084/m9.figshare.24574879.v2

### Scale

**1,170 real sonar images**

Collected between:
**2010–2021**

Platform:
**Teledyne Marine Gavia AUV**

SSS:
**900–1800 kHz**

Labels:
- MILCO
- NOMBO

### Why include

Again, not plane/net.

Use as a hard-negative pool for:
- small acoustic objects
- mine-like shapes
- unknown-object detector
- object-vs-seabed classification
- uncertainty estimation

The repository says the archive is publicly downloadable.

---

# 10. MH370 PHASE 2 SONAR VISUALISATION DATA

Australian Research Data:
https://researchdata.edu.au/the-search-flight-images-visualisation/

### Why it is interesting

This comes from the **Phase 2 search for Flight MH370**.

The dataset provides sonar information at **5 m resolution** from marine surveys conducted by:
- Australia
- Malaysia
- People's Republic of China

Survey systems include:
- Kongsberg Hugin 1000 / Echo Surveyor 7
- EdgeTech 2400 Deep Tow
- SLH PS-60 Synthetic Aperture Sonar

Modalities include:
- Side Scan Sonar
- Synthetic Aperture Sonar
- multibeam backscatter

### Use

Not a labeled aircraft dataset.

Use it for:
- massive-area search-domain imagery
- hard negatives
- unknown-object detection
- search-pattern simulation
- large-scale sonar domain shift

### Rights

The repository states that copyright applies and gives a specific attribution statement for reuse.

---

# 11. TAGANROG BAY — REAL FISHING-NET SSS

Paper:
https://izv.etu.ru/en/archive/2021/3/10-16

### Target

**Fishing nets in the water column**

### Location

**Taganrog Bay, Russia**

### Data

The study reports that researchers from Southern Federal University and LLC NOLACS conducted experiments in 2017 and presented several acoustic images of fishing nets.

The paper provides:
- SSS imaging methodology
- sonar characteristics
- acoustic-shadow discussion
- several fishing-net sonar examples

### Why it matters

This is one of the few sources focused on **actual fishing nets**, rather than traps.

### Status

`IMAGE_ONLY / RESEARCH REQUEST`

The source should be treated as a lead to obtain the original data and/or high-resolution figures from the authors.

---

# 12. JIAOZHOU BAY — FISHING-NET SEGMENTATION SOURCE

Paper:
https://www.sciencedirect.com/science/article/abs/pii/S0141118721000857

### Target

**Fishing nets**

### Dataset family

The paper explicitly says it evaluated segmentation on:
- sand waves
- coral reefs
- **fishing nets**

It discusses an SSS fishing-net dataset in addition to the other seabed datasets.

### Why important

This is a rare source specifically showing:

```text
SSS fishing net
+
pixel/segmentation problem
```

rather than only object classification.

### Jugaad

Use the paper to locate:
- supplementary material
- corresponding author
- institutional dataset
- source laboratory
- image figures

Do not count augmented patches as independent field images.

---

# 13. SCIACCA AIRCRAFT WRECK — ITALY

ISPRA:
https://www.isprambiente.gov.it/en/archive/news-and-other-events/ispra-news/2023/04/plane-wreck-on-the-seabed-off-sciacca

Direct image:
https://www.isprambiente.gov.it/en/archive/news-and-other-events/ispra-news/2023/04/plane-wreck-on-the-seabed-off-sciacca/@@download/image/relitto.jpg

### Details

University of Palermo researchers detected an apparent aircraft wreck about:

**20 m long**

approximately **7.5 nautical miles from Sciacca** during a 2023 oceanographic campaign.

The target was detected using **Side Scan Sonar**.

### Why use

This is a rare real aircraft sonar example outside the common KLSG/NOAA family.

Recommended class:
```text
plane
```

Recommended label:
`weak/manual`

---

# 14. SEABEE RC3 — QUEBEC

ShipwreckWorld:
https://www.shipwreckworld.com/articles/side-scan-sonar-images

Specific image page:
https://www.shipwreckworld.com/articles/gallery/40/110/

### Target

**Seabee RC3 aircraft wreck**

Location:
**Lac Simon, Quebec, Canada**

The archive describes the aircraft as a 1958 loss and provides its wreck image.

### Why interesting

Different from:
- WWII Pacific aircraft
- deep-ocean aircraft
- KLSG benchmark imagery

Use it for:
- freshwater aircraft domain
- rare aircraft shape
- weak/manual label
- external holdout

---

# 15. PROJECT RECOVER — A MAJOR NEW PLANE DATA LEAD

Project Recover:
https://www.projectrecover.org/side-scan-sonar/

### Current 2026 source

Project Recover's June 22, 2026 article describes its current use of SSS to find WWII and other conflict aircraft.

Important details:
- searches can cover extremely large areas
- AUVs maintain constant altitude over the bottom
- accurate navigation allows geolocation
- they use **two passes and two frequencies**
- low frequency for large-area search
- high frequency for detailed follow-up
- SSS candidates are confirmed with SCUBA or ROV

### Why this is extremely useful

This is not just a historical image archive.

It is an **active real-world aircraft-search operation**.

Their workflow is:

```text
LOW-FREQUENCY WIDE SEARCH
          ↓
candidate anomalies
          ↓
HIGH-FREQUENCY RE-SCAN
          ↓
human/AI review
          ↓
SCUBA / ROV confirmation
```

This is almost identical to the architecture you need.

### Important

Project Recover does not state that its raw operational data is publicly downloadable.

Treat it as:
`RESEARCH / PRIVATE DATA / COLLABORATION LEAD`

Do not assume they will release human-remains-sensitive data.

---

# 16. PROJECT RECOVER CHUUK — MORE AIRCRAFT CASES

2019 Annual Report:
https://www.projectrecover.org/wp-content/uploads/2020/06/2019-Project-Recover-Annual-Report-v3-web.pdf

The report documents:
- multiple Chuuk missions
- REMUS 100
- side-scan sonar
- SBD-5
- TBM/F-1C
- Japanese aircraft
- unknown aviation debris

It specifically describes a previously unknown sonar anomaly that was reacquired by SSS and then investigated by divers.

### Why use

This is valuable **weak-label ground-truth history**.

A source record can be structured as:

```json
{
  "target_class": "plane",
  "label_type": "field_verified",
  "source": "Project Recover",
  "region": "Chuuk",
  "confirmation": "diver/ROV"
}
```

---

# 17. PROJECT RECOVER PALAU — AIRCRAFT + SONAR + MAP

Project Recover:
https://www.projectrecover.org/mission-16-project-recover-locates-hellcat-avenger-palau/

The project page describes:
- current side-scan sonar file
- historical Japanese map
- Google Earth overlay
- aircraft debris field
- fuselage
- flap
- landing gear
- missing wing
- aviation confirmation

### Use

This is unusually useful for your GIS requirement because it connects:

```text
SONAR
+
HISTORICAL MAP
+
GEOGRAPHY
+
AIRCRAFT TARGET
```

Potential source of:
- weak labels
- target coordinates
- map overlay ideas
- external validation case

---

# 18. BALTIC / POLAND AIRCRAFT WRECK — FULL DATA QUALITY VARIANTS

Paper:
https://www.mdpi.com/2072-4292/14/20/5195

### What makes this source different

It contains multiple SSS quality conditions for the same aircraft.

Examples include:
- sonar too low
- sonar too high
- sonar too far
- incomplete acoustic shadow
- good-quality target
- different track-line orientations
- 40 m range
- 30 m range
- different towfish heights
- different views of the same wreck

The wreck was also inspected using:
- scanning sonar
- ROV

### Why this is extremely useful

Instead of simple:

```text
plane / not-plane
```

you get:

```text
GOOD
BAD-GEOMETRY
PARTIAL
SHADOW-MISSING
HIGH-ALTITUDE
LOW-ALTITUDE
```

This is excellent for your:
- confidence model
- uncertainty model
- data-quality classifier
- hard-negative bank

---

# 19. SHIPWRECKWORLD SIDE-SCAN SONAR IMAGE ARCHIVE

Main:
https://www.shipwreckworld.com/articles/side-scan-sonar-images

It includes named sonar-image subjects, including:
- Seabee aircraft wreck
- Great Lakes wrecks
- human-body target
- other underwater objects

### Use

This is an **archive mining source**, not a standardized ML dataset.

Workflow:

```text
archive image
 ↓
read title/caption
 ↓
class = plane / wreck / background
 ↓
manual annotation
 ↓
license verification
```

---

# 20. VIMS / CHESAPEAKE HISTORICAL GHOST-GEAR IMAGE SOURCE

VIMS:
https://www.vims.edu/newsandevents/topstories/archives/2009/ghost_pot_watermen.php

Scientific Reports:
https://www.nature.com/articles/srep19671

### Historical sonar evidence

The VIMS program used side-imaging sonar to locate submerged derelict crab pots.

A VIMS page provides a side-scan image showing:
- three derelict crab pots
- sonar survey track
- actual recovery context

It reports that a 2006–2007 survey found **more than 600 derelict pots in the mouth of the York River**, and that the broader program recovered thousands of pots.

The 2008–2014 Chesapeake program is also documented as generating scientific data and sonar-supported removal.

### Why useful

Not a modern YOLO dataset.

It gives you:
- historical SSS appearance
- old sonar hardware conditions
- real ghost-gear morphology
- recovery validation
- water/environment variation

Use as `weak/manual` or `research reference`.

---

# 21. CURRENT CHESAPEAKE TRAP DATA EXPANSION

VIMS:
https://www.vims.edu/newsandevents/topstories/2026/noaa-bathymetry-partnership.php

NOAA:
https://oceanservice.noaa.gov/news/july26/bathymetric-data.html

### Important new angle

The current TRAP program combines:
- commercial fishers
- low-cost sonar
- derelict trap removal
- shallow-water bathymetry

VIMS reports that the current program has generated **millions of new bathymetric points** and that the data are being processed and released in batches through NOAA's National Centers for Environmental Information Bathymetric Data Portal.

### Why useful

This may become a future public data source for:
- shallow-water SSS/bathymetry
- derelict-gear locations
- real field data

Monitor the NOAA portal for newly released batches.

---

# 22. HOW TO TURN THE NEW SOURCES INTO YOUR OWN DATA

## 22.1 Plane

Use:

```text
19-aircraft research corpus
+
Sciacca
+
Seabee RC3
+
Project Recover imagery
+
Palau/Chuuk historical sonar
+
Poland aircraft quality variants
```

Create:

```text
plane_real/
plane_partial/
plane_debris/
plane_shadow/
plane_weak_label/
plane_field_verified/
```

---

## 22.2 Ghost net

Use:

```text
Taganrog fishing-net sonar
+
Jiaozhou fishing-net segmentation
+
historical VIMS ghost-gear sonar
+
any newly acquired private SSS
```

Create:

```text
ghost_net_real/
ghost_net_partial/
ghost_net_shadow/
ghost_net_buried/
ghost_gear_rope/
ghost_gear_pot/
```

---

# 23. NEW HARD-NEGATIVE POOL

From the new sources, specifically collect:

```text
rock
coral
sand ripple
mud
seagrass
artificial reef
pipeline
cable
rope
mine-like object
human-like object
wreck
unknown debris
shadow-only
poor geometry
high-altitude sonar
low-altitude sonar
range-truncated target
```

The DeeperSense 434k sediment pool is especially good for seabed/hard-negative pretraining.

---

# 24. NEW SELF-SUPERVISED PRETRAINING POOL

Recommended order:

### Stage 1
DeeperSense:
**434,164 SSS images**

### Stage 2
PINTA:
raw/processed JSF survey data

### Stage 3
China Offshore SSS-AI:
**3,255** multi-region chips

### Stage 4
AquaScan:
**1,000** small-object SSS images

### Stage 5
mine SSS:
**1,170** real annotated images

Then fine-tune with:

```text
plane real
+
ghost-net real
```

This creates an SSS-specific encoder before the difficult target training.

---

# 25. NEW DATA PROVENANCE FIELDS

Add:

```text
source_original_url
source_project
source_owner
source_country
source_region
source_survey
source_sonar
source_frequency
source_resolution
raw_format
processed_format
label_status
field_verified
rights_status
download_status
request_status
derived_from
duplicate_group
```

---

# 26. NEW REQUEST TARGETS

| Organization | Target | Why contact |
|---|---|---|
| Project Recover | aircraft | 19-aircraft training research + ongoing missions |
| University of Delaware / Project Recover | aircraft | SSS + AUV + ROV + historical archive |
| Southern Federal University / NOLACS | nets | actual fishing-net SSS experiment |
| Ocean University of China authors | nets | SSS fishing-net segmentation dataset |
| BSH | SSS | raw JSF + target lists |
| USGS | SSS | raw Klein XTF |
| ISPRA / University of Palermo | plane | Sciacca aircraft SSS |
| ShipwreckWorld | plane | rare aircraft sonar archive |
| VIMS/CCRM | ghost gear | historical/current SSS + recovery |
| NOAA/NCEI | SSS | current/future public archive batches |

---

# 27. IMPORTANT: PRIVATE DATA ROUTE FROM THE NEW PLANE STUDY

The 2025 aircraft study is especially valuable because the authors say:

- high-resolution SSS
- 19 unique aircraft
- 290 labeled fragments
- six countries
- 600 and 1200 kHz
- test on newly collected aircraft
- three of four unknown aircraft detected
- raw data not publicly available because of human-remains sensitivity

This is exactly the type of source where a **small anonymized subset request** makes more sense than asking for the complete archive.

Suggested request:

```text
Subject:
Research request for anonymized side-scan sonar aircraft imagery

Hello Dr. Character,

I am working on a student research project for Smart India Hackathon 2026
focused on automated detection of marine debris and submerged aircraft
from side-scan sonar.

We came across your 2025 study "Deep Learning for Detection of
Underwater Aircraft Wrecks from US Conflicts" and were interested in
the multi-country aircraft-wreck sonar data used in the study.

We completely understand the sensitivity of the original data and are
not requesting exact locations, raw mission information, or any
human-remains-related information.

Would it be possible to share a small anonymized research-only subset,
for example 20–100 side-scan sonar image tiles with labels and all
geographic/mission identifiers removed?

PNG/JPG/GeoTIFF tiles would be sufficient; raw sonar is not required.

The data would be used only for academic/hackathon research, with full
citation/attribution and no redistribution.

Thank you for considering the request.
```

---

# 28. NEW RAW-DATA JUGAAD

Instead of finding a ready dataset:

```text
raw XTF / JSF
      ↓
read navigation
      ↓
generate waterfall
      ↓
detect candidate shadows
      ↓
tile
      ↓
human annotation
      ↓
YOLO
```

Potential new raw sources here:
- USGS Grand Bay XTF
- BSH PINTA JSF
- other NOAA/NCEI marine-trackline holdings

---

# 29. DO NOT COUNT THESE AS “NEW IMAGES” WITHOUT AUDIT

Some research sources generate data through:
- augmentation
- retiling
- mosaicking
- color remapping
- synthetic generation

For example:

```text
434,164 DeeperSense patches
```

does not mean 434,164 independent sonar survey scenes.

Likewise:

```text
810 training images from aircraft study
```

does not mean 810 independent aircraft wrecks.

Always preserve:
```text
parent_scene_id
parent_survey_id
tile_id
augmentation_id
```

---

# 30. NEW DATASET SELECTION FOR YOUR PROJECT

## If you want immediate downloads

Start with:

```text
1. DeeperSense 434,164
2. China Offshore SSS-AI 3,255
3. AquaScan-1K 1,000
4. Gavia mine SSS 1,170
5. BSH processed SSS packages
6. USGS XTF
```

## If you want rare exact plane data

Start with:

```text
1. 19-aircraft / 290-fragment research corpus request
2. Project Recover
3. Poland aircraft-wreck imagery
4. Sciacca
5. Seabee RC3
6. Project Recover Palau/Chuuk archive
```

## If you want rare exact ghost-net data

Start with:

```text
1. Taganrog Bay fishing-net SSS
2. Jiaozhou Bay fishing-net segmentation
3. VIMS historical ghost gear
4. current VIMS/TRAP sonar data
5. request newer raw survey data from related organizations
```

---

# 31. NEW ONLY — FINAL CHECK

These sources were specifically selected because they add a different dimension to your existing corpus:

### Exact plane
- 19 aircraft / 290 labeled fragments / six-country research corpus
- Sciacca 20-m aircraft SSS
- Seabee RC3 sonar archive
- Project Recover 2026 operational aircraft search
- Project Recover Chuuk/Palu weak-label archives
- Poland aircraft quality/geometry variants

### Exact ghost-net / net
- Taganrog Bay actual fishing-net sonar
- Jiaozhou fishing-net SSS segmentation research source
- historical VIMS ghost-gear SSS
- current VIMS/TRAP sonar-derived data route

### Massive SSS auxiliary
- DeeperSense 434,164 SSS patches
- BSH PINTA JSF archives
- USGS Grand Bay raw XTF
- China Offshore SSS-AI 3,255 chips
- AquaScan-1K
- Portuguese Navy/Gavia 1,170 images
- MH370 Phase 2 sonar products

These are intended as **additions**, not replacements for your already implemented datasets.
