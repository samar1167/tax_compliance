# Tax Compliance MVP

Split-stack MVP for an Indian personal tax compliance engine:
- `backend/`: Django admin, persistence, deterministic API layer
- `frontend/`: Next.js workflow UI
- `knowledge_base/`: versioned tax rule files
- `docs/`: module and process notes

## Current module

The MVP currently exposes:
- health check
- knowledge base summary
- knowledge base version management
- knowledge base bundle activation
- filing obligation and `ITR-1` / `ITR-2` evaluation
- document-backed `ITR-1` / `ITR-2` return data preparation for validation
- guided taxpayer workflow UI for onboarding, source capture, declared data entry, ITR recommendation, and final validation

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
npm run dev
```

## Notes

- The backend reads the seeded knowledge base from `knowledge_base/tax_rules/`.
- The runtime imports packageized KB content from `knowledge_base/packages/`.
- The rules engine is intentionally deterministic and traceable.
- The frontend implements a 5-step workflow:
  1. create a tax user and source-capture session
  2. add required source data with validation and test-record support
  3. collect declared data
  4. get the recommended ITR from the assessment engine
  5. run final validation and review the report
- The KB lifecycle is documented in `docs/knowledge-base-process.md`.

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

## Return Preparation Endpoint

The backend now supports a document reconciliation step before return validation:

- `POST /api/returns/prepare-validation/`
- `GET /api/return-sources/types/?return_type=ITR-1`
- `GET /api/return-sources/test-records/?return_type=ITR-2`
- `POST /api/return-sources/sessions/`
- `GET /api/return-sources/sessions/<session_id>/`
- `POST /api/return-sources/sessions/<session_id>/records/`

Request shape:

```json
{
  "return_type": "ITR-2",
  "context": {
    "assessment_year": "2026-27",
    "financial_year": "2025-26",
    "basic_exemption_limit": 300000
  },
  "declared_data": {
    "profile": {
      "residential_status": "resident_ordinary"
    },
    "income": {
      "salary_income": 900000,
      "total_income": 1100000,
      "short_term_capital_gains": 200000
    }
  },
  "documents": [
    {
      "document_type": "form16",
      "data": {
        "salary_income": 900000,
        "total_income": 1100000
      }
    },
    {
      "document_type": "capital_gains_statement",
      "data": {
        "short_term_capital_gains": 200000
      }
    },
    {
      "document_type": "ais",
      "data": {
        "salary_income": 900000,
        "short_term_capital_gains": 200000
      }
    }
  ]
}
```

Response includes:

- `flags`: missing-document and mismatch flags
- `field_comparisons`: per-field reconciliation status across declared and document-backed values
- `validation_payload`: final normalized payload prepared for the rules engine
- `validation_result`: existing filing-obligation / form-selection output run on the prepared payload

Source capture note:

- Source upload is not implemented yet.
- The backend can now list applicable source types for `ITR-1` and `ITR-2`, mark them as mandatory or optional, create a source-capture session, and save source data entered manually.
- Seeded test records are available per source type so the workflow can be exercised before real file upload exists.
