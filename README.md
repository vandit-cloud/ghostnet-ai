# GhostNet-AI

AI-powered detection of ghost nets and marine debris in side-scan sonar imagery.
**SIH26057.**

Two members, two machines, one repository, one frozen contract between the
halves.

```
                    GitHub  (source of truth)
                           |
              +------------+------------+
              |                         |
           PC 1                      PC 2
        Member 1                   Member 2
     AI / ML / sonar            backend / frontend
              |                         |
              +--- contracts/*.json ----+
                     (the interface)
```

## Layout

| Path | Owner | Contents |
|---|---|---|
| `ai/` | Member 1 | Sonar preprocessing, detection, geotagging, the output contract |
| `app/backend/` | Member 2 | FastAPI, database, GIS |
| `app/frontend/` | Member 2 | Dashboard, map, review UI |
| `app/docker-compose.yml` | shared | Compose setup for the single-machine demo |
| `contracts/` | **shared, generated** | JSON Schemas both sides validate against |
| `demo/` | shared | Per-class demo sonar files, reports and showcase material |
| `docs/` | shared | Build plans and the handoff document |

## Data, provenance and attribution

Training data is not published here — it is large and often licence-restricted,
so acquisition is scripted in `ai/scripts/` and documented in
[`docs/DATA.md`](docs/DATA.md), which records every source and its terms.

One source is unresolved and we would rather say so than leave it implicit: the
73 `ghost_net` chips are third-party side-scan imagery whose origin we have not
been able to document. The chips are not published in this repository. What is
published is our own work over them — 425 polygon annotations, the labelling
convention, and the build scripts — plus a small number of low-resolution
annotated crops used to illustrate that convention. We make no ownership claim
over the underlying imagery and will remove any of it on request from a rights
holder. See [`docs/DATA.md`](docs/DATA.md#the-ghost_net-chips-an-open-provenance-question).

## Start here

- **Downloading data?** [`docs/DOWNLOAD_GUIDE.md`](docs/DOWNLOAD_GUIDE.md) — step-by-step, with links.
- **Member 2:** [`docs/HANDOFF.md`](docs/HANDOFF.md) to build the app before a
  model exists, then [`docs/INTEGRATION_PLAN.md`](docs/INTEGRATION_PLAN.md) to
  wire the trained one in. **Use `detect_batch`, not `detect` in a loop** -- it
  is ten times faster, for a reason explained there.
- **What the model can and cannot do:**
  [`docs/MODEL_CAPABILITY_EVIDENCE.md`](docs/MODEL_CAPABILITY_EVIDENCE.md),
  with the command to reproduce every number.
- **Member 1:** [`docs/SIH26057_GhostNet_AI_BASIC_BUILD_PLAN.md`](docs/SIH26057_GhostNet_AI_BASIC_BUILD_PLAN.md)
  is the build target; the two master plans are the reference behind it.

## Setup

```bash
git clone <repo> && cd ghostnet-ai

# Member 1 (GPU, pinned CUDA build)
python -m venv .venv --system-site-packages
.venv/Scripts/python -m pip install -r ai/requirements.txt
.venv/Scripts/python ai/scripts/fetch_weights.py

# Member 2 (consumer; CPU is fine)
pip install -e ai/
```

Weights and datasets are **not** in git. `fetch_weights.py` re-downloads the
pretrained ones; dataset acquisition is scripted separately.

## Verify the checkout

```bash
.venv/Scripts/python -m pytest ai/tests -q          # 36 tests
.venv/Scripts/python ai/scripts/export_schemas.py --check   # contracts not stale
.venv/Scripts/python ai/scripts/make_fixtures.py    # regenerate example payloads
```

## The contract

`contracts/*.schema.json` are **generated** from `ai/ghostnet/contract.py`. Never
edit them by hand — a hand-maintained copy becomes a second source of truth and
drifts. Change the dataclasses, re-run `export_schemas.py`, commit both.

`export_schemas.py --check` is the guard, and it runs in the test suite.

## Branches

```
main         stable, demo-ready
develop      integration
member1-ai   PC 1
member2-app  PC 2
```

Work on your own branch. Merge to `develop` when a feature is stable, test both
halves together there, then promote to `main`. Do not commit directly to `main`.

## Scientific honesty

The plans commit to it and the code enforces it, so please do not undo it in the UI:

- A position that cannot be derived is reported as `null`, never invented.
- Every position carries `position_error_m`. Render the circle, not a bare pin.
- `uncertainty: "low"` is unreachable until the model is genuinely calibrated.
- Synthetic and illustrative numbers are never presented as measured results.

This is worth more at judging than a higher number would be.
