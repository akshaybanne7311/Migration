# F5 Config Intelligence

BIG-IP UCS/QKView/bigip.conf ingestion, dependency-aware bulk VIP migration
planning, and TMSH/REST/AS3 generation, driven by a 5-step Smart Migration
wizard.

## Run with Docker (production-style)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API: proxied through the frontend at `/api/v1/...` (not exposed
  directly by default)
- Session data (uploaded archives + parsed session DBs) persists in the
  `f5ci-data` named volume across restarts.

Override with environment variables (or a `.env` file next to
`docker-compose.yml`):

| Variable | Default | Purpose |
|---|---|---|
| `FRONTEND_PORT` | `8080` | Host port the UI is served on |
| `BACKEND_WORKERS` | `4` | Gunicorn/Uvicorn worker count |
| `F5CI_CORS_ORIGINS_RAW` | `http://localhost:8080` | Comma-separated allowed CORS origins |
| `F5CI_MAX_UPLOAD_BYTES` | `536870912` (512 MB) | Upload size cap |

## Run locally for development

Backend (Python 3.9+):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"   # adds pytest
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 20+):
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to :8000
```

## Tests

```bash
cd backend && source .venv/bin/activate && pytest
cd frontend && npx tsc --noEmit
```

## Architecture

One parsed representation (`ParsedConfig`) and one resolved-plan
representation (`ResolvedMigrationPlan` / `MigrationContext`) feed every
consumer — the UI, the validator, and all three generators (TMSH/REST/AS3)
— so they cannot drift from each other. See `backend/app/` module
docstrings for the parser, dependency graph, change engine, and generator
design notes.
