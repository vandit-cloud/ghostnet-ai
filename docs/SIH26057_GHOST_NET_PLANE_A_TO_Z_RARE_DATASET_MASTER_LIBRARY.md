# SIH26057 — Ghost Net + Plane / Aircraft Side-Scan Sonar Dataset Master Library
## A-to-Z rare, unique, advanced, labeled, unlabeled, weak-label and acquisition-source catalog

**Problem target:** SIH26057 marine debris detection in Side-Scan Sonar (SSS) imagery  
**Primary classes requested here:**  
- `ghost_net` — abandoned/lost/discarded fishing nets and net-like ghost gear
- `plane` — submerged aircraft, airplane wrecks, aircraft fuselage/wings/debris fields

**Important:** This file is intentionally broader than “ready-made YOLO datasets”. For these two classes, some of the best data exists as raw sonar surveys, government reports, image archives, papers, figures, or data-request projects rather than packaged ML datasets.

**Status key**
- ✅ READY-DATASET = directly downloadable/reusable as a dataset or archive
- 🟡 READY-AUX = downloadable but not exact target/geometry; use as auxiliary training
- 🔵 IMAGE-ONLY = individual real sonar images; useful for weak-label/manual annotation/holdout
- 🟣 REQUEST-DATA = real survey/model data appears to exist but needs a data request, collaboration, or access process
- 🟠 RESEARCH-REFERENCE = paper/report documents real sonar targets; underlying data may not be openly downloadable
- 🧪 SYNTHETIC = generated data; do not report as real-world validation
- ⚠️ LICENSE-VERIFY = check source license/terms before redistribution or commercial use

---

# 1. Executive recommendation

## Best Ghost-Net / Ghost-Gear sources

| Priority | Source | Target similarity | Data type | Approx. scale / evidence | Status |
|---|---|---|---|---|---|
| 1 | GhostVision / `sss-crab-pot-detection-ds` | Ghost gear / crab pots | SSS + boxes | 6,674 annotated images | ✅ |
| 2 | DFO / CSR GeoSurveys Ghost Gear | Ghost gear, pots, rope | SSS + localizations | 1,009 images; 1,568 pot localizations; 1,068 rope localizations; 66 negatives | 🟣 |
| 3 | GhostNetZero | **Real ghost nets** | sonar segments + segmentation | 412 manually annotated segments reported in study | 🟣 |
| 4 | DFO “Detection of Lost Gill Nets with Side Scan Sonar Technology” | **Actual lost gill net** | SSS figures / experiment | real net + hard negative gravel scene | 🔵/🟠 |
| 5 | Mullica River–Great Bay DFG survey | Derelict fishing gear | SSS survey | 2,218 probable DFG targets over 20.78 km² | 🟣 |
| 6 | Chiniak Bay Alaska | Lost crab pots | SSS + field verification | 189 putative; 15 verified; 147 recovered | 🟣/🟠 |
| 7 | Stockton Marine Field Station | Lost fishing gear | SSS survey | long-running program; explicit data-request route | 🟣 |
| 8 | Salish Sea crab-pot surveys | Derelict pots | SSS | multiple sites; real recovery validation | 🟣/🔵 |
| 9 | GGGI Pacific Northwest | Derelict pots | SSS survey | 19 linear km, 73 derelict pots reported | 🟣 |
| 10 | NKSID fishing-net class | Fishing net, but not SSS | forward-looking sonar | small auxiliary class | 🟡 |

### Critical ghost-net reality

Real labelled ghost-net SSS data is substantially rarer than aircraft or generic shipwreck data. This means your strongest dataset strategy is:

`real ghost gear + raw survey imagery + weak labels + hard negatives + controlled synthetic net insertion`

Do **not** claim synthetic-on-synthetic performance as field performance.

---

# 2. Best Plane / Aircraft SSS sources

| Priority | Source | Target | Data type | Scale / evidence | Status |
|---|---|---|---|---|---|
| 1 | SeabedObjects Ship + Airplane | airplane sonar | real SSS | 62 airplane images; also 385 ship images | ✅ |
| 2 | KLSG-II | airplane + ship | real SSS | about 66 airplane / 487 ship / 578 seabed images reported | ✅ |
| 3 | Roboflow Side Scan Sonar — Dae Hyeok Lee | Plane + Ship | labeled SSS | 550 images | ✅ |
| 4 | SonarVision Multi-Source v6 | airplane + debris + wreck + mine | YOLO SSS | 5,558 high-res SSS frames | ✅/⚠️ access condition |
| 5 | NOAA B-29 | WWII aircraft | real SSS image | 11.5 MB downloadable JPG | 🔵 |
| 6 | NOAA Saipan / Tinian expedition | aircraft wrecks | AUV SSS + ROV | multiple aircraft sites | 🔵/🟣 |
| 7 | UB88 SSS archive | many aircraft/wrecks | real SSS images | F-4, P-38, TBM Avenger, Piper Cherokee, etc. | 🔵 |
| 8 | Pacific Wrecks TBM Avenger | aircraft wreck | SSS image | real aircraft sonar | 🔵 |
| 9 | Wessex Archaeology | WWII aircraft | SSS image | real aircraft on seabed | 🔵 |
| 10 | SCTD | aircraft + other sonar targets | sonar; modality needs filtering | public archive with aircraft class | 🟡 |
| 11 | BES-YOLO-related SSS dataset | airplane wreckage + shipwreck + human | SSS | 1,584 images reported | 🟣/🟠 |
| 12 | NOAA aircraft search cases | missing aircraft | SSS | real operational search imagery/examples | 🔵/🟣 |

---

# 3. GHOST NET / GHOST GEAR — A-to-Z source catalog

## 3.1 GhostVision — Derelict Crab Pot SSS Dataset

**Why it matters:** one of the largest directly useful public ghost-gear SSS datasets currently identified.

- Dataset: `PINGEcosystem/sss-crab-pot-detection-ds`
- Total: **6,674 images**
- Sensor: consumer-grade Humminbird side-scan sonar
- Areas:
  - northern Rehoboth Bay near Dewey Beach
  - western Indian River Bay
  - southern Indian River Bay near White Creek
- Annotation: JSONL bounding boxes
- Related GhostVision paper reports 3,110 manually annotated images used for specific experiments, while the released dataset is larger.
- Targets are derelict crab pots / ghost pots rather than free-floating mesh gill nets.
- Extremely useful for:
  - ghost-gear detector pretraining
  - hard negatives
  - shadow analysis
  - georeferencing pipeline examples
  - low-cost sonar robustness
- License: inspect current Hugging Face / Zenodo terms before redistribution.

Links:
- https://huggingface.co/datasets/PINGEcosystem/sss-crab-pot-detection-ds
- https://github.com/PINGEcosystem/GhostVision
- https://zenodo.org/records/20056679

Source evidence:
GhostVision dataset page reports 6,674 annotated SSS images and Humminbird SSS imagery.
GhostVision publication describes 3,110 manually annotated images and the full pipeline.

## 3.2 GhostVision Zenodo package

**Dataset + model package**

- Archive: `GhostVision_DatasetAndModels.zip`
- Size shown: about **898.8 MB**
- Record data volume metadata: about **181.6 GB**
- Includes dataset/model resources for the GhostVision system.

Link:
https://zenodo.org/records/20056679

Use this as the preferred archive route when the Hugging Face dataset viewer or format is inconvenient.

---

## 3.3 DFO / CSR GeoSurveys Ghost Gear Detection Dataset

**High-value request target**

DFO’s AI portal documents a ghost-gear detector trained from CSR GeoSurveys data:

- **1,009 SSS images**
- **1,568 lobster-trap localizations**
- **1,068 rope localizations**
- **66 non-gear negatives**
- model: YOLOv6 in the portal description

Why this is valuable for `ghost_net`:
- rope is a strong visual/acoustic proxy for net structure
- negatives are useful for false-positive reduction
- real field survey data is better than synthetic-only data

Access:
https://ocds-ai-portal.canadacentral.cloudapp.azure.com/details/

Recommended action:
Contact the data owner / project and request:
1. original SSS images
2. original annotations
3. source file format
4. ping / navigation metadata
5. survey geometry
6. permission to use the data in a student research / hackathon model

---

## 3.4 GhostNetZero — real ghost-net sonar segments

This is one of the most important **true ghost-net** leads.

Reported data composition:
- Baltic Sea: **239 manually annotated sonar segments**
- Puget Sound: **173 manually annotated sonar segments**
- total: **412**
- annotations include binary segmentation masks
- real sonar, not a synthetic-only benchmark

Platform:
https://ghostnetzero.ai/

Research manuscript:
https://ecoevorxiv.org/repository/object/10294/download/19035/

Microsoft Research:
https://www.microsoft.com/en-us/research/publication/ghostnetzero-ai-for-detecting-marine-ghost-nets/

Why it is special:
- actual ghost nets
- segmentation rather than only detection
- multiple geographic environments
- highly relevant to the exact SIH problem

Recommended strategy:
- request the underlying annotated dataset or research collaboration
- ask specifically for raw XTF / processed sonar tiles / masks
- preserve Baltic vs Puget Sound provenance
- keep site-disjoint validation

---

## 3.5 DFO — Detection of Lost Gill Nets with Side Scan Sonar Technology

An older government source that normal dataset search often misses.

Report:
https://waves-vagues.dfo-mpo.gc.ca/library-bibliotheque/145861.pdf

It contains:
- a real sonar image of a net collected on a sandy bottom
- a **500 kHz, 50 m range** example
- a hard-negative case at a gravel site where the net was **not detected**
- explicit acoustic shadow information

Why use it:
- true lost-gill-net evidence
- acoustic-shadow morphology
- hard negative
- different seabed conditions

This is particularly useful to build:
- `ghost_net_real_reference`
- `ghost_net_shadow`
- `net_not_detected`
- `gravel_hard_negative`

**Legal caution:** a public report being viewable/downloadable does not automatically mean every extracted figure can be redistributed in your training dataset. Verify terms or use it only for research/annotation guidance as appropriate.

---

## 3.6 Mullica River–Great Bay Estuary derelict fishing gear survey

Paper:
https://www.sciencedirect.com/science/article/pii/S0025326X18307707

Documented survey facts:
- four winter survey periods
- 2013, 2014, 2016, 2017
- Klein 3900 and/or EdgeTech 6205 side-scan
- **2,218 probable DFG targets**
- **20.78 km²** surveyed

This is a high-value **raw-data request target** because the target count is much larger than most public ML datasets.

Potential classes:
- crab pot / trap
- rope
- other derelict fishing gear
- seabed false positives

Recommended contact route:
Use the paper author/project/institution pages and request:
- sonar mosaics
- raw swaths
- target coordinates
- target inspection/recovery status
- false-positive examples

---

## 3.7 Stockton University Marine Field Station

Page:
https://www.stockton.edu/marine/marine-debris.html

The program explicitly uses side-scan sonar for lost gear and has a **“Request data”** pathway.

The page identifies:
- marine debris program
- sonar training / survey work
- side-scan sonar image examples
- request-data email contact

Use this as a collaboration lead rather than assuming there is a public zip file.

Ask for:
- original survey imagery
- target annotations
- recovered vs unrecovered target status
- crab-pot/rope labels
- survey date/location metadata
- negatives

---

## 3.8 Salish Sea — Recovering Lost Crab Pots

ArcGIS StoryMap:
https://storymaps.arcgis.com/stories/1befb7cae32f49e89d8595d8ae884d38

Documented locations:
- Discovery Bay
- Cape George
- Port Townsend Bay

The StoryMap describes real-time side-scan sonar identification and geolocation of crab pots and notes difficult field conditions.

Why valuable:
- independent geographic domain
- shallow coastal water
- operational SSS
- target-confirmation workflow
- map/GIS context

Potential extraction:
- public figures / examples where legally reusable
- target morphology reference
- source organization contacts for data requests

---

## 3.9 Global Ghost Gear Initiative — Pacific Northwest

Project:
https://global-ghost-gear.squarespace.com/projects/signature-pnw

Reported:
- **19 linear km** SSS surveys
- **73 derelict pots** identified

Use:
- source for real-world ghost-gear domain
- survey design references
- organization/data-request lead

---

## 3.10 Chiniak Bay, Alaska — lost crab pots

Paper:
https://www.researchgate.net/publication/242471543_Ghost_fishing_by_Tanner_crab_Chionoecetes_bairdi_pots_off_Kodiak_Alaska_Pot_density_and_catch_per_trap_as_determined_from_sidescan_sonar_and_pot_recovery_data

Reported:
- **189 putative lost crab pots** found by SSS
- survey area: about **4.5 km²**
- 15 objects verified by submersible/ROV
- 147 pots recovered from surveyed/adjacent areas

Why useful:
- old, independent dataset lineage
- real sonar detections + physical verification
- recovery status is a valuable label

Possible schema:
`putative_pot`
`verified_pot`
`recovered_pot`
`false_target`

---

## 3.11 Evaluating SSS for ALDFG / ghost gear retrieval

Paper:
https://www.researchgate.net/publication/372158149_Evaluating_the_use_of_side_scan_sonar_for_improved_detection_and_targeted_retrieval_of_abandoned_lost_or_otherwise_discarded_fishing_gear

This is another strong research lead for:
- abandoned/lost/discarded fishing gear
- SSS detection
- retrieval workflows
- survey methodology

Use paper figures as reference/weak-label candidates only when licensing/permission permits.

---

## 3.12 NKSID Fishing Net — auxiliary sonar source

Repository:
https://github.com/Jorwnpay/NK-Sonar-Image-Dataset

Reported properties:
- 2,617 images
- 8 categories
- forward-looking sonar
- fishing-net category exists
- underwater target imagery captured with an Oculus M750d

Important:
**This is NOT side-scan sonar.**

Use it only for:
- auxiliary sonar representation learning
- net texture/shape pretraining
- contrastive learning
- synthetic net validation
- feature-level transfer

Do not mix directly into your SSS field-accuracy benchmark.

---

# 4. PLANE / AIRCRAFT — A-to-Z source catalog

## 4.1 SeabedObjects Ship + Airplane

GitHub:
https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset

Reported:
- **385 ship images**
- **62 airplane sonar images**
- real side-scan sonar
- academic-use statement in repository

Repository contains:
`plane-real.zip`

This is one of the cleanest dedicated real aircraft SSS datasets.

Recommended use:
- baseline plane detector
- aircraft-specific pretraining
- morphology library
- hard negatives from ship/seabed classes

---

## 4.2 KLSG-II

GitHub:
https://github.com/HHUCzCz/-SeabedObjects-KLSG--II

Published reports describe approximately:
- 66 airplane images
- 487 ship images
- 578 seabed images

Use:
- independent aircraft source
- seabed negatives
- ship-vs-plane confusion examples

Important:
KLSG and KLSG-II are related dataset families. Treat them as related provenance, not automatically as independent test sets.

---

## 4.3 Roboflow — Dae Hyeok Lee Side Scan Sonar

Dataset:
https://universe.roboflow.com/dae-hyeok-lee/side-scan-sonar

Reported:
- **550 images**
- classes:
  - `Ship`
  - `Plane`
- license displayed: **CC BY 4.0**

Excellent practical source because it already provides object-detection labels.

Recommended:
Download/export in YOLO format and convert class names into your canonical ontology:
`plane`

---

## 4.4 Roboflow duplicate / alternate workspace

Another public project:
https://universe.roboflow.com/college-qscys/side-scan-sonar-mg4j8

It also reports:
- 550 images
- Ship
- Plane

Before adding it, hash the images and compare them to the Dae Hyeok Lee set. Do **not** count duplicate exports as new independent data.

---

## 4.5 SonarVision Multi-Source SSS v6

Hugging Face:
https://huggingface.co/datasets/Dinoman1221/sonarvision-multisource-v6

Reported:
- **5,558 high-resolution SSS frames**
- classes:
  - `unknown_debris`
  - `airplane`
  - `mine`
  - `wreck`
- standard YOLO layout
- about **924 MB** archive in dataset documentation
- project code:
  https://github.com/Dinoman67/sonarvision

Potential use:
- aircraft positives
- debris class
- unknown class
- hard negatives
- multi-class detector pretraining

Access conditions may require agreement/contact information. Check the current dataset page before automated download.

---

## 4.6 NOAA B-29 side-scan sonar image

NOAA:
https://oceanexplorer.noaa.gov/multimedia/explorations-22saipan-surveys-gallery-media-b-29-2/

Real WWII B-29 aircraft wreck.

NOAA page reports:
- side-scan sonar image
- downloadable largest JPG
- about **11.5 MB**

This is highly useful for:
- rare aircraft morphology
- external real-world holdout
- long-range shadow patterns
- visual QA/demo

Do not treat a single aircraft as hundreds of independent test scenes.

---

## 4.7 NOAA Saipan / Tinian aircraft survey

Expedition:
https://oceanexplorer.noaa.gov/expedition/22saipan-surveys/

The expedition:
- occurred in 2022
- used side-scan sonar mounted on two REMUS 600 AUVs
- searched for WWII aircraft
- identified two aircraft crash sites
- also mapped other seafloor targets

Use:
- real aircraft SSS
- AUV-based domain
- deeper-water operational imagery
- data-request / expedition-data mining

---

## 4.8 NOAA B-25 aircraft example

NOAA’s SSS technology page:
https://oceanexplorer.noaa.gov/technology/sonar-side-scan/

It shows a high-resolution side-scan sonar image of a WWII **B-25** discovered in Papua New Guinea.

This is another independent aircraft morphology example.

---

## 4.9 UB88 Side-Scan Sonar archive

Archive:
https://www.ub88.org/sidescansonar/side-scan-sonar.html

This is an unusually good “hidden web” source.

It includes sonar imagery associated with aircraft/wreck sites such as:
- TBM Avenger
- F-4 Phantom
- P-38
- Piper Cherokee
- other underwater wrecks/targets

Use it to build:
- `plane_real_weak_label`
- `aircraft_debris`
- `aircraft_shadow`
- `wreck_hard_negative`

Important:
Archive image rights vary; verify image rights before redistributing or mass-downloading.

---

## 4.10 TBM Avenger — UB88

Project page:
https://www.ub88.org/researchprojects/tbmavenger/tbm-avenger.html

Additional:
https://pacificwrecks.com/aircraft/tbm/45810/2014/sss-fan-avenger.html

Use:
- dedicated aircraft sonar example
- debris-field context
- rare morphology

---

## 4.11 Wessex Archaeology — WWII aircraft sonar

Flickr:
https://www.flickr.com/photos/wessexarchaeology/4438313886/

Caption identifies:
- side-scan sonar image
- WWII aircraft on seabed off Kent

Important:
Flickr rights show “Some rights reserved”. Do not assume unrestricted dataset redistribution.

---

## 4.12 SCTD — Sonar Common Target Detection Dataset

GitHub:
https://github.com/MingqiangNing/SCTD

Repository contains:
- `SCTD.zip`
- `SCTD2.0.rar`
- Pascal VOC XML annotations
- helper conversion code

Aircraft class is present in documented versions/releases.

Use:
- auxiliary sonar representation
- aircraft classification/detection research
- cross-modal feature learning

**Modality caution:** SCTD is a broader sonar dataset and should be filtered to the appropriate sonar modality before being mixed into an SSS-only benchmark.

---

## 4.13 BES-YOLO / multi-scale SSS marine-object data

Paper:
https://pmc.ncbi.nlm.nih.gov/articles/PMC11281110/

Reported experimental dataset:
- **1,584 side-scan sonar images**
- includes:
  - shipwreck images
  - airplane wreckage images
  - human-related target images
- collected/assembled from multiple hydrographic departments, manufacturers and online sources
- systems mentioned include Klein 3000, EdgeTech 4200, Yellowfin, SS900

This is more of a **research/data-provenance lead** than a clean public benchmark.

Use paper references to locate its upstream images.

---

## 4.14 NOAA missing-aircraft SSS operational case

NOAA / Office of Coast Survey:
https://nauticalcharts.noaa.gov/updates/from-historic-air-disasters-to-todays-hurricane-response-noaa-uses-cutting-edge-science-to-survey-the-seafloor/

The article describes:
- a missing plane
- SSS survey around Martha’s Vineyard
- suspicious sonar target
- target later confirmed as the missing plane

This is useful for:
- operational detection context
- rare weak-label image mining
- false-positive / search scenario research

---

## 4.15 Lake Mead B-29 — historical side-scan discovery

National Park Service:
https://www.nps.gov/lake/learn/historic-lake-mead-b-29.htm

The page documents discovery of a B-29 wreck using side-scan sonar.

Use:
- search methodology
- aircraft target morphology
- potential archive/image trail

---

# 5. Additional sonar data that is not an exact target but is highly useful

These sources can make your model robust.

## 5.1 NOAA generic SSS image library

https://oceanexplorer.noaa.gov/multimedia/sonar-imagery/

Useful for:
- seafloor
- wrecks
- unknown objects
- sonar appearance
- hard negatives

Example NOAA imagery includes unknown targets and wrecks.

---

## 5.2 NOAA/NCEI Okeanos Explorer SSS-linked cruises

Example:
https://www.ncei.noaa.gov/waf/okeanos-rov-cruises/ex1711/

Contains cruise resources, imagery/video and dive context.

Use:
- unlabeled real seafloor
- wreck/debris scenes
- negative background
- multimodal validation

---

## 5.3 Historic NOAA Coast & Geodetic Survey sonar images

Example:
https://www.noaa.gov/noaa-collections/photo-library/cgs01170jpg

Good for:
- historic sonar texture
- hard negatives
- old acquisition characteristics

---

# 6. “Hidden” data acquisition methods

## 6.1 Search papers instead of dataset websites

Use these exact search templates:

```text
"side scan sonar" "ghost net"
"side scan sonar" "lost gill net"
"side scan sonar" "ghost gear"
"side scan sonar" "derelict fishing gear"
"side scan sonar" "lost crab pot"
"side scan sonar" "abandoned fishing gear"
"side scan sonar" "aircraft wreck"
"side scan sonar" "airplane wreck"
"side scan sonar" "B-29"
"side scan sonar" "B-25"
"side scan sonar" "P-38"
"side scan sonar" "F-4 Phantom"
"side scan sonar" "TBM Avenger"
"side scan sonar" "Piper Cherokee"
```

Then add:
```text
filetype:pdf
download
supplementary
dataset
repository
raw data
appendix
figures
archive
```

---

## 6.2 Government-report mining

Government reports often contain:
- high-resolution sonar figures
- target examples
- acquisition frequency
- range
- shadow
- seabed condition
- negative examples

Targets:
- NOAA
- DFO Canada
- NPS
- BOEM
- USGS
- national hydrographic offices
- coast surveys
- university marine field stations

Workflow:

```text
PDF/report
   ↓
identify sonar figures
   ↓
check rights
   ↓
crop target / background
   ↓
manually annotate
   ↓
store provenance
```

---

## 6.3 Archive mining

Potential image/archive sources:

```text
NOAA Ocean Exploration
NOAA NCEI
UB88
Pacific Wrecks
Wessex Archaeology
university field stations
ArcGIS StoryMaps
government photo libraries
Flickr institutional accounts
marine archaeology projects
shipwreck survey projects
```

Search target plus `side scan`, not merely target name.

Bad:
```text
B-29 underwater
```

Better:
```text
B-29 "side scan sonar"
```

---

## 6.4 Contact researchers directly

For rare ghost-net data, asking the research group can be far more productive than another Kaggle search.

Request:

```text
I am building an academic/student SIH 2026 prototype for automated
marine debris detection from side-scan sonar. We are specifically
interested in ghost gear / lost nets and would like to use a small
research-only subset of sonar images for model training and evaluation.
Could you share any raw or annotated SSS imagery, or point us to the
appropriate repository/data-request process?
```

Ask for:
- raw sonar
- exported image tiles
- masks/boxes
- navigation
- target coordinates
- target inspection status
- sonar frequency/range
- survey area/depth
- permission terms

---

# 7. Weak-label strategy for image-only sources

When an archive contains:

```text
page title = TBM Avenger
caption = side-scan sonar image
image = sonar frame
```

Store:

```json
{
  "class": "plane",
  "label_type": "weak",
  "target_name": "TBM Avenger",
  "image_source": "public_archive",
  "bbox_status": "manual_review_required",
  "license_status": "verify",
  "provenance_url": "..."
}
```

Then manually annotate the target.

For ghost gear:

```json
{
  "class": "ghost_net",
  "label_type": "weak",
  "evidence": "paper_figure_or_caption",
  "bbox_status": "manual_review_required"
}
```

Never silently upgrade weak labels to ground-truth labels.

---

# 8. Turning one large sonar image into a useful dataset

Suppose you have:

```text
8000 x 4000 sonar image
```

Create overlapping tiles:

```text
512x512
640x640
1024x640
1024x1024
1280x768
```

Recommended overlap:
- 20–50% depending on target size

But keep `scene_id`:

```text
scene_0001
scene_0001_tile_001
scene_0001_tile_002
...
```

**Critical split rule:** all tiles from one original scene must remain in the same train/validation/test partition.

Otherwise you get leakage.

---

# 9. Ghost-net synthetic generation

Because true ghost-net SSS data is scarce, synthetic augmentation is useful when clearly separated from real data.

## Generate net geometry

Create:
- straight gillnet
- collapsed gillnet
- tangled net
- coiled net
- broken net
- partially buried net
- net around rock
- net around debris
- net with strong shadow
- net with weak shadow
- vertically standing net
- low-contrast net
- oblique net
- partial net at image border

## Sonar appearance operations

Apply:
- speckle
- multiplicative gain
- attenuation
- blur
- local contrast changes
- directional smear
- dropout stripes
- missing pings
- motion distortion
- shadow synthesis
- range-dependent intensity
- left/right sonar asymmetry
- seabed texture blending

Label:

```text
real
synthetic
semi_synthetic
```

---

# 10. Plane synthetic generation

Use 3D/2D aircraft silhouettes only as an auxiliary expansion.

Generate variations:

```text
fuselage only
wing only
tail
nose
partially buried fuselage
broken aircraft
aircraft debris field
aircraft + strong shadow
aircraft + weak shadow
oblique aircraft
aircraft at far range
aircraft at near range
partial occlusion
low contrast
high speckle
dropout
motion distortion
```

The best semi-synthetic method is:

```text
REAL SSS BACKGROUND
       +
AIRCRAFT TARGET SHAPE
       +
PHYSICS-INSPIRED SHADOW
       +
SONAR NOISE
```

This is preferable to inserting a normal RGB photograph of an airplane.

---

# 11. Hard-negative bank

For `ghost_net` the following classes are mandatory:

```text
rock
ripple
sand ridge
cable
rope
pipeline
wreck
shipwreck debris
vegetation
shadow-only
seabed scar
noise
dropout
unknown object
```

For `plane`:

```text
ship
shipwreck
large debris
pipeline
elongated rock
rock cluster
strong shadow
industrial object
container
mine-like object
unknown debris
```

Why:
A high-accuracy detector on easy positives can still fail badly on real seabed scenes.

---

# 12. Self-supervised / unlabeled SSS collection

Your unlabeled data does not need manual labels initially.

Collect:

```text
raw SSS mosaics
raw SSS tiles
NOAA image archives
NCEI cruise data
public marine survey imagery
shipwreck surveys
seabed surveys
fishing-gear surveys
```

Use unlabeled data for:

### A. Contrastive pretraining
Learn sonar texture before supervised training.

### B. Autoencoder background modeling
Train normal-seabed reconstruction and detect unusual objects.

### C. Hard-negative mining
Run current detector, save high-confidence false positives, manually review.

### D. Unknown detector
Cluster novel acoustic targets separately from known classes.

### E. Domain adaptation
Pretrain on one sonar manufacturer and adapt to another.

---

# 13. Ghost-net-specific label ontology

Do not use only one broad label.

Recommended internal ontology:

```text
ghost_net
ghost_net_partial
ghost_net_buried
ghost_net_tangled
ghost_net_shadow
ghost_gear_pot
ghost_gear_rope
ghost_gear_other
unknown_ghost_gear
```

For the final SIH API you can collapse:

```text
ghost_net
```

while retaining the detailed internal subtype.

---

# 14. Plane-specific label ontology

Internal labels:

```text
plane
plane_partial
plane_fuselage
plane_wing
plane_tail
plane_debris
plane_wreck
unknown_aircraft
```

Final UI can display:

```text
Plane
```

with subtype in metadata.

---

# 15. Source/provenance schema

Every image must carry:

```json
{
  "image_id": "GN_BALTIC_000123",
  "source_name": "GhostNetZero",
  "source_url": "...",
  "source_type": "research_dataset",
  "target_class": "ghost_net",
  "label_type": "mask",
  "modality": "side_scan_sonar",
  "sonar_frequency_khz": null,
  "range_m": null,
  "location_level": "region",
  "country": null,
  "survey_id": null,
  "scene_id": null,
  "license": "verify",
  "license_verified": false,
  "download_date": "YYYY-MM-DD",
  "sha256": "...",
  "parent_image_id": null
}
```

Never lose provenance.

---

# 16. Recommended master directory

```text
datasets/
├── ghost_net/
│   ├── real_labeled/
│   │   ├── ghostvision/
│   │   ├── ghostnetzero/
│   │   ├── dfo_gillnet/
│   │   └── verified_other/
│   │
│   ├── real_weak/
│   │   ├── government_reports/
│   │   ├── archive_images/
│   │   └── paper_figures/
│   │
│   ├── real_unlabeled/
│   │   ├── stockton/
│   │   ├── mullica/
│   │   ├── salish/
│   │   └── other_sss/
│   │
│   ├── auxiliary/
│   │   └── nksid_fishing_net/
│   │
│   ├── synthetic/
│   │   ├── procedural/
│   │   ├── copy_paste/
│   │   └── physics_shadow/
│   │
│   └── hard_negative/
│
└── plane/
    ├── real_labeled/
    │   ├── seabedobjects/
    │   ├── klsg2/
    │   ├── roboflow/
    │   ├── sonarvision/
    │   └── sctd_filtered/
    │
    ├── real_weak/
    │   ├── noaa/
    │   ├── ub88/
    │   ├── pacific_wrecks/
    │   └── wessex/
    │
    ├── real_unlabeled/
    │
    ├── synthetic/
    │
    └── hard_negative/
```

---

# 17. Download/collection priority

## Phase 1 — download immediately

### Ghost
1. GhostVision / PINGEcosystem
2. GhostVision Zenodo archive
3. NKSID auxiliary fishing-net class

### Plane
1. SeabedObjects
2. KLSG-II
3. Roboflow 550
4. SonarVision v6
5. SCTD

---

# 18. Phase 2 — manually collect rare real images

### Ghost
1. DFO lost-gill-net report
2. GhostNetZero public-facing images/examples
3. Stockton imagery
4. Salish Sea StoryMap
5. GGGI project imagery
6. Mullica study figures
7. Chiniak paper figures

### Plane
1. NOAA B-29
2. NOAA B-25
3. NOAA Saipan expedition
4. UB88 aircraft
5. TBM Avenger
6. Pacific Wrecks
7. Wessex Archaeology
8. NOAA missing-aircraft operational cases
9. Lake Mead B-29 reference

---

# 19. Phase 3 — request original data

Highest-value requests:

```text
DFO / CSR GeoSurveys
GhostNetZero
Mullica River–Great Bay researchers
Stockton Marine Field Station
Salish Sea / local marine resources committees
GGGI Pacific Northwest
NOAA expedition investigators
UB88 project owners
```

Ask specifically for:
- raw or minimally processed SSS
- XTF / JSF / vendor-native formats
- georeferenced mosaics
- target coordinate tables
- annotation masks/boxes
- recovered/verified status
- negative targets
- survey metadata

---

# 20. Search engines and repositories to mine

## Dataset platforms
```text
Hugging Face
GitHub
Zenodo
Kaggle
Roboflow Universe
Data.gov / government data portals
Figshare
Dryad
Mendeley Data
PANGAEA
OpenAIRE
institutional repositories
```

## Research search
```text
Google Scholar
Semantic Scholar
Crossref
ResearchGate
PubMed Central
MDPI
IEEE Xplore
ScienceDirect
Springer
SAGE
Taylor & Francis
```

## Government
```text
NOAA
NCEI
DFO Canada
NPS
USGS
BOEM
state marine-resource agencies
national hydrographic offices
```

## Archive/image sites
```text
NOAA Ocean Exploration
NOAA Photo Library
NOAA NCEI
UB88
Pacific Wrecks
Wessex Archaeology
institutional Flickr accounts
ArcGIS StoryMaps
museum / maritime archaeology archives
```

---

# 21. Advanced “search trick” queries

Copy/paste:

```text
"side scan sonar" "ghost net" dataset
"side-scan sonar" "ghost net" filetype:pdf
"side scan sonar" "lost gill net"
"side scan sonar" "ghost gear" images
"side scan sonar" "derelict fishing gear"
"side scan sonar" "crab pot" sonar image
"side scan sonar" "lost crab pot" dataset
"side scan sonar" "fishing gear" sonar
"side scan sonar" "aircraft wreck" dataset
"side scan sonar" "airplane" dataset
"side scan sonar" "plane wreck"
"side scan sonar" B-29
"side scan sonar" B-25
"side scan sonar" P-38
"side scan sonar" F-4 Phantom
"side scan sonar" TBM Avenger
"side scan sonar" Piper Cherokee
"side-scan sonar" "aircraft" filetype:pdf
```

GitHub-specific:

```text
site:github.com "side scan sonar" airplane
site:github.com "side-scan sonar" plane dataset
site:github.com "ghost gear" sonar
site:github.com "ghost net" sonar
site:github.com "fishing net" sonar dataset
```

Hugging Face:

```text
site:huggingface.co/datasets sonar airplane
site:huggingface.co/datasets side scan sonar
site:huggingface.co/datasets ghost gear sonar
site:huggingface.co/datasets ghost net sonar
```

Government:

```text
site:noaa.gov "side scan sonar" aircraft
site:oceanexplorer.noaa.gov "side scan sonar" aircraft
site:dfo-mpo.gc.ca "side scan sonar" fishing gear
site:ncei.noaa.gov sonar wreck aircraft
site:nps.gov "side-scan sonar" aircraft
```

---

# 22. Data extraction from PDF figures

Recommended process:

```text
PDF
 ↓
identify figure number
 ↓
check license
 ↓
render at high resolution
 ↓
crop full sonar panel
 ↓
remove only non-data border if needed
 ↓
annotate target
 ↓
store original + crop
 ↓
record source page/figure
```

Store:

```text
source_document.pdf
source_page_07_full.png
source_page_07_target_crop.png
source_page_07_metadata.json
```

Do not overwrite originals.

---

# 23. De-duplication

Do not count:

```text
same image
different JPEG quality
same image mirrored
same image resized
same image exported from Roboflow and GitHub
same source appearing in another “new” dataset
```

Use:
- exact SHA-256
- perceptual hash
- image embedding similarity
- scene ID
- source provenance

Recommended duplicate fields:

```text
sha256
phash
source_id
scene_id
parent_image_id
```

---

# 24. Dataset leakage prevention

For sonar, random image-level splitting is dangerous.

Split by:

```text
survey
mission
site
wreck
geographic area
sonar acquisition
```

Not by random tile.

Recommended:

```text
TRAIN:
North/Survey A/B/C

VALIDATION:
Survey D

TEST:
completely different Survey E
```

For plane:
- do not put the same aircraft wreck in train and test

For ghost gear:
- do not put adjacent passes from the same survey into train and test.

---

# 25. Quality tiers

Each sample gets:

```text
TIER_0 = unverified
TIER_1 = weak label
TIER_2 = manually boxed
TIER_3 = double-reviewed
TIER_4 = field verified / physically recovered
TIER_5 = field verified + precise location metadata
```

Use TIER_4/5 for your best benchmark.

---

# 26. Ghost-net special benchmark

Build five test slices:

### GN-1: high contrast
Easy ghost gear.

### GN-2: weak contrast
Low SNR.

### GN-3: partial/buried
Only portion visible.

### GN-4: hard negative
Cable/rope/rock/ripple/shadow.

### GN-5: geographic shift
Train on one region, test on another.

This is much more credible than one overall mAP number.

---

# 27. Plane special benchmark

Build:

```text
PL-1 large aircraft
PL-2 small aircraft
PL-3 partial aircraft
PL-4 debris field
PL-5 low contrast
PL-6 strong shadow
PL-7 weak shadow
PL-8 different sonar manufacturer
PL-9 different geographic area
PL-10 ship/wreck confusion
```

---

# 28. Metadata to preserve

For every SSS image, preserve when available:

```text
latitude
longitude
heading
depth
slant range
swath range
frequency
towfish altitude
ship speed
ping rate
resolution
port/starboard
gain
time
survey date
sonar manufacturer
sonar model
file format
coordinate reference system
```

This directly supports your SIH metadata requirement.

---

# 29. Raw sonar formats to seek

Do not restrict requests to JPG.

Ask for:

```text
XTF
JSF
vendor-native sonar files
SDF/vendor exports
GeoTIFF
georeferenced mosaics
navigation logs
CSV target tables
KML/KMZ
shapefile
GeoPackage
```

Keep raw data separate from processed imagery.

---

# 30. Advanced synthetic data ideas

## 30.1 Procedural ghost net

Generate random net topology.

Parameters:
```text
length
height
mesh size
orientation
tangle factor
burial factor
visibility
shadow intensity
```

## 30.2 Acoustic shadow simulator

Approximate shadow using:
```text
object elevation
sonar incidence geometry
range
substrate reflectivity
```

## 30.3 Seabed style transfer

Apply:
```text
sand
mud
gravel
rock
rippled seabed
mixed bottom
```

## 30.4 Motion degradation

Simulate:
```text
heave
pitch
roll
yaw
towfish swing
speed variation
ping dropout
```

---

# 31. Advanced semi-synthetic pipeline

Recommended:

```text
REAL SSS BACKGROUND
        ↓
find natural empty region
        ↓
insert procedural target
        ↓
generate target echo + shadow
        ↓
blend with local seabed
        ↓
apply sonar degradation
        ↓
save mask/bbox
        ↓
store as SEMI_SYNTHETIC
```

This is much more realistic than copying an RGB airplane/net photo into sonar.

---

# 32. Active learning loop

Start with real labeled data.

```text
Train v1
 ↓
Run over unlabeled SSS
 ↓
collect:
  high-confidence false positives
  uncertain targets
  unknown targets
 ↓
human review
 ↓
add hardest cases
 ↓
Train v2
```

This turns your large unlabeled archive into useful training data.

---

# 33. Confidence and uncertainty data selection

Store:

```json
{
  "confidence": 0.61,
  "class_margin": 0.08,
  "tta_disagreement": 0.17,
  "unknown_score": 0.73,
  "review_required": true
}
```

High disagreement examples become annotation priorities.

---

# 34. Dataset balancing

Do not force exactly equal classes blindly.

Recommended starting target for **real/supervised** data:

```text
ghost_net / ghost_gear: as many real field positives as possible
plane: all independent real aircraft sources
hard_negative: at least 1–3x positive volume
unknown: large unlabeled pool
synthetic: capped and clearly separated
```

For ghost-net, prioritize **diversity over raw count**.

---

# 35. Recommended canonical class mapping

External labels → internal labels:

```text
Crab-Pot          → ghost_gear_pot
Maybe-Pot         → uncertain_ghost_gear
rope              → ghost_gear_rope
Fishing net       → ghost_net
ghost net         → ghost_net
airplane          → plane
Plane             → plane
aircraft          → plane
aircraft wreck    → plane
plane wreck       → plane
```

Keep original label in:

```text
source_class
```

---

# 36. Important distinction: ghost pot vs ghost net

Your SIH UI can have:

```text
Ghost Gear
 ├── Ghost Net
 ├── Ghost Pot
 └── Ghost Rope
```

but the main required class can remain:

```text
ghost_net
```

Use the more specific class only when evidence is strong.

This prevents incorrectly calling every ghost pot a net.

---

# 37. License / permission matrix

| Source | Action |
|---|---|
| CC BY / CC BY 4.0 | Usually usable with attribution, verify exact terms |
| CC BY-SA | Derivative sharing obligations may apply |
| Academic-use repository | Do not assume commercial redistribution |
| Government image | Check agency rights/credit requirements |
| Research paper figure | Do not automatically assume dataset redistribution rights |
| Flickr “Some rights reserved” | Check exact license |
| Request-only data | Follow owner’s written terms |
| Synthetic | You control your generated output, but check any source assets/models |

For the hackathon:
- keep a `LICENSE.md`
- keep source URLs
- keep author/organization names
- maintain attribution file
- never remove source metadata.

---

# 38. Recommended final dataset composition for SIH

## Ghost branch

### REAL
```text
GhostVision
GhostNetZero
DFO gill-net examples
DFO/CSR ghost-gear request data
Mullica request data
Chiniak request/reference
Stockton request data
Salish request/reference
GGGI reference
other verified research sources
```

### AUXILIARY
```text
NKSID fishing-net
rope/cable sonar examples
other sonar net-like targets
```

### SYNTHETIC
```text
procedural net
semi-synthetic net
shadow simulation
```

### NEGATIVE
```text
rock
ripple
rope
cable
pipeline
wreck
noise
shadow-only
```

---

# 39. Recommended final dataset composition for Plane

### REAL LABELED
```text
SeabedObjects
KLSG-II
Roboflow SSS Plane
SonarVision v6
filtered SCTD
```

### REAL WEAK / IMAGE-ONLY
```text
NOAA B-29
NOAA B-25
NOAA Saipan
UB88 aircraft archive
TBM Avenger
Pacific Wrecks
Wessex Archaeology
NOAA operational aircraft searches
Lake Mead B-29
```

### SYNTHETIC
```text
aircraft silhouettes
wreck fragments
semi-synthetic sonar shadows
```

### HARD NEGATIVE
```text
ships
shipwrecks
debris
rocks
pipelines
containers
unknown objects
```

---

# 40. The “rare dataset advantage” strategy

Your project does NOT need to claim:

> “We found the largest sonar dataset.”

A stronger statement is:

> “We combine public labeled SSS datasets with rare government/research sonar imagery, weakly supervised archive targets, field-validated ghost-gear sources, and controlled synthetic augmentation, while maintaining source- and survey-level provenance.”

That is technically much more defensible.

---

# 41. Final acquisition checklist

## Ghost Net

```text
[ ] GhostVision 6674
[ ] GhostVision Zenodo package
[ ] GhostNetZero 412 lead
[ ] DFO lost gill-net report
[ ] DFO/CSR 1009-image request
[ ] Mullica 2218-target request
[ ] Chiniak 189-target research lead
[ ] Stockton request
[ ] Salish Sea request
[ ] GGGI PNW lead
[ ] NKSID fishing-net auxiliary
[ ] government report mining
[ ] paper-figure mining
[ ] synthetic generator
[ ] hard-negative bank
```

## Plane

```text
[ ] SeabedObjects 62 airplane
[ ] KLSG-II
[ ] Roboflow 550
[ ] SonarVision v6
[ ] SCTD filtered aircraft
[ ] NOAA B-29
[ ] NOAA B-25
[ ] NOAA Saipan
[ ] UB88 aircraft archive
[ ] TBM Avenger
[ ] Pacific Wrecks
[ ] Wessex Archaeology
[ ] NOAA aircraft search case
[ ] Lake Mead B-29
[ ] SSS paper mining
[ ] aircraft synthetic generator
[ ] ship/wreck hard-negative bank
```

---

# 42. Source index

## Ghost / gear
1. GhostVision HF  
   https://huggingface.co/datasets/PINGEcosystem/sss-crab-pot-detection-ds

2. GhostVision GitHub  
   https://github.com/PINGEcosystem/GhostVision

3. GhostVision Zenodo  
   https://zenodo.org/records/20056679

4. GhostNetZero  
   https://ghostnetzero.ai/

5. GhostNetZero manuscript  
   https://ecoevorxiv.org/repository/object/10294/download/19035/

6. DFO AI portal / Ghost Gear Detection  
   https://ocds-ai-portal.canadacentral.cloudapp.azure.com/details/

7. DFO lost gill nets report  
   https://waves-vagues.dfo-mpo.gc.ca/library-bibliotheque/145861.pdf

8. Mullica River–Great Bay DFG study  
   https://www.sciencedirect.com/science/article/pii/S0025326X18307707

9. Stockton Marine Field Station  
   https://www.stockton.edu/marine/marine-debris.html

10. Salish Sea crab-pot StoryMap  
    https://storymaps.arcgis.com/stories/1befb7cae32f49e89d8595d8ae884d38

11. GGGI Pacific Northwest  
    https://global-ghost-gear.squarespace.com/projects/signature-pnw

12. Chiniak Bay ghost pots paper  
    https://www.researchgate.net/publication/242471543_Ghost_fishing_by_Tanner_crab_Chionoecetes_bairdi_pots_off_Kodiak_Alaska_Pot_density_and_catch_per_trap_as_determined_from_sidescan_sonar_and_pot_recovery_data

13. ALDFG SSS evaluation paper  
    https://www.researchgate.net/publication/372158149_Evaluating_the_use_of_side_scan_sonar_for_improved_detection_and_targeted_retrieval_of_abandoned_lost_or_otherwise_discarded_fishing_gear

14. NKSID  
    https://github.com/Jorwnpay/NK-Sonar-Image-Dataset

## Plane / aircraft
15. SeabedObjects  
    https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset

16. KLSG-II  
    https://github.com/HHUCzCz/-SeabedObjects-KLSG--II

17. Roboflow SSS Plane/Ship  
    https://universe.roboflow.com/dae-hyeok-lee/side-scan-sonar

18. Alternate Roboflow project  
    https://universe.roboflow.com/college-qscys/side-scan-sonar-mg4j8

19. SonarVision v6  
    https://huggingface.co/datasets/Dinoman1221/sonarvision-multisource-v6

20. SonarVision project  
    https://github.com/Dinoman67/sonarvision

21. SCTD  
    https://github.com/MingqiangNing/SCTD

22. NOAA B-29  
    https://oceanexplorer.noaa.gov/multimedia/explorations-22saipan-surveys-gallery-media-b-29-2/

23. NOAA Saipan expedition  
    https://oceanexplorer.noaa.gov/expedition/22saipan-surveys/

24. NOAA SSS technology examples  
    https://oceanexplorer.noaa.gov/technology/sonar-side-scan/

25. UB88 SSS archive  
    https://www.ub88.org/sidescansonar/side-scan-sonar.html

26. UB88 TBM Avenger  
    https://www.ub88.org/researchprojects/tbmavenger/tbm-avenger.html

27. Pacific Wrecks TBM Avenger SSS  
    https://pacificwrecks.com/aircraft/tbm/45810/2014/sss-fan-avenger.html

28. Wessex Archaeology aircraft sonar  
    https://www.flickr.com/photos/wessexarchaeology/4438313886/

29. NOAA missing-plane SSS case  
    https://nauticalcharts.noaa.gov/updates/from-historic-air-disasters-to-todays-hurricane-response-noaa-uses-cutting-edge-science-to-survey-the-seafloor/

30. Lake Mead B-29 / SSS discovery  
    https://www.nps.gov/lake/learn/historic-lake-mead-b-29.htm

31. BES-YOLO / SSS dataset paper  
    https://pmc.ncbi.nlm.nih.gov/articles/PMC11281110/

32. NOAA generic SSS imagery  
    https://oceanexplorer.noaa.gov/multimedia/sonar-imagery/

33. NOAA/NCEI Okeanos cruise data  
    https://www.ncei.noaa.gov/waf/okeanos-rov-cruises/ex1711/

34. Historic NOAA sonar image example  
    https://www.noaa.gov/noaa-collections/photo-library/cgs01170jpg

---

# 43. Research notes / evidence captured during source review

### GhostVision
The current GhostVision dataset page describes 6,674 annotated SSS images from consumer-grade Humminbird sonar. The 2026 GhostVision publication describes a manually annotated model-development subset and field workflow.

### DFO Ghost Gear
The DFO AI portal explicitly reports a ghost-gear detector trained on 1,009 SSS images with 1,568 lobster-trap localizations, 1,068 rope localizations and 66 negatives.

### GhostNetZero
The GhostNetZero research lead is particularly relevant because it concerns actual ghost nets rather than merely crab pots. Its reported study data are 239 Baltic and 173 Puget Sound annotated segments.

### Plane datasets
SeabedObjects explicitly reports 62 real airplane sonar images. Roboflow provides a 550-image Ship/Plane object-detection dataset. SonarVision v6 provides a larger multi-source SSS dataset with an explicit airplane class.

### Government/image archives
NOAA and institutional archaeology pages contain real aircraft SSS imagery that is rarely indexed as an “ML dataset”. These images should be treated as image-only/weak-label data unless original annotations are available.

---

# 44. Recommended exact data pipeline for your project

```text
                 ┌─────────────────────────────┐
                 │       DATA SOURCES           │
                 └──────────────┬──────────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
       ▼                        ▼                        ▼
  READY DATASETS          RARE RAW/IMAGE        REQUEST DATA
       │                        │                        │
       │                        │                        │
       └───────────────┬────────┴───────────────┬────────┘
                       ▼                        ▼
                 PROVENANCE STORE         LICENSE CHECK
                       │                        │
                       └────────────┬───────────┘
                                    ▼
                             DEDUPLICATION
                                    │
                                    ▼
                           LABEL NORMALIZATION
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
         REAL LABELLED         WEAK LABELLED         UNLABELLED
              │                     │                     │
              ▼                     ▼                     ▼
          TRAIN/VAL             REVIEW QUEUE         SELF-SUP
              │                     │                     │
              └──────────────┬──────┴──────────────┬──────┘
                             ▼                     ▼
                       HARD NEGATIVE          SYNTHETIC
                             │                     │
                             └──────────┬──────────┘
                                        ▼
                                 YOLO/SEG TRAINING
                                        │
                                        ▼
                              SITE-DISJOINT TESTING
                                        │
                                        ▼
                           SIH DEPLOYMENT / EDGE MODEL
```

---

# 45. Final practical recommendation

Do **not** wait for someone to publish a perfect “Ghost Net + Plane SSS dataset”.

Build a two-tier corpus:

## Tier A — benchmark-quality real data
- GhostVision
- GhostNetZero
- DFO/CSR
- SeabedObjects
- KLSG-II
- Roboflow Plane
- SonarVision
- independently sourced NOAA aircraft

## Tier B — rare expansion data
- government report figures
- Stockton
- Salish Sea
- Mullica
- Chiniak Bay
- GGGI
- UB88
- Pacific Wrecks
- Wessex
- NOAA/NCEI
- unlabeled SSS archives
- weak labels
- synthetic augmentation

This gives you a much stronger data story than simply combining common Kaggle/Roboflow datasets.

**Do not describe every source as a “downloadable dataset”.** Clearly mark the rare research sources as request/reference/image-only until you obtain their actual files and rights.


---

# 46. Newly verified sources found after the first version

**Important:** The previous version was not literally exhaustive. There is no reliable way to prove that every SSS dataset on the entire internet has been found. The sources below were found in an additional targeted search and were missing from the first version.

## 46.1 YDY-andy / Sonar-dataset — raw side-scan sonar repository

GitHub:
https://github.com/YDY-andy/Sonar-dataset

The repository describes itself as a dataset collected from **side-scan sonar**, with `images/` and `annotation/` folders. It is not a clean ghost-net/plane-only benchmark, so it should be treated as an **unlabeled/mixed SSS source** and inspected for target candidates and hard negatives.

Status:
- 🔵/🟡 SSS raw/mixed dataset
- likely useful for unlabeled SSS pretraining
- inspect annotations before assigning class labels

---

## 46.2 Ilia-Abolhasani / side-scan-sonar-segmentation

GitHub:
https://github.com/Ilia-Abolhasani/side-scan-sonar-segmentation

This project includes:
- `Dataset/`
- `Images/`
- trained segmentation artifacts
- notebooks
- a long-image seabed segmentation workflow

It is useful primarily as:
- SSS segmentation data/benchmark lead
- long sonar-strip training data
- background/hard-negative source

Do not assume it contains ghost nets or planes until the actual image/class files are audited.

Status:
- 🔵 SSS dataset lead
- ⚠️ target classes need audit

---

## 46.3 NNSSS — Multi-Class Segmentation of Side-Scan Sonar Data

GitHub:
https://github.com/aburguera/NNSSS

The repository includes an actual `DATASET` folder:

```text
DATA/
GT/
```

The README states:
- `DATA` contains informative acoustic SSS images
- images are grayscale PNG
- paired port/starboard transect images
- `GT` contains hand-labelled ground truth
- pixel values represent three classes

This is a useful **real labeled SSS segmentation dataset**, especially for:
- seabed/background learning
- acoustic segmentation
- hard-negative mining
- anomaly/unknown-object detection

It is not a dedicated ghost-net or plane dataset, so use it as supporting SSS data.

---

# 47. Newly verified aircraft/plane dataset leads

## 47.1 BES-YOLO / DBnet research corpus — aircraft count clarification

A review of the underlying papers gives more precise numbers than the earlier generic description.

The DBnet paper reports:

**Dataset A**
- 980 shipwreck images
- 36 drowned-person images
- **568 airplane-wreck images**

**SCTD**
- 266 shipwreck images
- 34 drowned-person images
- **57 airplane-wreck images**

Source:
https://www.mdpi.com/2073-4433?  # See original DBnet paper citation/references in your research workflow.
Direct paper:
https://www.mdpi.com/2077-1312/13/1/155

The broader BES-YOLO paper describes a separate **1,584-image SSS corpus** containing shipwreck, airplane-wreckage and human imagery from multiple sonar instruments and regions.

Use these as **research corpus leads**, and trace the cited upstream datasets before treating them as independent data.

---

## 47.2 Roboflow 100-VL SSS airplane subset

Roboflow search exposes a public family of datasets containing:
- airplane
- human
- shipwreck

Examples include:
- `sssod-hdha`
- `sssod-uaagn`
- `sssod-fsod`

The search index currently shows:
- about 443 images for one public SSS object-detection subset
- about 109 images for an FSOD airplane subset
- additional plane/ship/wreck variants

Search:
https://universe.roboflow.com/search?q=airplane+side+scan+sonar

**Critical:** some of these are likely subsets/derivatives of the same upstream SSS corpus. Hash and provenance-audit before counting them as new independent samples.

---

## 47.3 Additional Roboflow SSS datasets

Public search also exposes:
- `Side Scan Files` — about 1.03k images, planeship
- `sonar-yolo-2` — about 1.92k images, planeship
- `sonar image` — about 661 images in one instance-segmentation workspace
- `YOLO` — about 1.12k images
- `sonar-yolo` / other planeship collections

Start here:
https://universe.roboflow.com/search?q=side+scan+sonar+plane

These are **discovery sources**, not automatically independent datasets.

Recommended process:
1. Download metadata/listing.
2. Hash images.
3. Compare to SeabedObjects / Roboflow 550 / KLSG.
4. Keep only genuinely new images or new labels.
5. Store original workspace and version.

---

# 48. Newly discovered Ghost-Gear / Ghost-Net field data leads

## 48.1 Narragansett Bay — approximately 2,200 ghost traps

Commercial Fisheries Research Foundation:
https://www.cfrfoundation.org/locating-ghost-gear-targets-and-evaluating-removal-efforts-in-narragansett-bay

The project reports a directed side-scan sonar survey by CSR GeoSurvey in August 2023 that found approximately:

**2,200 ghost traps**

for removal in Narragansett Bay.

The program continued side-scan surveys in 2025 and 2026 and states an intention to disseminate collected data.

This is one of the most important **new request-data targets**.

Ask for:
- original SSS imagery
- target CSV
- GPS coordinates
- pre/post-removal surveys
- gear type
- confirmed vs probable targets

---

## 48.2 Narragansett Bay 2025 removal survey

CFRF's 2025 update reports:
- 7 surveys completed
- **269 traps removed**
- 4,220 pounds scrap metal
- 1,368 pounds rope
- approximately 200 pounds plastic removed

Source:
https://www.cfrfoundation.org/news/2025/8/7/2025-ghost-gear-removal-updates

The project says it is analyzing and publishing data about:
- gear type
- location
- depth
- substrate
- trap age
- bycatch
- ghost escape vents

This is highly useful for **field-verified labels and metadata**, even if the raw sonar archive still requires access.

---

## 48.3 Gulf of Maine — nearly 1,300 ALDFG side-scan targets

GGGI:
https://www.ghostgear.org/projects/signature-gulfofmaine

The project reports:
- CSR GeoSurveys side-scan sonar
- Casco Bay, Maine
- nearly **1,300 ALDFG targets**
- eight days of surveys
- April 26–May 9, 2023
- more than 1,200 possible targets at one priority site

This is a very strong raw-data/request lead.

---

## 48.4 Maine 2025 Klein 4900 pilot survey

General Oceans Foundation:
https://www.generaloceansfoundation.com/news/maine-ghost-gear-detection-with-side-scan-sonar

During Autumn 2025, Boothbay Harbor surveys used:
- **Klein 4900 side-scan sonar**
- multiple frequencies
- multiple ranges
- mud, sand and rock substrates
- detection out to about 75 m on each side

Images shown on the project page include:
- shipwreck surrounded by ghost lobster traps
- active traps connected by rope
- sonar-labelled gear scenes

This is a rare modern real-world SSS source and a **data-contact target**.

---

## 48.5 Vancouver Island — real nets AND traps, ground-truthed with ROV

Rugged Coast Research Society:
https://www.ruggedcoastresearchsociety.com/projects/1decwrnj77bawypdv9agbi608b7zd9

Project:
- Kyuquot Sound
- Hesquiaht Harbour
- west coast of Vancouver Island
- October 2022–February 2023
- side-scan sonar + submersible ROV
- located, ground-truthed and removed derelict **fishing nets and traps**
- approximately **1.5 tonnes of ghost gear removed**

This is especially important because it explicitly includes **nets**, not only traps.

Use as a research/data-request lead and image-mining source.

---

## 48.6 New Hampshire / Portsmouth / Isles of Shoals

NH Marine Debris:
https://nhmarinedebris.org/debris/sonarimages.cfm

Reported:
- initial SSS survey: September 16, 2008
- follow-up: August 2011
- survey areas include Portsmouth, Rye and Isles of Shoals
- approximately **28.64 miles of waters** surveyed
- objective: identify derelict lobster traps

This page contains actual sonar-result imagery and is useful as:
- ghost-gear image-only source
- hard-negative source
- potential archive/contact lead

---

## 48.7 Massachusetts / Cape Cod — long-running ghost-gear sonar program

Center for Coastal Studies:
https://coastalstudies.org/news/center-for-coastal-studies-announces-ghost-gear-removal-program-for-2025/

Program uses SSS in:
- Cape Cod Bay
- Boston Harbor
- Stellwagen Bank National Marine Sanctuary

The program reports:
- annual effort since 2013
- more than **86 tons** ghost gear removed from Cape Cod Bay
- 857 lobster traps returned to owners since 2013

The SSS surveys are explicitly intended to locate gear before retrieval.

This is another high-value **real survey data request**.

Contact details on page include:
- Laura Ludwig
- Owen Nichols
- Fritz McGirr

---

# 49. More “non-dataset” but valuable data sources

## 49.1 Institutional Flickr / photo archives

Search:
```text
site:flickr.com "side scan sonar" aircraft
site:flickr.com "side scan sonar" ghost gear
site:flickr.com "side scan sonar" fishing
site:flickr.com "side scan sonar" wreck
```

Potential institutional sources:
- Wessex Archaeology
- NOAA
- museums
- university marine labs
- archaeology contractors

Treat these as image-only/weak-label sources.

---

## 49.2 ArcGIS StoryMaps

Search:
```text
site:storymaps.arcgis.com "side scan sonar" ghost gear
site:storymaps.arcgis.com "side scan sonar" aircraft
site:storymaps.arcgis.com "ghost gear" sonar
```

StoryMaps often contain:
- sonar screenshots
- map coordinates
- target descriptions
- field verification
- before/after removal information

This makes them valuable for weak labels and metadata.

---

## 49.3 Government data portal search

Search:

```text
site:data.gov sonar wreck
site:data.gov side scan sonar
site:data.gov ghost gear
site:ncei.noaa.gov side scan sonar
site:oceanexplorer.noaa.gov side scan sonar
site:dfo-mpo.gc.ca side scan sonar
site:canada.ca ghost gear sonar
site:boem.gov side scan sonar wreck
site:usgs.gov side scan sonar
```

Look for:
- XTF
- JSF
- GeoTIFF
- sonar mosaic
- survey report
- target list
- GIS layer
- cruise archive

---

# 50. NEW master list — what to add beyond the previous version

## Ghost / Ghost Gear

### Direct / dataset-like
- GhostVision — 6,674 SSS images
- GhostVision Zenodo package
- NKSID Fishing Net — auxiliary, not SSS

### True ghost-net / high-value request
- GhostNetZero — 412 reported annotated real ghost-net segments
- DFO lost gill-net SSS report
- DFO/CSR GeoSurveys — 1,009 SSS images
- Rugged Coast — Vancouver Island nets + traps
- Mullica River–Great Bay — 2,218 probable DFG targets
- Narragansett Bay — ~2,200 ghost traps
- Gulf of Maine / Casco Bay — ~1,300 ALDFG targets
- Chiniak Bay — 189 putative lost pots
- Stockton
- Salish Sea
- GGGI PNW
- NH Portsmouth / Isles of Shoals
- Maine 2025 Klein 4900
- Massachusetts/Cape Cod
- GGGI Gulf of Maine/Rhode Island
- other DFO Ghost Gear Fund projects

### Generic/raw SSS
- YDY-andy/Sonar-dataset
- NNSSS
- Ilia-Abolhasani SSS segmentation project

---

# 51. UPDATED plane/aircraft master list

### Direct / labeled
- SeabedObjects Ship + Airplane
- KLSG-II
- Roboflow Dae Hyeok Lee 550
- SonarVision Multi-Source v6
- SCTD aircraft subset
- Roboflow 100-VL SSS aircraft subsets
- DBnet Dataset A — 568 airplane-wreck images
- SCTD in DBnet paper — 57 airplane-wreck images

### Real image/archive sources
- NOAA B-29
- NOAA B-25
- NOAA Saipan/Tinian expedition
- UB88
- TBM Avenger
- Pacific Wrecks
- Wessex Archaeology
- NOAA missing-plane operational case
- Lake Mead B-29
- other NOAA aircraft/wreck images

### Additional mixed SSS
- BES-YOLO 1,584-image corpus
- Roboflow `Side Scan Files`
- Roboflow `sonar-yolo-2`
- Roboflow plane/ship datasets
- institutional SSS archives

---

# 52. Data that should NOT be counted as independent

Be careful with:

```text
DRISHTI
Roboflow Plane/Ship
KLSG
KLSG-II
SonarVision
BES-YOLO
SCTD
various GitHub mirrors
```

Some are assembled or derived from common upstream data.

**Always record:**

```text
original_source
derived_source
duplicate_group
source_hash
parent_dataset
```

The goal is not a huge inflated number. The goal is a large amount of **genuinely diverse sonar scenes**.

---

# 53. Final answer to “is everything included?”

**No — the first file was not literally every possible dataset on the internet.**

After another targeted search, I found additional relevant sources that were missing from it, especially:

1. **YDY-andy Sonar-dataset** — public raw SSS repository.
2. **NNSSS** — real labeled SSS segmentation dataset.
3. **Ilia-Abolhasani SSS segmentation dataset/project**.
4. **DBnet Dataset A — 568 airplane-wreck images**.
5. **Additional Roboflow 100-VL / SSS airplane subsets**.
6. **Narragansett Bay — ~2,200 ghost traps**.
7. **Gulf of Maine — ~1,300 ALDFG targets**.
8. **Rugged Coast — real nets + traps, side-scan + ROV ground truth**.
9. **New Hampshire — 28.64-mile SSS ghost-gear survey**.
10. **Maine 2025 Klein 4900 survey**.
11. **Massachusetts/Cape Cod long-running SSS ghost-gear program**.

Therefore, the safest claim for your SIH documentation is:

> **“Comprehensive curated dataset-source library assembled from public datasets, research corpora, government reports, institutional archives, field-survey programs, data-request targets, unlabeled SSS repositories, weak-label sources, and synthetic augmentation opportunities.”**

Do **not** say “all datasets in the world” because new/private/unindexed datasets can exist and some source collections are not public.


---

# 54. GLOBAL-WORLDWIDE COVERAGE: add these sources too

This section is added specifically to move the library closer to a worldwide source map.

## 54.1 Global Ghost Gear Initiative (GGGI) Data Portal — worldwide ALDFG records

Portal:
https://www.ghostgear.org/dataportal

This is not a pure SSS image dataset. It is a **global ghost-gear record system** and is therefore important for the project’s metadata and geographic expansion.

The portal describes itself as a publicly accessible database containing **thousands of ALDFG records submitted by organizations around the world**. It also states that historical versions contained more than **300,000 ALDFG data records** from dozens of organizations.

Available information can include:
- geographic position / GSP coordinates
- gear type
- time observed
- submitting organization, depending on sharing level
- contributor/source attribution

Use it for:
- global ghost-gear occurrence priors
- selecting candidate countries/regions for SSS source hunting
- geographic balancing
- GIS metadata
- identifying organizations that may possess raw sonar surveys

**Do not treat GGGI point records as sonar images.**

The portal also has a resource library with **700+ publications**, which is an unusually useful secondary source-discovery mechanism.

---

## 54.2 GGGI Side-Scan Sonar project directory

https://www.ghostgear.org/projects/category/Side%2BScan%2BSonar%2BSurveys

This directory currently identifies multiple GGGI projects under the specific category:

**Side Scan Sonar Surveys**

Project pages are separated into:
- GGGI Signature Projects
- GGGI Small Grants

This should be treated as a **global project index**, not one dataset.

Search every project page for:
- sonar imagery
- target maps
- survey organizations
- contact persons
- data-sharing arrangements
- reports
- downloadable attachments

---

# 55. New ghost-net / fishing-net SSS research datasets and image sources

## 55.1 Fishing-net SSS segmentation dataset — Jiaozhou Bay / Ocean University of China

Research paper:
https://www.sciencedirect.com/science/article/abs/pii/S0141118721000857

The paper states that its experiments use **three SSS datasets**:
- sand waves
- coral reefs
- **fishing nets**

The work reports thousands of augmented patches for experimentation and explicitly evaluates segmentation on SSS fishing-net images.

This is a **high-value dataset-discovery lead** because it is one of the sources specifically described as SSS fishing-net segmentation data rather than generic sonar.

Important:
- distinguish original fishing-net images from augmented patches
- find the authors/repository/supplementary data before counting it as a downloadable independent dataset
- do not count augmented copies as independent real scenes

Status:
- 🟣 REQUEST/RESEARCH DATASET LEAD

---

## 55.2 Taganrog Bay / Russia — fishing-net SSS images

Article:
https://izv.etu.ru/en/archive/2021/3/10-16

Title:
**APPLICATION OF SIDE-SCAN SONAR TO LOCATE FISHING NETS**

The study describes 2017 experimental work in **Taganrog Bay** by researchers from Southern Federal University and NOLACS.

It contains:
- actual acoustic images of fishing nets
- SSS system description
- test conditions
- sonar characteristics
- discussion of acoustic shadows
- net-in-water detection

This is an excellent rare source for:
- real fishing-net morphology
- different acoustic conditions
- weak-label image extraction
- researcher contact/data request

Status:
- 🔵 IMAGE-ONLY / 🟣 RESEARCH REQUEST

---

## 55.3 Ghost Nets in Danish Waters — DTU Aqua

Main report:
https://orbit.dtu.dk/en/publications/ghost-nets-in-danish-waters/

Appendices:
https://orbit.dtu.dk/en/publications/ghost-nets-in-danish-waters-appendices/

Direct appendices PDF:
https://www.aqua.dtu.dk/-/media/institutter/aqua/publikationer/rapporter-352-400/appendices_ghost-nets-in-danish-waters.pdf

Direct report PDF:
https://www.aqua.dtu.dk/-/media/institutter/aqua/publikationer/rapporter-352-400/394-2021_ghost-nets-in-danish-waters.pdf

Important facts:
- DTU Aqua / Danish research program
- report published 2022
- appendices contain **173 pages**
- survey equipment included **EdgeTech 4125 dual-frequency side-scan sonar**
- frequencies: **600 / 1600 kHz**
- nominal range: about **25 m each side**
- navigation: AtlasLink A326
- Blue Robotics BlueROV2 used for visual confirmation
- SonarWiz used for post-processing

This is one of the strongest sources for:
- modern high-frequency SSS
- actual ghost-net survey design
- visual confirmation / ground truth
- sonar + ROV pairing
- acoustic environmental variation

Status:
- 🔵 REPORT/IMAGE DATA
- 🟣 potential research-data request

---

# 56. Ghost-net data that should be pursued directly from project owners

## 56.1 Narragansett Bay / Rhode Island

CFRF:
https://www.cfrfoundation.org/locating-ghost-gear-targets-and-evaluating-removal-efforts-in-narragansett-bay

Reported:
- directed SSS survey in August 2023
- approximately **2,200 ghost traps**
- CSR Geosurvey
- follow-up removals
- project continuing through 2026
- project explicitly says it will disseminate collected data

This should be classified:

`REQUEST-DATA / HIGH PRIORITY`

---

## 56.2 Gulf of Maine / Casco Bay

GGGI:
https://global-ghost-gear.squarespace.com/projects/signature-gulfofmaine

Reported:
- CSR GeoSurveys
- side-scan sonar
- nearly **1,300 ALDFG targets**
- April–May 2023
- subsequent retrieval of identified gear

Class:
`REQUEST-DATA / HIGH PRIORITY`

---

## 56.3 Maine — Klein 4900

General Oceans Foundation:
https://www.generaloceansfoundation.com/news/maine-ghost-gear-detection-with-side-scan-sonar

Reported:
- autumn 2025
- Boothbay Harbor
- Klein 4900
- multiple frequencies/ranges
- mud, sand and rock seabed
- examples show ghost traps/rope and wreck + ghost gear

This is useful for **modern multi-frequency hard-negative / domain-shift** testing.

---

## 56.4 Vancouver Island — ghost nets + traps + ROV

Rugged Coast:
https://www.ruggedcoastresearchsociety.com/projects/1decwrnj77bawypdv9agbi608b7zd9

Reported:
- Kyuquot Sound / Hesquiaht Harbour
- 2022–2023
- SSS and ROV
- derelict nets and traps
- approximately 1.5 tonnes of ghost gear removed

This is one of the best external leads for true `ghost_net`, because it is not limited to pots.

---

# 57. Additional aircraft-specific real SSS research source

## 57.1 Baltic Sea underwater airplane wreck — Poland

Paper:
https://www.mdpi.com/2072-4292/14/20/5195

The survey used:
- **Klein 3900**
- **455 / 900 kHz**
- 200 m Kevlar tow cable
- SonarPro
- towing speed about 3.5 knots
- survey lines parallel to aircraft wings and at 45°
- subsequent scanning sonar and ROV verification

The study reports SSS imagery of the airplane wreck and ROV observations including:
- right wing
- cockpit
- left wing
- propeller
- detached tail
- engine cover
- nets associated with the wreck

This is valuable for:
- plane SSS imagery
- different look angles
- partial-aircraft labels
- aircraft debris
- net-on-wreck hard cases

Status:
- 🔵 IMAGE/RESEARCH SOURCE
- 🟣 data request candidate

---

# 58. SSS synthetic benchmark source — S3Simulator

ResearchGate:
https://www.researchgate.net/publication/389288054_S3Simulator_A_Benchmarking_Side_Scan_Sonar_Simulator_Dataset_for_Underwater_Image_Analysis

S3Simulator combines:
- 3D object models
- computer simulation
- sonar simulation
- real SSS references

It specifically uses aircraft/ship silhouettes and the SeabedObjects-KLSG data as real sonar reference.

Use this source for:
- aircraft synthetic expansion
- simulator validation
- zero/few-shot experiments
- comparing synthetic vs real sonar appearance

Class:
`SYNTHETIC / AUXILIARY`

Never merge it into the real-plane benchmark without a `synthetic=true` field.

---

# 59. Large aircraft synthetic-generation evidence

## 59.1 Zero/Few-Sample SSS Generation

Paper:
https://doi.org/10.3390/rs16224134

The paper reports:
- SeabedObjects-KLSG real sonar
- 66 airplane images
- 487 shipwreck images
- 578 seabed images
- Blender/Isaac Sim 3D models
- UA-CycleGAN transfer
- ADA-StyleGAN3 sonar generation
- **2,400 generated sonar images**

This is not a replacement for real airplane SSS, but it is a very strong source for your **advanced synthetic/low-data augmentation branch**.

---

# 60. Underwater rescue/aircraft augmented sonar dataset

A related sonar-target recognition study reports creation of **6,000 sonar images** through augmentation:
- 1,200 airplanes
- 1,200 ships
- 1,200 seabeds
- 1,200 airplane tails
- 1,200 airplane wings

The paper states the underlying real SSS data came from SeabedObjects-KLSG and that the augmented set was divided into training and validation data.

Important:
- these are **augmented derivatives**, not 6,000 independent real sonar scenes
- keep them in `derived_augmented`, not `real`
- aircraft tail/wing labels can be useful for partial-target detection

---

# 61. Improved SSS recognition paper — another source map

The literature around SeabedObjects-KLSG identifies these supplier/source lineages:
- L-3 Klein Associates
- EdgeTech
- Lcocean
- Hydro-tech Marine
- Tritech

The dataset accumulated over years and includes:
- aircraft
- shipwreck
- seabed
- in some publications additional drowning-person and mine classes

Use the supplier list as a **source-expansion trick**:
search each supplier + exact target + `side scan sonar` + `dataset`.

---

# 62. Worldwide data-source strategy

Because the user requested “all available in the whole world”, use the following hierarchy.

## Level 0 — globally indexed portals

```text
GGGI Data Portal
NOAA / NCEI
Government data portals
Zenodo
Figshare
Dryad
PANGAEA
Mendeley Data
Hugging Face
GitHub
Roboflow
Kaggle
institutional repositories
```

## Level 1 — academic dataset papers

Search:
```text
"side scan sonar" dataset
"side-scan sonar" dataset
"SSS images" aircraft
"SSS images" fishing nets
"sonar images" ghost gear
"side scan sonar" derelict gear
```

## Level 2 — government reports

```text
NOAA
DFO Canada
DTU Aqua / Danish agencies
USGS
NPS
BOEM
marine resources departments
hydrographic offices
```

## Level 3 — archaeology / wreck archives

```text
NOAA Ocean Exploration
UB88
Pacific Wrecks
Wessex Archaeology
maritime museums
university archaeology labs
shipwreck survey contractors
```

## Level 4 — project/contact mining

Any project with:
```text
side scan survey
ghost gear
ALDFG
wreck mapping
aircraft search
```

becomes a data-request lead.

---

# 63. Worldwide region checklist

Use this as a search checklist so entire geographic groups are not ignored.

## North America
```text
USA
Canada
Alaska
Pacific Northwest
California
Gulf of Mexico
New England
Great Lakes
Hawaii
Puerto Rico
US Virgin Islands
```

## Europe
```text
UK
Ireland
Denmark
Norway
Sweden
Finland
Germany
Netherlands
Belgium
France
Spain
Portugal
Italy
Greece
Croatia
Poland
Baltic Sea
Mediterranean
North Sea
Black Sea
```

## Asia
```text
Japan
South Korea
China
Taiwan
India
Indonesia
Philippines
Vietnam
Thailand
Malaysia
Singapore
Sri Lanka
Bangladesh
```

## Oceania
```text
Australia
New Zealand
Papua New Guinea
Pacific islands
Micronesia
Polynesia
Melanesia
```

## Africa
```text
South Africa
Namibia
Mozambique
Tanzania
Kenya
Ghana
Nigeria
Morocco
Egypt
Mediterranean Africa
```

## South / Central America
```text
Brazil
Argentina
Chile
Peru
Ecuador
Colombia
Mexico
Caribbean
Central America
```

**Note:** a region listed here is a search target, not proof that an open SSS ghost-net/aircraft dataset exists there.

---

# 64. “World search” source-discovery query pack

## Ghost nets

```text
"side scan sonar" "ghost net" [country]
"side scan sonar" "ghost gear" [country]
"side scan sonar" "derelict fishing gear" [country]
"side scan sonar" "lost fishing net" [country]
"side scan sonar" "lost gill net" [country]
"side scan sonar" "lost crab pot" [country]
"side scan sonar" "abandoned fishing gear" [country]
```

## Plane

```text
"side scan sonar" aircraft [country]
"side scan sonar" airplane wreck [country]
"side scan sonar" aircraft wreck [country]
"side scan sonar" WWII aircraft [country]
"side scan sonar" submerged aircraft [country]
```

## Raw files

```text
"XTF" sonar aircraft
"XTF" sonar ghost gear
"XTF" "side scan sonar" dataset
"JSF" side scan sonar dataset
"GeoTIFF" "side scan sonar" wreck
"SonarWiz" ghost gear
"SonarPro" aircraft sonar
```

---

# 65. Source classification that should be enforced

Every discovered item must be assigned exactly one primary source class:

```text
REAL_LABELED
REAL_UNLABELED
REAL_WEAK_LABEL
REAL_FIELD_VERIFIED
REAL_REQUEST_DATA
AUXILIARY_SONAR
DERIVED_AUGMENTED
SYNTHETIC
SIMULATED
IMAGE_ARCHIVE
PAPER_FIGURE
METADATA_ONLY
```

This prevents your final dataset from claiming synthetic or paper-derived samples are raw real-world measurements.

---

# 66. Recommended master database tables

## datasets

```text
dataset_id
dataset_name
target_family
modality
region
country
source_url
download_url
access_type
license
license_verified
image_count
label_count
real_or_synthetic
primary_or_auxiliary
duplicate_group
notes
```

## images

```text
image_id
dataset_id
scene_id
source_scene_id
filename
sha256
phash
width
height
modality
class
label_type
bbox
mask
lat
lon
depth
frequency_khz
range_m
sensor
survey_id
license
```

## requests

```text
request_id
organization
project
country
target
data_type
contact_url
date_contacted
status
response
permission
```

---

# 67. Acquisition priority after the worldwide expansion

## Ghost Net — highest-value targets

```text
A1 GhostNetZero
A2 DFO/CSR GeoSurveys
A3 GhostVision
A4 DTU Aqua Denmark
A5 Narragansett Bay
A6 Gulf of Maine
A7 Vancouver Island
A8 Mullica River / Great Bay
A9 Chiniak Bay
A10 Stockton
A11 Salish Sea
A12 DFO Hurricane Fiona projects
A13 New Hampshire
A14 Maine Klein 4900
A15 Cape Cod
A16 Taganrog Bay
A17 Jiaozhou Bay fishing-net SSS
A18 GGGI global project directory
A19 GGGI Data Portal
```

## Plane — highest-value targets

```text
B1 SeabedObjects
B2 KLSG-II
B3 Roboflow SSS Plane
B4 SonarVision v6
B5 DBnet aircraft corpus
B6 SCTD aircraft
B7 NOAA B-29
B8 NOAA B-25
B9 NOAA Saipan/Tinian
B10 Baltic Sea Poland aircraft wreck
B11 UB88 aircraft archive
B12 TBM Avenger
B13 Pacific Wrecks
B14 Wessex Archaeology
B15 NOAA missing-aircraft case
B16 Lake Mead B-29
B17 Roboflow SSS aircraft subsets
B18 S3Simulator
B19 SSS synthetic-generation datasets
```

---

# 68. IMPORTANT: what “all worldwide data” can realistically mean

There are four different universes of data:

### Public downloadable
You can obtain the actual file now.

### Publicly viewable
You can see an image/report but the original training archive is not supplied.

### Requestable
The project states or strongly implies that underlying survey data can be requested/shared.

### Private/unpublished
Only researchers/organizations hold the data.

No public web search can honestly guarantee enumeration of the fourth category.

Therefore your master library should call itself:

**GLOBAL SSS TARGET-DATA SOURCE LIBRARY**

rather than:
**ALL SONAR DATA IN THE WORLD**

This is important for academic and SIH credibility.

---

# 69. Final expanded source families

The master library now covers:

```text
1. Ready-to-download SSS datasets
2. Ghost-net / ghost-gear datasets
3. Fishing-net SSS segmentation sources
4. Crab-pot SSS sources
5. Rope/cable auxiliary ghost-gear sources
6. Plane/aircraft SSS datasets
7. Aircraft wreck image archives
8. Government sonar reports
9. Archaeological sonar archives
10. Research-paper datasets
11. Request-only research data
12. Global ghost-gear data portals
13. Raw XTF/JSF data leads
14. GeoTIFF/mosaic sources
15. Image-only weak-label sources
16. Unlabeled SSS repositories
17. SSS segmentation datasets
18. Sonar auxiliary modalities
19. Synthetic SSS generation datasets
20. Simulated aircraft sonar
21. Synthetic ghost-net generation
22. Hard-negative sources
23. Geographic-domain expansion
24. Active-learning data mining
25. Provenance / license / deduplication
26. Site-disjoint evaluation
27. Field-verification links
28. ROV-confirmed targets
29. Pre/post-removal ghost-gear surveys
30. Global project/contact discovery
```

---

# 70. Current completeness statement

After the additional global search, this library is **substantially more comprehensive** than the previous version.

It includes:
- known downloadable sources
- less-obvious GitHub repositories
- academic research datasets
- actual fishing-net SSS segmentation sources
- government reports
- large ghost-gear survey programs
- worldwide GGGI data infrastructure
- aircraft research cases
- image archives
- request-only raw data
- synthetic and simulated sources
- auxiliary sonar datasets
- geographic expansion routes

However, **it is still impossible to guarantee that literally every private, unpublished, newly-created, paywalled, login-only, or unindexed SSS dataset on Earth has been enumerated**.

The correct engineering objective is therefore to use this master list as the **global discovery and acquisition registry**, and continually add newly discovered sources with provenance rather than pretending a static web search is permanently complete.
