# Data attribution

GhostNet-AI redistributes a small number of third-party side-scan sonar frames,
as demo fixtures and as illustrations of our labelling convention. This file
records, for every one of them, where it came from and under what terms.

**Our own work — the code, the 425 ghost_net polygons, the 74 ghost_net boxes,
the 63 plane boxes, the labelling conventions and the build scripts — is
released under the licences named in `LICENSE` and `NOTICE`. Nothing in this
file changes that. Conversely, nothing in our licence grants you rights over
the third-party imagery listed below: each item keeps its original terms.**

We make no ownership claim over any third-party imagery in this repository and
will remove any of it promptly on request from a rights holder.

## Summary of terms we inherit

| source | licence | what it obliges us to do |
|---|---|---|
| China Offshore SSS-AI v2 | CC BY 4.0 | credit the source; redistribution permitted |
| SubPipe | CC BY 4.0 | credit the source; redistribution permitted |
| sonar_detect (Roboflow) | CC BY 4.0 | credit the source; redistribution permitted |
| GhostVision v1.0.0 | **CC BY-SA 4.0** | credit **and** share-alike: adaptations of these frames must themselves be CC BY-SA 4.0 |
| AI4Shipwrecks | no formal licence; open research dataset | cite; redistribution is by academic convention, not by an explicit grant |
| SCTD 1.0 | no formal licence; academic use stated | cite; same caveat as above |

The last two carry no explicit redistribution grant. We publish a handful of
640x640 excerpts from them as illustrative examples in a non-commercial
research repository, with full citation — a customary academic use, but not a
right we can point to in a licence file. Stated here rather than left implicit.

## Demo showcase frames

Generated from `demo/showcase/manifest.json`, which records the provenance of
every frame at build time.

### AI4Shipwrecks — 10 frame(s)

- Rights holder: University of Michigan Field Robotics Group
- Source: https://umfieldrobotics.github.io/ai4shipwrecks/
- Licence: **Open research dataset; no formal licence file. Academic use.**
- Registry id: `AI4SHIPWRECKS`


| file in this repository | original filename | split |
|---|---|---|
| `demo/showcase/frames/aircraft/90_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y0.png` | test |
| `demo/showcase/frames/aircraft/91_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y1440.png` | test |
| `demo/showcase/frames/debris/90_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y0.png` | test |
| `demo/showcase/frames/debris/91_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y1440.png` | test |
| `demo/showcase/frames/ghost_gear/90_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y0.png` | test |
| `demo/showcase/frames/ghost_gear/91_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y1440.png` | test |
| `demo/showcase/frames/wrecks/01_wreck.png` | `AI4SHIPWRECKS__Lucinda_van_Valkenburg_19__x960_y1440.png` | test |
| `demo/showcase/frames/wrecks/02_wreck.png` | `AI4SHIPWRECKS__Montana_05__x960_y960.png` | val |
| `demo/showcase/frames/wrecks/90_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y0.png` | test |
| `demo/showcase/frames/wrecks/91_natural_seabed.png` | `AI4SHIPWRECKS__Artificial_Reef_01__x0_y1440.png` | test |


### SCTD 1.0 — 6 frame(s)

- Rights holder: Ning et al.
- Source: https://github.com/MingqiangNing/SCTD
- Licence: **No formal licence file; academic use stated.**
- Registry id: `SCTD`


| file in this repository | original filename | split |
|---|---|---|
| `demo/showcase/frames/aircraft/01_plane.jpg` | `SCTD__000027.jpg` | test |
| `demo/showcase/frames/aircraft/02_plane.jpg` | `SCTD__000074.jpg` | val |
| `demo/showcase/frames/aircraft/03_plane.jpg` | `SCTD__000006.jpg` | val |
| `demo/showcase/frames/aircraft/04_plane.jpg` | `SCTD__000080.jpg` | val |
| `demo/showcase/frames/wrecks/03_wreck.jpg` | `SCTD__000185.jpg` | test |
| `demo/showcase/frames/wrecks/04_wreck.jpg` | `SCTD__000174.jpg` | val |


### SubPipe — 4 frame(s)

- Rights holder: OceanScan-MST / INESC TEC
- Source: https://zenodo.org/records/12666132
- Licence: **CC BY 4.0 - attribution required.**
- Registry id: `SUBPIPE`


| file in this repository | original filename | split |
|---|---|---|
| `demo/showcase/frames/debris/01_debris.png` | `SUBPIPE__SSS_HF_images_1693570212.989__x3375_y0.png` | test |
| `demo/showcase/frames/debris/02_debris.png` | `SUBPIPE__SSS_HF_images_1693570100.969__x3375_y0.png` | test |
| `demo/showcase/frames/debris/03_debris.png` | `SUBPIPE__SSS_HF_images_1693570099.969__x3375_y0.png` | test |
| `demo/showcase/frames/debris/04_debris.png` | `SUBPIPE__SSS_HF_images_1693570109.969__x3375_y0.png` | test |


### GhostVision v1.0.0 — 3 frame(s)

- Rights holder: PING Ecosystem
- Source: https://zenodo.org/records/20056679
- Licence: **CC BY-SA 4.0 - attribution AND share-alike.**
- Registry id: `GHOSTVISION`


| file in this repository | original filename | split |
|---|---|---|
| `demo/showcase/frames/ghost_gear/02_ghost_pot.jpg` | `GHOSTVISION__Contact_515_sslo_png_jpg.rf.9130a073c8946f00dc62cf1c9a63803d.jpg` | val |
| `demo/showcase/frames/ghost_gear/03_ghost_pot.jpg` | `GHOSTVISION__Rec14_wcp_ss_port_00011_png_jpg.rf.248bef1091991fdade425133597b2927.jpg` | test |
| `demo/showcase/frames/ghost_gear/04_ghost_pot.jpg` | `GHOSTVISION__Rec9_wcp_ss_star_00044_png_jpg.rf.cafaf08eb47b1611ab2dc2cd8115fcb6.jpg` | test |


### China Offshore SSS-AI v2 — 1 frame(s)

- Rights holder: Zenodo record 20048164
- Source: https://zenodo.org/records/20048164
- Licence: **CC BY 4.0 - attribution required.**
- Registry id: `CHINA-OFFSHORE`


| file in this repository | original filename | split |
|---|---|---|
| `demo/showcase/frames/ghost_gear/01_ghost_net.png` | `GHOSTNET-HAND__quanzhou_HN_057.png` | val |

## Labelling-convention illustrations

25 annotated crops under `ai/data/annotate/*/_guide/` teach the labelling
conventions; a convention cannot be taught without showing examples.

| directory | crops | underlying imagery | licence |
|---|---|---|---|
| `ai/data/annotate/ghost_net/_guide/` | 9 | China Offshore SSS-AI v2 net chips | CC BY 4.0 |
| `ai/data/annotate/ghost_net_seg/_guide/` | 13 | China Offshore SSS-AI v2 net chips | CC BY 4.0 |
| `ai/data/annotate/plane/_guide/` | 3 | SCTD 1.0 | no formal licence; academic use |

`ai/data/provenance/quality_audit/{aircraft,fish,other,shipwreck}.jpg` are
sample crops from **sonar_detect** (Roboflow Universe, CC BY 4.0,
https://universe.roboflow.com/object-detect-ury2h/sonar_detect), kept as
evidence for the quality audit recorded in `dataset_candidates.csv`.

`app/frontend/public/demo/d2_chip.jpg` is one China Offshore SSS-AI v2 net
chip, used as the before/after illustration of the D2 segmentation result.

## A caveat on the six "natural seabed" frames

The frames named `90_natural_seabed.png` and `91_natural_seabed.png` in each
showcase survey are tiles of **`AI4SHIPWRECKS__Artificial_Reef_01`**. Their
labels are empty, and the model returns no detection on them — but an empty
label in AI4Shipwrecks does **not** prove the tile is empty seabed. That survey
annotates one target wreck per site, so lines that do not pass over the target
carry a blank mask even where the sonar imaged other man-made structure; 100 of
its 261 waterfalls are blank this way, `Artificial_Reef_01` through `_05`
among them. See `docs/READING_RESULTS.md` Part 3b.

These frames are therefore **"no annotation present"**, not verified natural
seabed, and the file name overstates what is known. Read them as the former.
