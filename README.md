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
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # adjust DATABASE_URL if needed
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

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
