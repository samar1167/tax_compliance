# Knowledge Base Injection Process

This system is designed to let future rules and seed data enter through versioned knowledge-base packages instead of direct code edits.

## Package Structure

Each knowledge-base package should follow this shape:

```text
knowledge_base/packages/<package_name>/
  manifest.yaml
  sources.yaml
  thresholds.yaml
  rules/
    filing_obligation.yaml
    itr_selection.yaml
  tests/
    smoke_cases.yaml
```

## Step-Based Lifecycle

1. Author a package
- Add or update `manifest`, `sources`, `thresholds`, `rules`, and `tests`.

2. Import the package
- Run `python manage.py import_kb_package <package_path>`
- The backend stores the package as a database-backed KB version.

3. Validate the package
- Run `python manage.py validate_kb_version <version_id>`
- The system checks schema, rule references, supported operators, and regression cases.

4. Activate the package
- Run `python manage.py activate_kb_version <version_id>`
- The system retires any currently active version for the same module and AY, then promotes the chosen version.

5. Optionally activate a rule bundle
- Run `python manage.py list_kb_bundles <version_id>`
- Run `python manage.py activate_kb_bundle <version_id> <bundle_code>`
- Or disable it with `python manage.py deactivate_kb_bundle <version_id> <bundle_code>`
- Bundle toggles are validated against dependencies and regression cases before they are accepted.

6. Execute assessments
- Runtime APIs evaluate taxpayer facts against the active version.
- The decision trace records which rule ids fired and which KB version produced the answer.

## API Snapshot

- `GET /api/knowledge-base/summary/`
- `GET /api/knowledge-base/versions/`
- `GET /api/knowledge-base/versions/{id}/`
- `POST /api/knowledge-base/import/`
- `POST /api/knowledge-base/versions/{id}/validate/`
- `POST /api/knowledge-base/versions/{id}/activate/`
- `GET /api/knowledge-base/versions/{id}/bundles/`
- `POST /api/knowledge-base/versions/{id}/bundles/{bundle_code}/activate/`
- `POST /api/knowledge-base/versions/{id}/bundles/{bundle_code}/deactivate/`

## Design Notes

- File packages are the authoring format.
- Database records are the execution format.
- Only `active` KB versions are used for runtime decisions.
- Test cases travel with the package so rule updates are validated in-context.
- Bundles are the safe feature-toggle layer; individual rules are not meant to be toggled ad hoc by operators.
