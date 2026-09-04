# Raw research datasets — pruned 2026-09-05

These source downloads were deleted to reclaim disk (~29 GB → ~9 GB). **Nothing
derived from them was lost:** every one had already been normalised into
`ai/data/interim/` and built into `ai/data/processed/`, which is what training
and evaluation actually read. `processed/build_report.json` records each
source's exact contribution.

**What this costs.** You can still train, re-train and re-run every published
metric from `processed/`. What you cannot do offline any more is *re-derive* the
dataset from source — new splits, different tiling, changed augmentation — that
needs these downloads back.

## Deleted, with what each contributed

| dataset | size | images it contributed |
|---|---|---|
| `SubPipeMini2` | 14.53 GB | 2,049 (SUBPIPE) |
| `AI4Shipwrecks` | 1.13 GB | 6,976 |
| `China-Offshore-SSS-AI_Zenodo_public_upload` + `.zip` | 1.85 GB | 2,072 |
| `GhostVision_DatasetAndModels` | 0.88 GB | 6,655 |
| `KLSG` | 0.09 GB | — (surveyed, not built in) |
| `SCTD` | 0.08 GB | 327 (30 exact duplicates dropped) |
| `MARINE-PULSE` | 0.06 GB | 88 |
| `SONARDETECT` | 0.04 GB | 70 |
| `MGDS_Download.tar`, `NBP050501B.XTF.gz` | 0.33 GB | — (redundant copies, see below) |

## Deliberately kept

| kept | why |
|---|---|
| `GHOSTNET-HAND` (147 files), `PLANE-HAND` (125 files) | **Hand-annotated by us. Not re-downloadable at any price.** 30 MB total. |
| `MGDS_Download/MGDS_Download/NBP0505/NBP050501B.XTF/NBP050501B.XTF` | 209 MB. The demo file's provenance — `demo/RAW_DATA.md` cites its sha256, and `demo/NBP0505_line01B_demo.xtf` is its first 40,000,000 bytes. |

The `.tar` and `.gz` copies of that survey line went because the decompressed
`.XTF` is the one everything references. Verified before deleting: the tar held
exactly 2 entries, both present extracted.

The China-Offshore zip was verified byte-for-byte against its extracted
directory — 3,268 files and 0.95 GB on both sides — before removal.

## Getting them back

Sources and download instructions are in
`docs/SIH26057_MEMBER_1_DATASET_COLLECTION_AND_SOURCES.md` and
`docs/SIH26057_MEMBER_1_COMPLETE_DATASET_LIBRARY_BASIC_TO_ADVANCED.md`. All of
the deleted sets are public research datasets. After re-downloading, rebuild
with:

```bash
python ai/scripts/build_dataset.py     # raw -> interim -> processed
```

Compare the new `processed/build_report.json` against the committed one:
`images_per_source`, `split_sizes` and `boxes_per_class_per_split` should match,
since the split is seeded (`seed` is recorded in the report).
