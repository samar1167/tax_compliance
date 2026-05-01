# Tax Compliance MVP

AI-assisted Indian personal tax compliance engine focused on deterministic filing-obligation and ITR-selection logic, backed by a versioned knowledge base and an extendable Django + Next.js architecture.

Current direction:
- target user: Indian resident salaried individual
- initial return focus: `ITR-1` and `ITR-2`
- AI role: knowledge-base bootstrapping, explanations, guidance
- deterministic role: thresholds, filing obligation, form selection, validation gates

Project layout:
- `backend/`: Django backend, admin, KB import/validation/activation, APIs
- `frontend/`: Next.js workflow UI
- `knowledge_base/`: versioned rule packages and seed material
- `docs/`: process and design notes

## 1. Setting Up A Fresh New Environment

### Option A: Docker-first setup

From the repo root:

```bash
docker compose up --build
```

Main URLs:
- frontend: `http://localhost:3011`
- backend API: `http://localhost:9010/api/health/`
- Django admin: `http://localhost:9010/admin/`

What happens on backend startup:
- migrations run
- default KB bootstrap command runs
- active KB version becomes available for evaluation

Create a Django admin user through Docker:

```bash
docker compose run --rm \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@example.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin123 \
  backend sh -c "python manage.py migrate && python manage.py sync_kb_snapshot && python manage.py createsuperuser --noinput"
```

### Option B: Local setup without Docker

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_kb_snapshot
DJANGO_SUPERUSER_USERNAME=admin \
DJANGO_SUPERUSER_EMAIL=admin@example.com \
DJANGO_SUPERUSER_PASSWORD=admin123 \
python manage.py createsuperuser --noinput
python manage.py runserver 9010
```

Frontend:

```bash
cd frontend
npm install
rm -rf .next
npm run dev
```

### First sanity checks

Health:

```bash
curl http://localhost:9010/api/health/
```

Active KB summary:

```bash
curl http://localhost:9010/api/knowledge-base/summary/
```

Required inputs for a specific KB version:

```bash
curl http://localhost:9010/api/knowledge-base/versions/1/required-inputs/
```

Legitimate backend assessment example:

```bash
curl -X POST http://localhost:9010/api/assessments/evaluate/ \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "assessment_year": "2026-27",
      "financial_year": "2025-26",
      "basic_exemption_limit": 300000
    },
    "profile": {
      "person_type": "individual",
      "residential_status": "resident_ordinary",
      "age_on_previous_year_end": 32,
      "is_director_in_company": false,
      "held_unlisted_equity_shares": false,
      "has_foreign_asset": false,
      "has_foreign_signing_authority": false,
      "has_foreign_source_income": false,
      "has_deferred_esop_tax": false,
      "tds_under_194n": false,
      "is_beneficiary_of_foreign_asset": false
    },
    "income": {
      "total_income": 1200000,
      "total_income_before_specified_exemptions_and_chapter_via": 1200000,
      "salary_income": 1200000,
      "house_property_count": 1,
      "agricultural_income": 0,
      "business_or_profession_income": 0,
      "business_turnover": 0,
      "professional_receipts": 0,
      "short_term_capital_gains": 0,
      "ltcg_112a_amount": 0,
      "other_capital_gains_amount": 0,
      "brought_forward_loss_exists": false,
      "loss_to_carry_forward_exists": false,
      "partnership_firm_interest_salary_bonus_commission": 0
    },
    "specified_triggers": {
      "current_account_deposits": 0,
      "foreign_travel_expenditure": 0,
      "electricity_expenditure": 0,
      "aggregate_tds_tcs": 45000,
      "savings_bank_deposits": 200000
    }
  }'
```

Expected direction:
- filing obligation should be `required`
- recommended form should typically be `ITR-1`

### Knowledge-base package workflow

Import a package:

```bash
docker compose run --rm backend python manage.py import_kb_package /knowledge_base/packages/ay2026_27_v1_1_bundle_experiment
```

Validate a package version:

```bash
docker compose run --rm backend python manage.py validate_kb_version <version_id>
```

Activate a package version:

```bash
docker compose run --rm backend python manage.py activate_kb_version <version_id>
```

List bundles:

```bash
docker compose run --rm backend python manage.py list_kb_bundles <version_id>
```

Activate a bundle:

```bash
docker compose run --rm backend python manage.py activate_kb_bundle <version_id> synthetic_itrx_experiment
```

Deactivate a bundle:

```bash
docker compose run --rm backend python manage.py deactivate_kb_bundle <version_id> synthetic_itrx_experiment
```

Related process note:
- [docs/knowledge-base-process.md](/home/samar/projects/tax_compliance/docs/knowledge-base-process.md)

## 2. Prompts Used For Creating This System

These are the reusable prompt shapes that drove the current system design.

### Product-definition prompt

```text
We are designing an AI-assisted Indian personal tax compliance intelligence engine.

Current scope:
- MVP focused on Indian resident salaried individuals
- Support ITR-1 / ITR-2 initially
- Goal is to build structured compliance knowledge base + reasoning engine
- Use AI for knowledge base bootstrapping, explanations, and guidance
- Use deterministic rules for calculations/threshold logic

Please help me design the first module:
Indian Personal Tax Filing Obligation + ITR Selection Engine

Start with:
1. Structured rule schema / ontology
2. Initial knowledge base entries
3. Deterministic rule logic
4. Validation against official Indian tax guidance
5. Suggested system design for implementation
```

### Builder prompt for MVP scaffolding

```text
Lets go ahead and start creating MVP.
I want a typical django based backend with admin and nextjs based frontend, exposing necessary APIs.
I want both to stay in this directory structure separately.
Enable docker compose etc for docker.
```

### Knowledge-base architecture prompt

```text
Now get rules, seed and other things from knowledge base exposed in the system.
I want a system where I can continue to inject rules/seed in the system in future.
Therefore, design step based process and let me know the approach.
```

### Package-based KB implementation prompt

```text
You can use existing knowledge base or get new knowledge within the given framework.
After implementing, let me know its execution process snapshot.
```

### Controlled experiment prompt

```text
Lets add a test rule.
Say, if house_property_count is more than 1, neither ITR1 or ITR2 is valid.
A special ITRx need to be filed.
How do I make it effective?
```

### Safer activation-model prompt

```text
Can we activate/deactivate the new rule.
However, there can be dependencies.
Before you generate code, discuss.
```

This led to the current approach:
- KB version is the main release unit
- bundles are the safe activation layer
- rules can carry metadata for status, dependencies, produced fields, and required fields
- evaluation is deterministic and traceable
- incomplete inputs are blocked before decisioning

### Strict backend-validation prompt

```text
When I test with some fields not present, I am not getting error.
Are we ensuring all required data is captured before validation can be applied?
```

This led to:
- required-input derivation from active effective rules
- `400` responses for missing required inputs
- dedicated required-inputs endpoint for clients

## 3. Prompt For Continued Extension Of Current System

Use the following prompt as the default continuation prompt for future work on this repo:

```text
We are extending an AI-assisted Indian personal tax compliance system.

Current architecture:
- Django backend with admin and JSON APIs
- Next.js frontend workflow UI
- Docker Compose local setup
- Versioned knowledge-base packages under knowledge_base/packages/
- Deterministic rules engine for filing obligation and ITR selection
- Bundle-aware activation model for experimental or dependent rule groups
- Required-input validation before assessment is allowed

Current product scope:
- Indian resident salaried individuals
- ITR-1 and ITR-2 as the main supported forms
- AI only for explanations, knowledge-base drafting, and guidance
- Deterministic logic for thresholds, validation, obligation, and form recommendation

Working rules:
1. Do not replace deterministic logic with AI decisioning.
2. Preserve KB versioning, package import, validation, activation, and bundle workflows.
3. Prefer extending the knowledge base and test cases over hardcoding one-off rules.
4. Any new rule with non-trivial behavioral impact should include:
   - source metadata
   - rule metadata
   - regression test coverage
   - activation strategy
5. If introducing experimental behavior, put it behind a bundle rather than making it globally active by default.
6. If adding new required facts, expose them through the required-input API.
7. Maintain explainability: every decision should stay traceable to rule ids and KB version context.

When extending the system, do the following:
1. inspect the current code and knowledge-base structure first
2. explain the design impact briefly
3. implement end-to-end changes
4. add or update KB package content and tests where appropriate
5. update README or docs if operator workflow changes
6. summarize execution steps and verification at the end

Current priority:
[replace this line with the next feature or compliance module to build]
```

## Notes

- The runtime imports packageized KB content from `knowledge_base/packages/`.
- The rules engine is intentionally deterministic and traceable.
- Bundles are the safe feature-toggle layer; individual rules are not meant to be toggled ad hoc in production.
- The backend now exposes required-input metadata so clients can collect complete data before rule execution.
