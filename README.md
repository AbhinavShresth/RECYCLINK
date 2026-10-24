# RecycLink

RecycLink is being built alongside the existing HiLabs/Centene data pipeline in the parent workspace. The parent pipeline and its data are preserved. This README distinguishes the new React/FastAPI foundation from the earlier local Node demonstration, which remains available during the migration.

## Architecture (implemented phases 1–9)

- `frontend/`: React 19, strict TypeScript, Vite, Tailwind, React Router, TanStack Query, React Hook Form/Zod, Recharts, Leaflet, ElevenLabs' official React SDK, and accessible Lucide controls. Session tokens are not stored in localStorage.
- `backend/`: FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic, PostgreSQL driver, Argon2 password hashing, signed HttpOnly cookies, and CSRF validation on authenticated writes.
- `infrastructure/docker-compose.yml`: PostgreSQL 16 development service. Docker was not installed in this environment, so Compose startup is not yet verified.
- `ml/`: explicit TrashNet/TACO mapping notes, MobileNetV3-Small transfer learning, exact-image hash grouping, evaluation reports, and dataset inspection/validation scripts. No dataset or trained checkpoint is supplied.
- `server.js`, `web/`, and `test/`: the original standalone Node/SQLite demo. Its database remains intact; it is not the target architecture and is not connected to the new API.

The relational schema covers identity and roles; private locations; recycler profiles/service areas; classifications/feedback; listings/offers; collection transitions/history/notifications; persisted road-route plans/stops; simulated/device bin readings, alerts and collection events; inventory receipts and ledger movements; processing batches/recovered lots; and material sales/payment records. PostgreSQL is the target database. SQLite is an explicit development and test fallback.

See [the implementation plan](../docs/IMPLEMENTATION_PLAN.md) for the phased roadmap. API and schema docs are in `../docs/`.

## Run the new application

Prerequisites: Node.js 22.12+ (Node 24 is used here), Python 3.12, and npm. Docker Desktop is needed only for PostgreSQL; SQLite can run locally without it.

1. Copy `.env.example` to `.env`. For PostgreSQL, start the service from this directory:

   ```powershell
   docker compose -f infrastructure/docker-compose.yml up -d postgres
   ```

   If Docker is unavailable, change `DATABASE_URL` in `.env` to `sqlite:///./data/recyclink-api.sqlite` and run commands from `backend/`.

2. Install and migrate the backend from `backend/`:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   On a normal Python installation, replace the bundled interpreter path with `python`.

3. In another terminal, from `frontend/`:

   ```powershell
   npm ci
   npm run dev
   ```

   Open <http://127.0.0.1:5173>. API docs are at <http://127.0.0.1:8000/docs>; liveness/readiness are `/api/v1/health/live` and `/api/v1/health/ready`.

4. To create fictional development identities, run from `backend/` after migration:

   ```powershell
   $env:DEMO_PASSWORD = "recyclink-demo-2026"
   .\.venv\Scripts\python.exe -m scripts.seed_dev --demo
   ```

   The seeder refuses to create demo identities when `APP_ENV=production`. Do not reuse the example password. For an administrator, use `python -m scripts.bootstrap_admin <email> --name "Name"`; it prompts for a password and does not provide a default admin account.

## Configuration

The root `.env.example` contains local-only PostgreSQL values, the backend secret placeholder, frontend origin, and optional integrations. Generate a new `SECRET_KEY` before any shared deployment. `DATABASE_URL` may explicitly select SQLite for local fallback. Backend cookies become Secure in production; authenticated state-changing endpoints require the CSRF cookie/header pair.

Optional provider variables are left empty by default. ElevenLabs requires an Agent ID and server-side API key; routing requires an operator-configured road-routing endpoint; model inference requires a trained checkpoint at `ML_MODEL_PATH`. Missing providers must stay visibly unavailable; there are no fake successful predictions, voice sessions, or road routes.

## Tests and checks

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic current
```

From `frontend/`:

```powershell
npm run build
npm test
```

The backend tests use isolated in-memory SQLite. The existing Node demo has its separate test suite: `npm test` from `recyclink/`.

## Current feature status

The connected app includes secure authentication and roles, private locations, recycler profiles/discovery, honest model readiness/history/feedback and manual category fallback, marketplace listings/offers/collection lifecycle, persisted notifications, OSRM route planning, ledger inventory, facility receipt, mass-balanced processing, recovered lots, material sales, smart-bin simulator/alerts, record-backed role analytics, metadata-only administrator audit records, and an ElevenLabs signed-session integration with authenticated browser tools.

No physical IoT device, external road router, or live ElevenLabs account is connected in this environment. The bin simulator advances when an administrator triggers it; these records are marked SIMULATED. Analytics currently provide aggregate totals and category/status charts, not forecasting or a complete historical time-series suite. No TrashNet/TACO data was downloaded; no model training/evaluation occurred; and no accuracy metrics are available. The classification UI explicitly reports that its trained checkpoint is unavailable and supports manual category selection. Payment is manually marked by a recycler using a confirmation reference; no gateway is connected. Docker/PostgreSQL has not been exercised because Docker is unavailable locally.

## External configuration still needed

- ElevenLabs: `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, and the client-tool contract in [the voice integration guide](../docs/ELEVENLABS_INTEGRATION.md).
- Road routing: set an operator-controlled `OSRM_BASE_URL`. The app intentionally does not assume public OSRM capacity.
- Image classifier: acquire licensed data, review mappings in `ml/labels.json`, train and evaluate; point `ML_MODEL_PATH` at the resulting checkpoint. See [ML pipeline notes](../docs/ML_PIPELINE.md).
- PostgreSQL: use Docker Compose or a managed PostgreSQL endpoint; SQLite is only a local development fallback.

## Project phase report

Phases 1–10 are implemented and verified to the limits above. The backend has 27 tests, the ML split utilities have 2 tests, the frontend has 1 Vitest test, and the preserved legacy prototype has 3 workflow tests. See [the final demo script](../docs/DEMO_SCRIPT.md) for the live presentation sequence. No phase is treated as proof of a live external provider unless that provider was exercised.
