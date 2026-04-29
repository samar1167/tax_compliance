# Tax Compliance MVP

Split-stack MVP for an Indian personal tax compliance engine:
- `backend/`: Django admin, persistence, deterministic API layer
- `frontend/`: Next.js assessment UI
- `knowledge_base/`: versioned tax rule files
- `docs/`: module and process notes

## Current module

The MVP currently exposes:
- health check
- knowledge base summary
- knowledge base version management
- knowledge base bundle activation
- filing obligation and `ITR-1` / `ITR-2` evaluation

## Run locally with Docker Compose

```bash
docker compose up --build
```

Endpoints:
- Frontend: `http://localhost:3011`
- Backend API: `http://localhost:9010/api/health/`
- Django admin: `http://localhost:9010/admin/`

## Run locally without Docker

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_kb_snapshot
python manage.py createsuperuser
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
rm -rf .next
npm run dev
```

## Notes

- The backend reads the seeded knowledge base from `knowledge_base/tax_rules/`.
- The runtime imports packageized KB content from `knowledge_base/packages/`.
- The rules engine is intentionally deterministic and traceable.
- The frontend currently focuses on a single assessment workflow for `FY 2025-26 / AY 2026-27`.
- For Docker, the frontend uses `API_BASE_URL=http://backend:9010` internally and `NEXT_PUBLIC_API_BASE_URL=http://localhost:9010` in the browser.
- The KB lifecycle is documented in `docs/knowledge-base-process.md`.
- If the frontend shows a stylesheet parse error, rebuild after clearing `frontend/.next` so stale build artifacts do not interfere.
- In Docker, the frontend container now clears `.next` on startup and keeps `/app/.next` on its own volume to avoid host build artifacts polluting the container runtime.

## Bundle Workflow

Example bundle-aware workflow:

```bash
docker compose run --rm backend python manage.py import_kb_package /knowledge_base/packages/ay2026_27_v1_1_bundle_experiment
docker compose run --rm backend python manage.py validate_kb_version <version_id>
docker compose run --rm backend python manage.py activate_kb_version <version_id>
docker compose run --rm backend python manage.py list_kb_bundles <version_id>
docker compose run --rm backend python manage.py activate_kb_bundle <version_id> synthetic_itrx_experiment
```

This keeps the KB version stable while allowing dependency-checked activation of experimental rule bundles.
