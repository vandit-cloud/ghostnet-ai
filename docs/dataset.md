# GhostNet-AI (SIH26057): NEW Side-Scan Sonar Data Sources Beyond the Known Set

## TL;DR
- The richest NEW ready-to-train finds are the **DeeperSense Seafloor Sediments** set (434,164 SSS patches — the single best hard-negative/clutter corpus available), **Marine-PULSE**, **SWDD**, the **MILCO/NOMBO mine dataset**, and the **Roboflow "kamal/sonar-zjeoz" Plane set** — all free and directly downloadable.
- For the rarest class (PLANE), genuinely distinct real submerged-aircraft SSS imagery is extremely scarce: essentially all public "aircraft" images trace back to ~60–70 originals, and the largest purpose-built aircraft dataset — Character et al. 2025, "the largest aircraft wreck-focused dataset that has been published to date, with 19 unique aircraft wrecks, composed of 290 individual fragments and located across six countries" — is NOT publicly released and must be requested from the authors.
- For GHOST_POT, the best NEW leads are request-only survey programs in fresh geographies (National TRAP Program: Florida Keys spiny lobster/stone crab, Beverly MA, Midcoast Maine; GGGI Gulf of Maine signature project) — but note most produce survey counts, not labeled images. The economic stakes are large: Scheld, Bilkovic & Havens (2016) found removing even 10% of derelict pots/traps from major crustacean fisheries "could increase landings by 293,929 metric tons, at a value of $831 million annually."

## Key Findings
1. Ready, downloadable SSS datasets exist that you have not implemented — mostly seabed-texture, structure, mine, and wall datasets ideal for hard-negative training, plus a couple of plane/ship detection sets on Roboflow.
2. The PLANE class is a genuine data desert. Real, distinct submerged-aircraft SSS images number only in the low tens; synthetic augmentation and request-based access are essential.
3. National hydrographic archives (NOAA NCEI, USGS, INFOMAR/Ireland, Wessex Archaeology/UK) are large IMAGE-ONLY reservoirs requiring manual annotation but offering geographic and hardware diversity you cannot get from the ML datasets.
4. Mature synthetic SSS generators (HoloOcean, S3Simulator, Stonefish, diffusion/GAN pipelines) can specifically backfill WRECK and PLANE rare-class shortfalls.

## Details

### RANKED — Best NEW ready-to-use sources (top = highest value)

**1. DeeperSense Large-Scale Seafloor Sediments SSS Dataset**
- One-line: Very large corpus of side-scan waterfall patches (384×384) of natural seafloor collected off Catalunya (Spain).
- URL: https://zenodo.org/records/10209445
- Category: READY-DATASET
- Helps class: hard-negative (also self-supervised pretraining)
- Size: 434,164 images (real image count). Per the Zenodo record (DeeperSense, EU H2020 Project 101016958; data collected by Tecnoambiente SL): "This resulted in a total of 434,164 images... including rocky bottoms, sand ripples, detrital funds, posidonia, cymocea, mud, corals, artificial reefs etc." It extends the Ocean Engineering paper DOI 10.1016/j.oceaneng.2023.115647.
- Format: raw image patches (PNG) for self-supervised pretraining; tools at github.com/DeeperSense/deepersense-seafloorscan
- License/access: Zenodo open (verify CC terms on record)
- Why valuable: By far the largest SSS corpus found; captures rocky bottoms, sand ripples, detrital funds, posidonia, cymodocea, mud, corals, and artificial reefs — an outstanding false-positive-suppression and pretraining backbone.

**2. Marine-PULSE Dataset**
- One-line: Annotated SSS of man-made marine engineering structures (pipelines/cables, mounds, seabed surface, platforms).
- URL: https://zenodo.org/records/7922705
- Category: READY-DATASET
- Helps class: hard-negative (structure clutter)
- Size: 719 images total (323 pipeline/cable, 134 underwater residual mound, 88 seabed surface, 82 engineering platform)
- Format: image classification set (train/test split provided); multiple sonars (EdgeTech 4200FS/MP, Benthos SIS-1624, Klein 2000/3000)
- License/access: Zenodo open
- Why valuable: Elongated linear structures and platforms are classic false positives for wreck/plane detectors; hardware diversity aids generalization.

**3. SWDD — Sonar Wall Detection Dataset (+ SWDD-Validation, SWDD-Adversarial)**
- One-line: SSS of harbor walls from an LAUV with Klein 3500 in Porto de Leixões (Portugal).
- URL: https://zenodo.org/records/13692547 and https://zenodo.org/records/10528135
- Category: READY-DATASET
- Helps class: hard-negative (linear structures), robustness testing
- Size: 216 base images plus augmented/adversarial extensions (SWDD-Clean, SWDD-Surface, SWDD-Noisy)
- Format: object-detection annotations (YOLO-style); waterfall images
- License/access: Zenodo open
- Why valuable: The adversarial/noisy variants specifically stress false-positive robustness — directly relevant to clutter-rejection benchmarking.

**4. SSS Mine Detection (MILCO / NOMBO) Dataset**
- One-line: Real SSS images of mine-like contacts (MILCO) and non-mine bottom objects (NOMBO) from a Teledyne Gavia AUV.
- URL: https://figshare.com/articles/dataset/_i_Side-scan_sonar_imaging_for_Mine_detection_i_/24574879 (Data in Brief DOI 10.1016/j.dib.2024.110132)
- Category: READY-DATASET
- Helps class: hard-negative (NOMBO clutter) and small compact-target detection
- Size: Per Pessanha Santos et al., Data in Brief, "1170 real sonar images taken between 2010 and 2021 using a Teledyne Marine Gavia AUV," collected with a "900–1800 kHz Marine Sonic dual frequency side-scan sonar"; a baseline YOLOv4 gave mAP 75%, Precision 82%, Recall 64%.
- Format: .jpg images + .txt annotations (detection/classification/segmentation ready)
- License/access: figshare open
- Why valuable: NOMBO = non-mine bottom objects are exactly the compact clutter that triggers false positives; MILCO shapes resemble small ghost-pot returns, aiding small-object tuning.

**5. Roboflow Universe — "sonar" (kamal/sonar-zjeoz)**
- One-line: SSS object-detection set with a dedicated Plane class (plus shadow).
- URL: https://universe.roboflow.com/kamal-po9gr/sonar-zjeoz
- Category: READY-DATASET
- Helps class: plane
- Size: 123 images
- Format: bounding boxes exportable to YOLO/COCO/VOC
- License/access: CC BY 4.0, free (Roboflow account)
- Why valuable: One of very few plane-labeled bbox sets; drop-in for detection. Caution: images appear KLSG-derived (leakage risk — see provenance section).

**6. AquaScan-1K**
- One-line: High-res SSS images for underwater human detection across varied lakebeds and frequencies (455–1075 kHz).
- URL: https://zenodo.org/records/18771165
- Category: READY-DATASET
- Helps class: hard-negative (small low-contrast targets; lakebed clutter)
- Size: 1,033 images
- Format: images + YOLO-style labels (images/, labels/, classes.txt), single "human" class
- License/access: Zenodo open
- Why valuable: Multi-frequency, multi-depth lakebed diversity; small low-contrast targets train the detector to distinguish genuine compact objects from noise — a strong hard-negative and small-object companion.

**7. SeabedObjects-KLSG-II (extended)**
- One-line: Extended KLSG with more ship/airplane/seafloor SSS images.
- URL: https://github.com/HHUCzCz/-SeabedObjects-KLSG--II
- Category: READY-DATASET
- Helps class: plane, wreck, hard-negative (seafloor)
- Size: 66 airplane, 487 ship, 578 seafloor images
- Format: image classification (PNG)
- License/access: free on GitHub (academic use)
- Why valuable: Slightly larger aircraft/ship counts than base KLSG. Caution: this is an extension of the SeabedObjects family you already use — treat as overlap/dedup risk, not fully independent data.

**8. Consumer-Class Side-Scanning Sonar Dataset for Human Detection**
- One-line: Baltic Sea SSS collected with a consumer Garmin unit; includes "other objects" (tires, rocks).
- URL: https://ieeexplore.ieee.org/document/10159954/
- Category: REQUEST-DATA / RESEARCH-REFERENCE (paper; data by author contact)
- Helps class: hard-negative (tires, rocks)
- Size: 331 human images + 364 images with other objects (tires, rocks)
- Format: cropped + full-resolution images, defined train/val/test split
- License/access: paper on IEEE Xplore; dataset availability via authors
- Why valuable: Rare consumer-grade sonar domain (matches low-cost survey gear used in ghost-pot work); tires/rocks are direct hard negatives.

**9. NNSSS — Online Multi-class SSS Segmentation Dataset (Burguera & Bonin-Font)**
- One-line: AUV-collected SSS with multi-class seabed segmentation labels.
- URL: https://github.com/aburguera/NNSSS/tree/master/DATASET
- Category: READY-DATASET
- Helps class: hard-negative (seabed types)
- Size: small (~10 labeled scenes per benchmark tables)
- Format: segmentation masks
- License/access: GitHub open
- Why valuable: Pixel-level seabed segmentation supports semantic hard-negative masking and terrain-aware training.

**10. IEEE DataPort — "Side-scan sonar image" (Can Lei, DOI 10.21227/m4je-bd83)**
- One-line: 695 SSS images spanning aircraft, ships, mines, human bodies.
- URL: https://ieee-dataport.org/documents/side-scan-sonar-image
- Category: REQUEST-DATA (subscription-gated)
- Helps class: plane (123), wreck (272), hard-negative (mines 172, bodies 128)
- Size: 695 images (123 aircraft, 272 sunken ships, 172 mines, 128 human bodies)
- Format: images
- License/access: requires IEEE DataPort subscription/IEEE Society membership — GATED
- Why valuable: Explicit aircraft class, but the plane/ship images are re-sourced from Huo Guanying's public GitHub, so it largely duplicates free data behind a paywall — low priority.

### GHOST_POT — new sources (mostly survey programs, not labeled images)

**A. National TRAP Program (VIMS/CCRM-administered, NOAA-funded) — NEW geographies**
- One-line: Multi-state derelict trap removal using side-scan sonar in fresh regions.
- URL: https://www.trapprogram.org/2026-partners/ and https://news.wm.edu/2025/10/29/national-trap-program-targets-ghostly-issue-with-second-round-of-coastal-clean-up-funding/
- Category: REQUEST-DATA
- Helps class: ghost_pot
- Size: SURVEY PROGRAM (not image counts). Per W&M/VIMS: the National Marine Sanctuary Foundation was "awarded $146,553 to remove derelict spiny lobster and stone crab traps from... the Florida Keys National Marine Sanctuary"; the City of Beverly MA "received $124,700"; and the program is backed by an $8 million, four-year (2023) NOAA Marine Debris Program grant distributing roughly $1.5 million annually. Also funds Midcoast Maine gear balls and Port Angeles/Sequim WA Dungeness crab removal (Northwest Straits Foundation, clearing ~3,980 acres).
- Format: side-scan survey data held by partners (raw, must be requested)
- License/access: contact program/partners
- Why valuable: Opens Florida, Massachusetts, and new Maine/WA geographies and trap types (spiny lobster, stone crab, Dungeness) beyond your existing PNW/NJ/Chesapeake set.

**B. GGGI Signature Project — Gulf of Maine & Rhode Island (NEW; distinct from the excluded PNW signature project)**
- One-line: Side-scan surveys for lost lobster traps in the Gulf of Maine.
- URL: https://www.ghostgear.org/projects/signature-gulfofmaine
- Category: REQUEST-DATA
- Helps class: ghost_pot
- Size: SURVEY COUNT (NOT labeled images) — ~1,300 ALDFG targets identified over 8 survey days (Apr–May 2023). Per the GGGI page: "Casco Bay was confirmed as a priority site... through our side-scan sonar efforts conducted in summer 2023, which showed more than 1,200 possible targets," and a subsequent retrieval "collected a mass of rope, net, and lobster traps weighing roughly 4,500 kg."
- Format: side-scan survey data (request via GGGI/Gulf of Maine Lobster Foundation)
- License/access: contact GGGI/GOMLF
- Why valuable: Lobster-trap morphology in a cold Atlantic setting; different gear shape than crab pots.

**C. Delaware Inland Bays GhostVision crab-pot dataset (context/adjacent — confirm you already hold this)**
- One-line: Manually annotated SSS of derelict crab pots in Delaware's Inland Bays and Delaware Bay.
- URL: https://huggingface.co/datasets/PINGEcosystem/sss-crab-pot-detection-ds
- Category: READY-DATASET
- Helps class: ghost_pot
- Size: labeled SSS images (JSONL bbox format)
- Format: JSONL (HF Datasets-native), bounding boxes
- License/access: Hugging Face (check card)
- Why valuable: NOTE — this is the dataset backing GhostVision, which is in your KNOWN base; included only so you can confirm you already have the DE geography and avoid double-counting.

*Economic context for ghost-pot prioritization:* Scheld, Bilkovic & Havens (2016), "The Dilemma of Derelict Gear" (Scientific Reports, nature.com/articles/srep19671), found that removing even 10% of derelict pots/traps from major crustacean fisheries "could increase landings by 293,929 metric tons, at a value of $831 million annually"; the same study reported that removing 34,408 Chesapeake pots added 13,504 MT of harvest worth US $21.3 million (a 27% increase). This is a strong motivation to prioritize GHOST_POT data acquisition despite the survey-vs-image gap.

### PLANE — new sources (rarest class)

**D. Character et al. 2025 / Project Recover MIA Aircraft Dataset**
- One-line: Largest purpose-built submerged-aircraft SSS training set (WWII Missing-In-Action aircraft, six countries).
- URL: https://journal.caa-international.org/articles/10.5334/jcaa.179 (paper, CC-BY; PDF: https://journal.caa-international.org/articles/179/files/681b372b2fb05.pdf)
- Category: RESEARCH-REFERENCE / REQUEST-DATA
- Helps class: plane
- Size: Per the paper, "Our training dataset is the largest aircraft wreck-focused dataset that has been published to date, with 19 unique aircraft wrecks, composed of 290 individual fragments and located across six countries" (Chuuk/Micronesia, Croatia, Maloelap/Marshall Islands, Denmark, Alaska, Palau). Collected mostly with a REMUS-100 AUV and Atlas 600/1200 kHz chirp SSS; tiles are 640×640 with YOLOv7/KITTI labels; the YOLOv7 model reached F1 = 0.74 and correctly identified 3 of 4 previously unknown aircraft. (These are wreck/fragment counts, not a released image download.)
- Format: YOLOv7-format tiles (per paper)
- License/access: Data NOT publicly posted (no DOI/repo found; likely withheld for war-grave/location protection). Request from authors — Leila Character (Sam Houston State Univ. / Univ. of Delaware, leilacharacter@shsu.edu) or Mark Moline (Univ. of Delaware). Co-authored with Project Recover (UD College of Earth, Ocean & Environment + Scripps Institution of Oceanography + BentProp).
- Why valuable: The only large, purpose-built aircraft SSS corpus with real geographic/hardware diversity; a successful request would transform your PLANE class.

**E. Project Recover / Scripps mission galleries**
- One-line: News/mission pages with embedded sonar screenshots of located WWII aircraft.
- URLs: https://www.projectrecover.org/project-recover-locates-3-wwii-aircraft-in-chuuk/ ; https://scripps.ucsd.edu/news/another-historic-find
- Category: IMAGE-ONLY
- Helps class: plane
- Size: a handful of illustrative screenshots (not a dataset)
- Format: JPG on web
- License/access: copyrighted, all-rights-reserved — reference only
- Why valuable: Visual reference for TBM Avenger, SBD Dauntless, and F6F Hellcat sonar signatures; not for direct training use.

**F. Wessex Archaeology aircraft SSS imagery (UK)**
- One-line: Side-scan sonar images of WWII aircraft on the UK seabed (Do-17 "Flying Pencil", Short Sunderland Mk 1 T9044, B-24 Liberator, B-17).
- URLs: https://www.flickr.com/photos/wessexarchaeology/4438313886 ; https://coflein.gov.uk/en/archive/6378950 ; https://www.wessexarch.co.uk/our-work/alsf-wrecks-seabed
- Category: IMAGE-ONLY
- Helps class: plane, wreck
- Size: individual annotated images across their Flickr/Coflein archives
- Format: web images (Crown Copyright on the underlying survey data)
- License/access: Crown Copyright / Wessex Archaeology rights — check terms before use
- Why valuable: Rare distinct aircraft types (Dornier, Sunderland flying boat, US heavy bombers) in European Channel/North Sea settings — genuine morphological diversity for PLANE.

**G. TIGHAR / Nikumaroro Earhart sonar imagery**
- One-line: High-frequency side-scan sonar anomaly imagery from AUV surveys off Nikumaroro.
- URL: http://tighar.org/Projects/Earhart/Archives/Research/Bulletins/66_NikuVIIUpdate/66_NikuVIIUpdate.html
- Category: IMAGE-ONLY / RESEARCH-REFERENCE
- Helps class: plane (edge case — debris/anomaly)
- Size: few images (single anomaly, ~22–32 ft object at ~600 ft depth)
- Format: web imagery, processed by Oceanic Imaging Consultants
- License/access: TIGHAR rights — reference only
- Why valuable: Illustrates deep reef-slope aircraft-debris signatures and the "anomaly vs. natural background" problem central to false-positive suppression.

### WRECK — new sources

**H. NOAA NCEI hydrographic + trackline SSS archives**
- One-line: National archive of geo-referenced side-scan sonar mosaics and legacy analog SSS from NOAA hydrographic and geophysical surveys.
- URLs: https://www.ncei.noaa.gov/products/nos-hydrographic-survey ; https://www.ncei.noaa.gov/products/marine-trackline-geophysical-data
- Category: IMAGE-ONLY / REQUEST-DATA
- Helps class: wreck, hard-negative
- Size: 11,000+ smooth sheets, 8,000+ descriptive reports; SSS mosaics for recent high-res surveys (survey counts, not labeled images)
- Format: GeoTIFF/MrSID mosaics, XTF, SegY; interactive map viewer
- License/access: free, public domain (US Gov)
- Why valuable: Enormous, free, public-domain reservoir of real US-coast SSS with wrecks, obstructions, and natural seafloor — needs manual annotation but offers unmatched scale and hardware/geography diversity.

**I. NOAA Office of Coast Survey Wrecks & Obstructions Database (AWOIS successor)**
- One-line: ~20,000 wreck/obstruction records with locations.
- URL: https://nauticalcharts.noaa.gov/updates/access-to-wrecks-and-obstructions/
- Category: RESEARCH-REFERENCE (locations/metadata, KML/KMZ) — not imagery
- Helps class: wreck (targeting/ground-truth)
- Size: Per NOAA Office of Coast Survey: "Correcting for some overlap... Coast Survey's new wrecks and obstructions database now contains information on about 13,000 wreck features and 6,000 obstructions" (nearly 20,000 combined records).
- Format: KML/KMZ, tabular
- License/access: free, public domain
- Why valuable: Cross-reference to locate corresponding SSS in NCEI archives; ground-truth positions for scraping wreck imagery.

**J. USGS Coastal/Marine Geology side-scan sonar data series**
- One-line: Archived SSS + multibeam data with GeoTIFF mosaics from USGS cruises (e.g., Gulf Islands National Seashore, Klein 3900 dual-frequency).
- URL: https://pubs.usgs.gov/ds/671/html/equipment_processing.html (representative; broader catalog under USGS coastal/marine geology)
- Category: IMAGE-ONLY
- Helps class: wreck, hard-negative
- Size: per-cruise mosaics (survey products, not labeled images)
- Format: GeoTIFF, XTF/CARIS
- License/access: free, public domain
- Why valuable: High-quality US coastal SSS mosaics with ground-truth grab samples for seabed-type labeling.

**K. INFOMAR (Ireland) shipwreck inventory + seabed viewer**
- One-line: Ireland's national seabed programme; 480+ surveyed shipwrecks, side-scan among data holdings, freely served via web viewers.
- URLs: https://data.gov.ie/dataset/infomar-shipwrecks ; https://www.infomar.ie/
- Category: IMAGE-ONLY / RESEARCH-REFERENCE
- Helps class: wreck
- Size: 480+ shipwreck records; >120 TB geophysical database incl. sidescan
- Format: WMS layers, ZIP, HTML; MBES-derived wreck imagery
- License/access: freely available (check INFOMAR/GSI licence)
- Why valuable: North-east Atlantic geography and hardware diversity; distinct from your US/Great Lakes-heavy base.

**L. EMODnet (pan-European) geology/bathymetry portals**
- One-line: Harmonized European seabed data (survey methods incl. side-scan sonar) across all EU seas.
- URL: https://emodnet.ec.europa.eu/
- Category: RESEARCH-REFERENCE / IMAGE-ONLY
- Helps class: wreck, hard-negative
- Size: continental-scale (metadata + some imagery)
- Format: portal layers, WMS
- License/access: open EU data
- Why valuable: Broadest European coverage for locating regional SSS holdings and seabed-substrate ground truth.

### SYNTHETIC / augmentation options (flag all outputs as synthetic)

**M. S3Simulator**
- One-line: Benchmark simulated SSS dataset + pipeline generating synthetic ship and plane images (SAM + CAD + Gazebo/SelfCAD).
- URL: https://github.com/bashakamal/S3Simulator (paper arXiv:2408.12833)
- Category: SYNTHETIC
- Helps class: plane, wreck
- Size: synthetic set incl. aircraft silhouettes
- Format: images
- License/access: free (GitHub)
- Why valuable: Purpose-built to fill ship/plane scarcity; directly targets your two rarest classes.

**N. HoloOcean (BYU FRoST Lab)**
- One-line: Open-source UE4 underwater simulator with a realistic side-scan sonar sensor (octree ray-tracing, multipath, noise models).
- URL: https://frostlab.byu.edu/holoocean-underwater-simulator
- Category: SYNTHETIC
- Helps class: wreck, plane, hard-negative
- Size: generator (unlimited)
- Format: Python API; pip install
- License/access: open source
- Why valuable: Place 3D wreck/aircraft meshes on varied seabeds and render labeled SSS at scale; strongest turnkey simulator.

**O. Stonefish simulator**
- One-line: Physically grounded marine robotics simulator with side-scan (plus multibeam/FLS) sonar and detailed hydrodynamics.
- URL: https://github.com/patrykcieslak/stonefish
- Category: SYNTHETIC
- Helps class: wreck, plane, hard-negative
- Size: generator
- Format: C++/ROS
- License/access: open source
- Why valuable: Physics-grounded returns and vehicle-motion coupling for realistic waterfall geometry.

**P. STARS physics-based Blender SSS renderer (BLAINDER extension)**
- One-line: Physics-based side-scan rendering of TurboSquid ship meshes with randomized reflectance/orientation for sim-to-real shipwreck segmentation.
- URL: https://arxiv.org/pdf/2310.01667 (STARS)
- Category: SYNTHETIC
- Helps class: wreck (extendable to plane)
- Size: generator
- Format: Blender pipeline
- License/access: research code
- Why valuable: Zero-shot sim-to-real shown for shipwrecks; adaptable to aircraft meshes.

**Q. Diffusion / GAN SSS generators**
- One-line: Category-controllable diffusion SSS generator (MDPI) and GAN/pix2pix optical-to-sonar tools.
- URLs: https://www.mdpi.com/2077-1312/12/8/1457 (diffusion generator); https://github.com/json9512/sonarToimage (GAN); DS-SIAUG DDPM augmentation (PMC11315046)
- Category: SYNTHETIC
- Helps class: plane, wreck, ghost_pot (rare-class balancing)
- Size: generators
- Format: PyTorch
- License/access: research code
- Why valuable: Diffusion controllable-category generation can synthesize under-represented classes; strong for rebalancing GHOST_POT/PLANE.

### HARD-NEGATIVE / clutter sources (consolidated)
- **DeeperSense Seafloor Sediments** (434,164 patches; rock, ripple, mud, seagrass, reef) — https://zenodo.org/records/10209445 — READY-DATASET, the primary recommendation.
- **SASSED** (129 SAS snippets: hardpack sand, mud, sea grass, rock, sand ripple) — https://data.mendeley.com/datasets/s5j5gzr2vc/4 — READY-DATASET (note: SAS not SSS; texture transfer only).
- **Marine-PULSE** (structures) and **SWDD** (walls) — as above.
- **MILCO/NOMBO** (non-mine bottom objects) — as above.
- **Consumer SSS human dataset** (tires, rocks) — as above.
- **NNSSS** (seabed segmentation) — as above.

### Meta-references to mine further
- "Sonar Image Datasets: A Comprehensive Survey" — https://arxiv.org/html/2510.03353v1 (master table + timeline).
- Awesome-Sonar-Image-Resources — https://github.com/Jorwnpay/Awesome-Sonar-Image-Resources
- OpenSonarDatasets — https://github.com/remaro-network/OpenSonarDatasets

## Recommendations
1. **Immediately ingest (free, high ROI):** DeeperSense Seafloor Sediments (hard-negative backbone/pretraining), Marine-PULSE, SWDD (+adversarial), MILCO/NOMBO, AquaScan-1K, and Roboflow kamal/sonar-zjeoz (plane bboxes). These require no gatekeeping and cover your weakest areas (clutter + plane).
2. **Send data requests now (long lead time):** Email Leila Character / Mark Moline for the Project Recover MIA aircraft dataset; contact GGGI/Gulf of Maine Lobster Foundation and the National TRAP Program partners (Florida Keys, Beverly MA, Midcoast Maine) for ghost-pot side-scan survey data. Benchmark to change plan: if the Character dataset is granted, deprioritize synthetic plane generation.
3. **Stand up a synthetic pipeline** (HoloOcean first, S3Simulator second) to generate labeled PLANE and WRECK imagery; target parity with real-image counts per class. Threshold: if real PLANE images remain < ~200 after requests, rely on synthetic for ≥50% of plane training data and hold out ALL real planes for validation.
4. **Harvest IMAGE-ONLY archives** (NOAA NCEI, USGS, INFOMAR, Wessex/Coflein) via the Wrecks & Obstructions database to target annotation effort; prioritize Wessex aircraft images for PLANE diversity.
5. **Guard against leakage** (below) before merging any KLSG-derived set.

## Caveats
- **Survey counts ≠ labeled images.** GGGI Gulf of Maine (~1,300 targets), Chesapeake/TRAP programs, and NCEI/USGS holdings are survey statistics or raw mosaics, not ready training labels. Do not report them as image counts.
- **Provenance/leakage risk (critical):** Roboflow kamal/sonar-zjeoz, KLSG-II, and the IEEE DataPort Can Lei set all appear to recycle Huo Guanying's SeabedObjects-KLSG aircraft/ship images — which underlie your existing base. Deduplicate by perceptual hashing before train/test splitting to avoid train–test contamination; genuinely distinct real submerged-aircraft SSS images likely number only ~60–70.
- **Class fidelity:** Keep crab/lobster pots (GHOST_POT) distinct from nets and from generic debris; keep aircraft (PLANE) distinct from ship WRECK. MILCO/NOMBO and Marine-PULSE items are hard-negatives, not target classes.
- **Rights:** Wessex (Crown Copyright), Project Recover/Scripps (all rights reserved), and TIGHAR imagery are reference-only unless licensed. IEEE DataPort Can Lei is subscription-gated. Verify each Zenodo/HF/Roboflow licence before redistribution.
- **Modality mismatch:** SASSED is synthetic-aperture sonar (SAS), and FLS datasets (Marine Debris FLS, FSSG) are forward-looking — use for texture/transfer only, not as native SSS.