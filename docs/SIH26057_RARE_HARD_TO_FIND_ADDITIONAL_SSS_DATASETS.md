# SIH26057 GhostNet-AI — Rare / Hard-to-Find Additional SSS Sources

This is an **add-on** to the datasets already used in the project. It intentionally avoids simply repeating AI4Shipwrecks, GhostVision, SubPipe, SeabedObjects, and the common Roboflow source.

## 1. SonarVision Multi-Source v6 — strongest new ready-to-use source

A newer multi-source Side-Scan Sonar object-detection corpus. Its current dataset card reports **5,558 high-resolution SSS frames** split into 4,033 train, 563 validation, and 962 held-out test frames. Classes include `unknown_debris`, `airplane`, `mine`, and `wreck`. It is packaged in YOLO format. The card says the source combines multiple maritime datasets and reports a 924 MB compressed archive; access currently requires accepting the dataset's access conditions.

Source/download:
https://huggingface.co/datasets/Dinoman1221/sonarvision-multisource-v6

Project/code:
https://github.com/Dinoman67/sonarvision

**Use:** extra `wreck`, `plane`, and `unknown_debris` data; cross-source generalization.

**Do not:** count its upstream images twice if you already use those source datasets.

## 2. NOAA B-29 Wreck — rare real aircraft SSS image

NOAA Ocean Exploration provides a downloadable high-resolution SSS image of the WWII B-29 aircraft wreck near Tinian Island.

Source/download:
https://oceanexplorer.noaa.gov/multimedia/explorations-22saipan-surveys-gallery-media-b-29-2/

**Use:** rare real `plane` example; manually annotate the aircraft for supplemental training/validation if rights permit.

**Important:** this is an image resource, not a labeled dataset. One image must not be presented as a statistically meaningful test set.

## 3. UB88 Side-Scan Sonar archive — rare aircraft + wreck collection

UB88 maintains a gallery of submerged wrecks and obstructions imaged with towed Side-Scan Sonar. The collection includes aircraft-related examples such as TBM Avenger, F-4 Phantom, P-38, Piper Cherokee, plus many shipwrecks and other objects.

Source:
https://www.ub88.org/sidescansonar/side-scan-sonar.html

**Use:** rare image supplementation for `plane` and `wreck`; manual annotation; shadow/shape studies; qualitative external validation.

**Important:** image collection, not a standardized YOLO dataset. Check rights/credit for each image.

## 4. TBM Avenger 45810 — rare aircraft SSS image

Pacific Wrecks provides a Side-Scan Sonar view of the submerged TBM Avenger 45810 crash site, including a high-resolution image option.

Source:
https://pacificwrecks.com/aircraft/tbm/45810/2014/sss-fan-avenger.html

**Use:** rare `plane` sonar appearance, aircraft-wreck geometry, manual annotation, shadow analysis.

**Important:** not a ready training dataset; verify image rights before reuse.

## 5. NOAA Automated Archaeological Detection project — rare wreck / mixed-sonar resources

NOAA's Software Tools to Enable Automated Detection of Submerged Archaeological Sites project includes real sonar imagery, shipwreck examples, SSS-derived bathymetry and multibeam data. It includes downloadable examples such as William P. Rend and SS Monrovia.

Source:
https://oceanexplorer.noaa.gov/expedition/25automated-arch/

**Use:** advanced `wreck` research, segmentation reference, geospatial workflow, multimodal robustness.

**Important:** multibeam is not the same modality as SSS. Keep it separate unless you explicitly model cross-modality/domain shift.

## 6. NOAA 22shipwreck-detection expedition — rare real SSS survey imagery

The expedition page documents 8.04 km² of IVER-3 SSS surveys and expert labels distinguishing background, ships, debris and moorings around wreck sites.

Source:
https://oceanexplorer.noaa.gov/expedition/22shipwreck-detection/

Useful downloadable examples:
https://oceanexplorer.noaa.gov/multimedia/grecian-site/
https://oceanexplorer.noaa.gov/multimedia/explorations-22shipwreck-detection-gallery-media-monrovia-side-scan-sonar-iver/
https://oceanexplorer.noaa.gov/multimedia/georeferenced-side-scan-sonar-image/

**Use:** rare `wreck` examples, manual annotation, georeferencing validation, external qualitative testing.

## 7. Chiniak Bay, Alaska — rare independent ghost-pot survey

A Fishery Bulletin study reports Side-Scan Sonar locating **189 putative lost crab pots** in 4.5 km² of Chiniak Bay near Kodiak, Alaska; 15 were subsequently verified by submersible/ROV as crab pots.

Source/paper:
https://www.researchgate.net/publication/242471543_Ghost_fishing_by_Tanner_crab_Chionoecetes_bairdi_pots_off_Kodiak_Alaska_Pot_density_and_catch_per_trap_as_determined_from_sidescan_sonar_and_pot_recovery_data

**Use:** independent-domain `ghost_pot` evidence and potential data-acquisition lead.

**Important:** the public paper is evidence of the survey, not a ready-download YOLO dataset. Contact the data owner if you need the original sonar imagery.

## 8. Mullica River / Great Bay, New Jersey — rare ghost-fishing-gear survey

A four-year study used Klein 3900 and EdgeTech 6205 SSS and reports **2,218 probable derelict-fishing-gear targets** across 20.78 km².

Source:
https://www.sciencedirect.com/science/article/abs/pii/S0025326X18307707

Program/source:
https://stockton.edu/marine/marine-debris.html

**Use:** independent `ghost_pot` / derelict-gear domain; external validation; possible request-for-data path.

**Important:** not currently a standard downloadable labeled ML dataset on those pages.

## 9. Salish Sea / Washington — rare ghost-pot survey

The Jefferson County Marine Resources Committee documents SSS surveys in Discovery Bay, Cape George and Port Townsend Bay, including more than 100 crab pots detected at Cape George.

StoryMap/source:
https://storymaps.arcgis.com/stories/1befb7cae32f49e89d8595d8ae884d38

Project:
https://www.jeffersonmrc.org/projects/crabber-outreach-derelict-gear-removal/

**Use:** independent geography for ghost-pot domain generalization and potential imagery/data requests.

**Important:** public pages document survey findings rather than providing a standard annotation package.

## 10. Pacific Northwest / Global Ghost Gear Initiative — independent ghost-pot source

The Global Ghost Gear Initiative documents about **19 linear km of Side-Scan Sonar surveys** in the Pacific Northwest, identifying 73 derelict crab pots and investigating/removing many of them.

Source:
https://global-ghost-gear.squarespace.com/projects/signature-pnw

**Use:** independent ghost-gear domain, validation/reference, data-acquisition lead.

## 11. Stockton Marine Field Station — long-term lost-gear sonar program

Stockton University documents long-term marine-debris work using SSS to identify and map lost fishing gear and includes a side-scan image of lost crab pots plus a request-data path.

Source:
https://stockton.edu/marine/marine-debris.html

**Use:** rare ghost-pot examples and possible requestable survey data.

## 12. Ghost-pot field-survey context — Chesapeake / NOAA

NOAA describes earlier Marine Debris Program pilot surveys showing SSS could identify derelict crab pots in Chesapeake Bay while also collecting bathymetric information.

Source:
https://oceanservice.noaa.gov/news/july26/bathymetric-data.html

**Use:** historical independent ghost-pot domain context and lead-finding, not a ready ML dataset.

## 13. Sonar Diffusion Dataset — rare wreck/plane crop-level source

Hugging Face currently shows **762** sonar examples with text classes including `shipwreck`, `airplane`, `other` and `fish`.

Source:
https://huggingface.co/datasets/PaweekornSora/sonar-diffusion-dataset

**Use:** crop-level representation learning, research augmentation and additional plane/wreck examples.

**Important:** small research dataset; inspect provenance and license before making it part of a benchmark.

## 14. DRISHTI SSS — useful assembled SIH-specific reference

A public 2026 SIH-oriented SSS dataset is available in YOLO format. Its dataset card documents upstream attribution and caveats; it includes `wreckR` from a Ship+Plane SSS source and explicitly documents a synthetic class and upstream provenance.

Source:
https://huggingface.co/datasets/rehan9599/drishti-sss

Alternate current mirror:
https://huggingface.co/datasets/atharvhugg17/drishti-sss

**Use:** studying an SIH-style assembled pipeline, YOLO-format reference, comparison with your own dataset assembly.

**Important:** do not treat it as an independent dataset simply because it is packaged separately. It reuses upstream sources; avoid duplicate training/test leakage.

## 15. Rare-source rule: downloadable vs image-only vs request-only

Classify every source as:

```text
READY-DATASET
→ download and inspect

IMAGE-ONLY
→ download → verify rights → manually annotate

REQUEST-DATA
→ contact owner → get permission → receive source data

RESEARCH-REFERENCE
→ use for methodology/validation only
```

Never mix these categories in your metrics.

## 16. Best new sources if common datasets are already implemented

### Highest priority

```text
1. SonarVision Multi-Source v6
   → wreck + plane + unknown_debris

2. NOAA B-29
   → rare plane image

3. UB88 Side-Scan archive
   → rare plane + wreck images

4. TBM Avenger
   → rare plane image
```

### Best independent ghost-pot expansion

```text
5. Chiniak Bay, Alaska
6. Mullica River / Great Bay, NJ
7. Salish Sea / Washington
8. Stockton Marine Field Station
9. Pacific Northwest GGGI
```

## 17. How to add rare images to your AI dataset

For image-only sources:

```text
Download
↓
Record source/credit/license
↓
Hash file
↓
Inspect sonar modality
↓
Manual annotation
↓
Annotation QA
↓
Store original + normalized label
↓
Assign survey/source group
↓
Split safely
```

Do not create train/test leakage from multiple crops of the same image.

## 18. Wreck-specific expansion

Target:

```text
AI4Shipwrecks (existing)
+
SeabedObjects (existing)
+
SonarVision v6
+
NOAA Grecian/Monrovia/Barge examples
+
UB88 wreck collection
```

Use NOAA/UB88 image-only material mainly to increase **appearance diversity** after verifying rights and annotation quality.

## 19. Plane-specific expansion

Target:

```text
SeabedObjects plane (existing)
+
Roboflow Ship/Plane (existing)
+
SonarVision v6
+
NOAA B-29
+
TBM Avenger
+
UB88 aircraft collection
```

This gives you multiple aircraft appearances instead of learning one narrow visual pattern.

## 20. Ghost-pot-specific expansion

Target:

```text
GhostVision (existing)
+
Chiniak Bay
+
Mullica River / Great Bay
+
Salish Sea
+
Stockton
+
PNW GGGI
```

Where raw images are unavailable, use the projects as **data-request leads** rather than pretending the survey counts are image counts.

## 21. Why rare sources are valuable

Do not add rare data merely to increase the number of images.

The real value is:

```text
Different geography
+
Different sonar hardware
+
Different seabed
+
Different object appearance
+
Different acquisition conditions
=
Better domain robustness
```

## 22. Duplicate / provenance check

Before merging:

```text
SHA256
original filename
source URL
survey/site
image dimensions
near-duplicate crop check
```

This is especially important for assembled datasets such as SonarVision/DRISHTI, which can reuse upstream sources.

## 23. Final recommendation

If the normal datasets in your existing project are already implemented, do NOT repeat them.

Use this expansion path:

```text
CURRENT COMMON DATA
        ↓
SonarVision v6
        ↓
rare NOAA plane/wreck images
        ↓
UB88 aircraft/wreck collection
        ↓
independent ghost-pot surveys
        ↓
hard-negative mining
        ↓
final leakage-safe evaluation
```

The goal is a model that recognizes:

```text
WRECK
GHOST_POT
PLANE
```

across different real sonar conditions, while rejecting natural seafloor and acoustic clutter.

## 24. Source list

- SonarVision v6: https://huggingface.co/datasets/Dinoman1221/sonarvision-multisource-v6
- SonarVision code: https://github.com/Dinoman67/sonarvision
- NOAA B-29 SSS: https://oceanexplorer.noaa.gov/multimedia/explorations-22saipan-surveys-gallery-media-b-29-2/
- UB88 SSS archive: https://www.ub88.org/sidescansonar/side-scan-sonar.html
- TBM Avenger: https://pacificwrecks.com/aircraft/tbm/45810/2014/sss-fan-avenger.html
- NOAA archaeological detection: https://oceanexplorer.noaa.gov/expedition/25automated-arch/
- NOAA shipwreck expedition: https://oceanexplorer.noaa.gov/expedition/22shipwreck-detection/
- Chiniak Bay study: https://www.researchgate.net/publication/242471543_Ghost_fishing_by_Tanner_crab_Chionoecetes_bairdi_pots_off_Kodiak_Alaska_Pot_density_and_catch_per_trap_as_determined_from_sidescan_sonar_and_pot_recovery_data
- Mullica River study: https://www.sciencedirect.com/science/article/abs/pii/S0025326X18307707
- Stockton Marine Field Station: https://stockton.edu/marine/marine-debris.html
- Salish Sea StoryMap: https://storymaps.arcgis.com/stories/1befb7cae32f49e89d8595d8ae884d38
- Jefferson County MRC: https://www.jeffersonmrc.org/projects/crabber-outreach-derelict-gear-removal/
- Global Ghost Gear Initiative PNW: https://global-ghost-gear.squarespace.com/projects/signature-pnw
- NOAA Chesapeake crab-pot program: https://oceanservice.noaa.gov/news/july26/bathymetric-data.html
- Sonar Diffusion: https://huggingface.co/datasets/PaweekornSora/sonar-diffusion-dataset
- DRISHTI: https://huggingface.co/datasets/rehan9599/drishti-sss

## 25. Important truthfulness rule

A source may be:

```text
real SSS dataset
real SSS image collection
survey report
requestable raw survey data
```

These are different things.

Never turn a survey count such as "189 crab pots detected" into "189 labeled training images" unless the actual images/labels exist.

Never call a crab pot a ghost net.
Never call a plane a generic wreck unless the class definition explicitly permits it.
Never report image-only examples as a benchmark dataset.

**Use rare data to improve diversity and real-world robustness, not to manufacture statistics.**
