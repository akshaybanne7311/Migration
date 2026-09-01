# F5 Config Intelligence

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/backend-Python%203.9%2B-3776AB?logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/frontend-React%2019-61DAFB?logo=react&logoColor=black" />
  <img alt="TypeScript" src="https://img.shields.io/badge/lang-TypeScript-3178C6?logo=typescript&logoColor=white" />
  <img alt="Docker" src="https://img.shields.io/badge/deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white" />
  <img alt="Tests" src="https://img.shields.io/badge/backend%20tests-78%20passing-2ea44f" />
</p>

<p align="center">
  F5 BIG-IP configuration intelligence and bulk VIP migration — ingest a UCS/QKView/<code>bigip.conf</code>,
  plan changes across hundreds of VIPs with a dependency-aware wizard, and generate real TMSH/REST/AS3 output.
</p>

---

## What it does

- **Ingests** BIG-IP UCS archives, QKViews, or raw `bigip.conf` files with a real tokenizer + recursive-descent
  parser (not regex) — correctly handles IPv4/IPv6 destinations, route domains, and shared nodes/pools/VLANs.
- **Smart Migration wizard** — select VIPs, review current config, choose changes (common + per-VIP exceptions),
  and validate/generate — built so a network engineer never needs to understand the dependency graph underneath.
- **Dependency-aware change engine** — a node or pool shared by dozens of VIPs is resolved and emitted exactly
  once, in the correct order, whether you're renumbering in place or generating a full recreate script for a
  new device.
- **TMSH / REST / AS3 generation** from one shared resolved-plan representation, so the three outputs can never
  drift from each other.
- **F5 GUI preview** — an editable recreation of the BIG-IP Configuration Utility. Change a field, and it computes
  the real TMSH command for that edit through the same backend engine the wizard uses — not a second, guessable
  formatter.
- **Excel & SOP export** — a real `.xlsx` workbook and a Word runbook (pre-migration checklist, validation
  results, numbered TMSH steps, sign-off table) generated from the same plan data.

## Screenshots

| Smart Migration — Validate & Generate | F5 GUI Preview — editable |
|---|---|
| ![Smart Migration Step 5](docs/screenshots/smart-migration-step5.png) | ![F5 GUI Preview](docs/screenshots/f5-gui-preview.png) |

| F5 GUI Preview — Virtual Server List | Light theme |
|---|---|
| ![F5 GUI list view](docs/screenshots/f5-gui-list.png) | ![Light theme](docs/screenshots/vips-light-theme.png) |

## Run with Docker (production-style)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API: proxied through the frontend at `/api/v1/...` (not exposed directly by default)
- Session data (uploaded archives + parsed session DBs) persists in the `f5ci-data` named volume across restarts

Override with environment variables (or a `.env` file next to `docker-compose.yml`):

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
cd backend && source .venv/bin/activate && pytest       # 78 tests
cd frontend && npx tsc --noEmit
```

## Architecture

One parsed representation (`ParsedConfig`) and one resolved-plan representation (`ResolvedMigrationPlan` /
`MigrationContext`) feed every consumer — the UI, the validator, and all three generators (TMSH/REST/AS3) — so
they cannot drift from each other. See `backend/app/` module docstrings for the parser, dependency graph,
change engine, and generator design notes.

```
UCS/QKView/bigip.conf
  → tokenizer + recursive-descent parser
  → typed domain objects (Vip, Pool, Node, Vlan, Monitor, Profile)
  → SQLite session store
  → dependency graph (networkx)
  → Smart Migration wizard → change engine (common changes ⊕ per-VIP exceptions)
  → validator (PASS / WARN / BLOCKED)
  → generators (TMSH / REST / AS3), all from one resolved plan
```

## Status

Backend and frontend are both fully tested against a synthetic fixture (78 backend tests, zero console errors
across every page in browser testing). Not yet validated against a real production UCS file, and SNAT pools /
self-IPs / route domain objects aren't modeled yet — see open items before treating this as production-ready
for your environment.
