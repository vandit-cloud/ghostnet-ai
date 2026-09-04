# GhostNet-AI — Member 2 (Frontend + Backend + Database + GIS)

Implementation of `SIH26057_MEMBER_2_FRONTEND_BACKEND_DATABASE_GIS_BUILD_PLAN.md`: the web application, FastAPI backend, PostgreSQL/PostGIS database, GIS map, detection review workflow, reports, and realtime updates that wrap Member 1's sonar-AI pipeline.

Member 1's real model is not yet integrated — the AI seam (`backend/app/services/ai_service.py`) currently uses `MockAIAdapter`, which produces contract-valid, clearly-labelled synthetic detections (spec section 67) so the whole application can be built, demoed, and tested ahead of the real model. Swapping in the real service means implementing `AIServiceAdapter.analyze_frame` against Member 1's inference call — nothing else in the app needs to change.

## Stack

- **Frontend:** Next.js 14 (App Router) + TypeScript, TanStack Query, Zustand, React Hook Form + Zod, Tailwind, Leaflet.
- **Backend:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic, Python 3.11.
- **Database:** PostgreSQL 16 + PostGIS.
- **Realtime:** native WebSocket (`/api/v1/ws/surveys/{survey_id}`).
- **Background jobs:** in-process `asyncio` tasks, state persisted in `processing_jobs` / `reports` tables so a browser refresh never restarts work.

## Run it (Docker Compose)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs
- Seed login: **operator / operator123**

If ports 5432/8000/3000 are already used by something else on your machine, add a `docker-compose.override.yml` remapping the host ports (see comments in `docker-compose.yml`).

## Run it locally (without Docker)

**Database** — any PostgreSQL 16 with the PostGIS extension available, e.g.:

```bash
docker run -d -p 5432:5432 -e POSTGRES_USER=ghostnet -e POSTGRES_PASSWORD=ghostnet -e POSTGRES_DB=ghostnet postgis/postgis:16-3.4
```

**Backend:**

```bash
cd backend
python -m venv .venv --system-site-packages    # see the note below
.venv/Scripts/activate                         # or source .venv/bin/activate
pip install -r requirements.txt
pip install -e ../../ai --no-deps              # the AI half, from ai/ in this repo
cp .env.example .env   # adjust DATABASE_URL if needed
alembic upgrade head
uvicorn app.main:app --reload
```

> **Why `--system-site-packages`, and why `--no-deps`.** The backend imports
> `ghostnet` in-process, and `ghostnet` needs torch, torchvision, ultralytics,
> opencv and pyproj — about 2.6 GB. That set is expected to be installed
> already, at the exact versions pinned in `requirements-ai.txt` at the
> repository root, so the venv inherits it instead of downloading a second
> copy. `--no-deps` stops pip re-resolving it to versions the model was never
> trained or evaluated against.
>
> The venv still shadows what it installs itself, so the backend keeps its own
> newer FastAPI, pydantic, SQLAlchemy, starlette and uvicorn — verified.
>
> The cost is that this venv is **not self-describing**: `pip list` inside it
> will not explain why `torch` imports. If `ghostnet.config.SETTINGS.device`
> ever reports `cpu` on a machine with a GPU, suspect a broken torch install
> rather than a missing GPU — `resolve_device()` catches the failure and falls
> back silently.
>
> A fully isolated venv works too; it just downloads torch again (~12 min) and
> gives you a second copy on disk. Nothing in the app depends on which you pick.
>
> Without the AI package the backend still runs: `get_ai_adapter()` falls back
> to `MockAIAdapter` and every payload is stamped
> `model_version: mock-ghostnet-dev-v0`, so mock results can never be mistaken
> for real ones later.

**Frontend:**

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## Docker gives you the app, with a STAND-IN detector

`docker compose up` builds the backend from the `./backend` context, which
cannot reach `ai/` at the repository root. The image has no torch and no
`ghostnet`, so `get_ai_adapter()` falls back to `MockAIAdapter`.

Everything runs — upload, processing, map, reports — but the detections are
invented. They are stamped `model_version: mock-ghostnet-dev-v0` and the
backend logs `AI adapter: MockAIAdapter -- these are NOT real detections` at
startup, so a stored result can always be traced back. **Do not demo from
Docker.** The mock's numbers look plausible on the dashboard and the map; you
have to open a detection's detail page to see which detector produced them.

For real detections use the local setup above. Making the image self-sufficient
means moving the compose context to the repository root and baking ~2.6 GB of
torch/CUDA into the layer — a decision nobody has taken yet.

## Tests

Backend (needs a running Postgres+PostGIS — detections use a PostGIS geometry column with no sqlite equivalent):

```bash
cd backend
createdb ghostnet_test   # or: docker exec <db-container> psql -U ghostnet -d postgres -c "CREATE DATABASE ghostnet_test"
pytest
```

Frontend:

```bash
cd frontend
npm test          # vitest — utils/components
npx tsc --noEmit  # type-check
npm run build     # full production build
```

## Demo flow (spec section 73)

Login → create survey → upload sonar file (+ optional metadata) → validate → start processing → watch live pipeline stages over WebSocket → detections persist → view in list / detail / sonar viewer / GIS map / dashboard → review an uncertain detection → generate + download a CSV/JSON report.

## Known follow-ups

- `next` currently has residual npm-audit advisories that only a Next.js 16 (breaking, App Router changes) fully resolves; deferred per spec section 71 (security hardening is a company-grade upgrade, not a basic-build blocker).
- Auth is a single seeded operator account with JWT — full RBAC/multi-user auth is part of the company-grade plan (spec section 71), not the basic build.
