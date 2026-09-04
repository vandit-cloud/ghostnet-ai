# Data acquisition — Phase 0

> **Just want the steps?** → **[DOWNLOAD_GUIDE.md](DOWNLOAD_GUIDE.md)** has the
> click-by-click instructions. This document is the *reasoning* behind them.

**Nothing is downloaded yet.** This document says what to get, in what order,
and what each source is actually good for. Verified against published sources on
2026-08-30; see `ai/data/provenance/dataset_candidates.csv` for the machine-readable
version with a `verification` column on every row.

The plan's rule applies throughout: **do not download datasets blindly, and do
not train before understanding what the data actually contains.**

---

## The two findings that change the plan

### 1. No public side-scan dataset contains ghost nets. Confirmed independently.

An October 2025 survey of sonar image datasets finds **no public SSS dataset
containing fishing nets or ghost nets** — it names this as an open gap in the
field. The build plan's own admission (B2) was correct.

This settles gap #4. A ghost-net F1 target cannot be honestly measured on real
data, because no real labelled ghost-net SSS data exists to measure it against.
The metric is therefore **binary artificial-vs-natural**, which real data does
support and which matches the problem statement's own wording — *"separates
natural seafloor topology from artificial anomalies."*

Say this out loud to the judges rather than hiding it. A team that knows why its
metric is framed the way it is looks stronger than one quoting a number it could
not have earned.

### 2. The 578 hard negatives are real — but not where you would look for them.

The plan's J1 hard-negative strategy depends on KLSG's 578 plain-seafloor images.
That count is **confirmed**: KLSG is 1,190 images — 385 wrecks, 36 drowning
victims, 62 planes, 129 mines, 578 seafloor.

**But they are not published anywhere.** Verified against the GitHub API on
2026-08-30:

| Repository | Actual contents |
|---|---|
| `huoguanying/SeabedObjects-Ship-and-Airplane-dataset` | 4 zips: `plane-real.zip` + `ship-real-1/2/3.zip`, ~50 MB. Ships and planes **only**. |
| `HHUCzCz/-SeabedObjects-KLSG--II` (advertises the 578) | **One 45 KB file, `A SSS image sample.jpg`. That is the entire repository.** |

Clone either expecting hard negatives and you get zero, with no error. Open
issues #1, #2 and #4 on the second repo all ask for the complete dataset and
none have been answered, so **email is the only remaining route** and it may not
work.

**Treat the Zenodo fallback as the likely path, not the emergency one.** If the 578 stay unobtainable, J1 needs a
different negative source (the Zenodo sediments set below is the fallback), and
that is a plan change you want in week one, not week three.

---

## Acquisition order

### 1. SCTD — start here

The only source that is real side-scan, has real bounding boxes, and downloads
without emailing anyone. `SCTD.zip` and `SCTD2.0.rar` are committed straight to
<https://github.com/MingqiangNing/SCTD>.

- `SCTD.zip`, **79 MB** of real data, no account needed. (`SCTD2.0.rar` is a
  134-byte Git LFS pointer, not a dataset — ignore it.)
- ~357 images: 57 plane, 266 ship, 34 drowning victim
- **Pascal VOC XML** boxes, with a `voc2coco.py` in the repo
- Count caveat: the SCTD 1.0 paper cites 596 images, but the published class
  breakdown sums to 357. `inventory.py` will tell you which is true once it is
  extracted — that is precisely what it is for.

Extract to `ai/data/raw/research/SCTD/`.

### 2. AI4Shipwrecks

<https://umfieldrobotics.github.io/ai4shipwrecks/> (hosted via UMich Deep Blue Data).

- 286 high-resolution SSS images across 28 wrecks, PNG
- **Pixel-wise segmentation masks** → convert to YOLO polygons
- Caveat worth stating in the report: collected in Thunder Bay, Lake Huron — a
  **freshwater lake floor**. Sediment and clutter differ from Indian coastal
  seabed. It is good data; it is not in-domain.

Extract to `ai/data/raw/research/AI4SHIPWRECKS/`.

### 3. KLSG — for the hard negatives, if they can be obtained

Try in this order:

1. ~~`HHUCzCz/-SeabedObjects-KLSG--II`~~ — **dead end, confirmed.** The repo
   advertises the 578 seafloor images in its description but contains exactly one
   45 KB sample JPEG and nothing else. Three open issues ask for the full set;
   none answered.
2. The Kaggle mirror, `enochkwatehdongbo/seabedobjects-klsg-dataset` — direct
   download with an account, but **verify it actually includes the seafloor
   class**; a mirror may carry only the public subset.
3. Email the maintainer: `huoguanying@hhu.edu.cn` / `huoguanying@163.com`.
   Academic use is stated. Assume days of turnaround — send it early, in parallel
   with everything else, not when you are blocked on it.

Classification-only: **no boxes**. Fine for hard negatives, which need no boxes,
and fine for a `natural` class. Not a detection source.

### 4. Fallback negatives — Zenodo seafloor sediments

<https://zenodo.org/records/10209445> — 434,164 SSS images of seafloor sediments,
rocks and marine life. Direct download.

**Not usable, checked 2026-08-30.** The record is a single split archive --
`.z01` (21.5 GB) + `.z02` (21.5 GB) + `.zip` (9.3 GB) -- totalling 52.3 GB. The
`.zip` is the final segment carrying the central directory, so no part extracts
on its own and there is no way to take a small slice.

**Replaced by hard-negative mining from SONARDETECT** (plan §22). Its 581 frames
carry boxes on every object, so any tile overlapping no box is plain seabed from
the same sensor and survey as the positives. That is better than a foreign
survey, not just cheaper: a different seabed can be separated on texture or gain
alone, inflating the artificial-vs-natural score without the model learning
anything about objects.

---

## Deliberately not used, and why

**MDT marine debris** (<https://github.com/mvaldenegro/marine-debris-fls-datasets>)
and **UATD** are the only real marine-*debris* sonar datasets found — tyres,
cans, bottles, chains, hooks. Both are **forward-looking sonar, not side-scan**,
and MDT was captured in a watertank.

That is a genuine modality mismatch, not a technicality. FLS and SSS differ in
viewing geometry and in how acoustic shadow — the primary cue for a raised object
on the seabed — forms at all. Training a side-scan model on watertank FLS imagery
and reporting the result as side-scan performance would be the kind of quiet
dishonesty the plan's §25 rules exist to prevent.

If they are used at all, it must be stated explicitly in the report.

---

## Before you train on anything

```bash
.venv/Scripts/python ai/scripts/inventory.py --verbose
```

This scans `ai/data/raw/` and writes `ai/data/provenance/data_inventory.csv` with
the field list from plan §5. Every column is measured by reading files: real
image counts, real pixel dimensions, annotation format inferred from what is
present, and whether any navigation or GPS data exists.

It cross-checks the counts against `dataset_candidates.csv` and **flags any
dataset where the claim and the disk disagree**, along with any dataset whose
licence is still unverified.

`dataset_candidates.csv` is what sources *claim*. `data_inventory.csv` is what we
*have*. They are separate files on purpose — the fastest way to break the plan's
own rule is to let a cited image count stand in for a directory nobody opened.

---

## Licensing

None of these carry a formal licence file. KLSG and SCTD state academic use;
AI4Shipwrecks and the Zenodo sediments set are published research datasets.

For a hackathon submission this is workable, but **record the provenance and cite
every source** — that is what the `provenance/` directory is for, and it is why
it is the one directory under `ai/data/` that git tracks.

---

## Sources

- [Sonar Image Datasets: A Comprehensive Survey (arXiv 2510.03353)](https://arxiv.org/html/2510.03353v1)
- [SCTD — Sonar Common Target Detection](https://github.com/MingqiangNing/SCTD)
- [AI4Shipwrecks](https://umfieldrobotics.github.io/ai4shipwrecks/)
- [SeabedObjects-KLSG-II](https://github.com/HHUCzCz/-SeabedObjects-KLSG--II)
- [SeabedObjects Ship and Airplane (public subset)](https://github.com/huoguanying/SeabedObjects-Ship-and-Airplane-dataset)
- [Seafloor Sediments, Zenodo](https://zenodo.org/records/10209445)
- [Marine Debris FLS datasets](https://github.com/mvaldenegro/marine-debris-fls-datasets)
- [OpenSonarDatasets index](https://github.com/remaro-network/OpenSonarDatasets)
