# Indian Personal Tax Filing Obligation + ITR Selection Engine

This module is the first deterministic compliance layer for Indian personal tax filing.

Scope of this draft:
- Taxpayer type: individual
- Primary target: Indian resident salaried individuals
- Forms covered: `ITR-1`, `ITR-2`
- Filing year baseline: `FY 2025-26 / AY 2026-27`

Important date boundary:
- Returns for income earned in `FY 2025-26` are filed for `AY 2026-27` under the `Income-tax Act, 1961`, even though the filing happens after `1 April 2026`.
- The new `Income Tax Act, 2025` applies prospectively to tax years beginning on or after `1 April 2026`.

## 1. Structured Rule Schema / Ontology

The rules engine should separate:
- `facts`: normalized taxpayer data collected from forms, imports, AIS/TIS, or derived services
- `rules`: declarative eligibility / obligation rules
- `decisions`: evaluated outcomes such as `filing_obligation=true` or `recommended_itr=ITR-2`
- `sources`: official citations that justify each rule

Recommended top-level ontology:

1. `TaxpayerProfile`
- `person_type`: `individual`
- `age_on_previous_year_end`
- `residential_status`: `resident_ordinary`, `resident_not_ordinary`, `non_resident`, `deemed_resident_not_ordinary`
- `is_director_in_company`
- `held_unlisted_equity_shares`
- `has_foreign_asset`
- `has_foreign_signing_authority`
- `has_foreign_source_income`
- `has_deferred_esop_tax`
- `tds_under_194n`

2. `ReturnContext`
- `financial_year`
- `assessment_year`
- `act_version`
- `tax_regime_selected`: `old`, `new`, `unknown`
- `basic_exemption_limit`

3. `IncomeProfile`
- `total_income`
- `total_income_before_specified_exemptions_and_chapter_via`
- `salary_income`
- `pension_income`
- `house_property_count`
- `house_property_income`
- `other_sources_interest_income`
- `other_sources_dividend_income`
- `family_pension_income`
- `lottery_income`
- `race_horse_income`
- `business_turnover`
- `professional_receipts`
- `business_or_profession_income`
- `short_term_capital_gains`
- `ltcg_112a_amount`
- `other_capital_gains_amount`
- `agricultural_income`
- `brought_forward_loss_exists`
- `loss_to_carry_forward_exists`
- `clubbing_income_present`
- `clubbing_income_heads`

4. `SpecifiedFilingTriggerProfile`
- `current_account_deposits`
- `foreign_travel_expenditure`
- `electricity_expenditure`
- `aggregate_tds_tcs`
- `savings_bank_deposits`

5. `Decision`
- `filing_obligation`: `required`, `not_required`, `insufficient_data`
- `filing_obligation_reasons`
- `eligible_forms`
- `ineligible_forms`
- `recommended_form`
- `decision_trace`

6. `Rule`
- `rule_id`
- `module`
- `version`
- `effective_from_ay`
- `effective_to_ay`
- `priority`
- `applies_if`
- `when`
- `effect`
- `explanation_template`
- `source_refs`

## 2. Deterministic Decision Model

Evaluation should happen in this order:

1. `Residency classification`
- Use section 6 logic or a separate upstream service.
- For this module, residency is an input dependency but must be explicit because `ITR-1` requires `resident other than RNOR`.

2. `Filing obligation`
- Determine whether filing is mandatory under section 139(1) and related provisos/rules.

3. `ITR-1 exclusion screen`
- Start from "potentially ITR-1 eligible" and remove eligibility if any exclusion fires.

4. `ITR-2 selection`
- If individual is not eligible for `ITR-1` and does not have `profits and gains of business or profession`, assign `ITR-2`.

5. `Escalation flags`
- If business/profession income exists, emit `outside_current_scope` because likely `ITR-3` / `ITR-4`.

## 3. Filing Obligation Rules

### Core filing obligation

Mandatory if any of these are true:

1. `total_income > basic_exemption_limit`
- Section 139(1) main rule.

2. `total_income_before_specified_exemptions_and_chapter_via > basic_exemption_limit`
- Captures the proviso that requires filing even if deductions / specified exemptions later reduce taxable income below threshold.

3. `resident_ordinary_with_foreign_asset_or_signing_authority_or_beneficiary_trigger`
- Resident other than RNOR with foreign asset / financial interest / signing authority must file.

4. Any seventh proviso trigger:
- `current_account_deposits > 1,00,00,000`
- `foreign_travel_expenditure > 2,00,000`
- `electricity_expenditure > 1,00,000`
- prescribed Rule 12AB conditions:
  - `business_turnover > 60,00,000`
  - `professional_receipts > 10,00,000`
  - `aggregate_tds_tcs >= 25,000`
  - for resident senior citizen age `>= 60`: `aggregate_tds_tcs >= 50,000`
  - `savings_bank_deposits >= 50,00,000`

### Filing obligation output shape

Return a structured result:

```json
{
  "filing_obligation": "required",
  "reasons": [
    {
      "code": "SEVENTH_PROVISO_FOREIGN_TRAVEL",
      "message": "Foreign travel expenditure exceeded Rs. 2,00,000 during the previous year.",
      "source_refs": ["sec139_7th_proviso", "rule12ab_if_applicable"]
    }
  ]
}
```

## 4. ITR Selection Rules

### ITR-1 positive eligibility

`ITR-1` is allowed only if all are true:

1. `person_type = individual`
2. `residential_status = resident_ordinary`
3. `total_income <= 50,00,000`
4. Income heads limited to:
- salary / pension
- one house property
- other sources of allowed kind
- agricultural income `<= 5,000`
- LTCG under `section 112A <= 1,25,000`
5. Clubbed income, if any, also fits the same limits

### ITR-1 exclusion rules

Exclude `ITR-1` if any are true:

1. `residential_status != resident_ordinary`
2. `total_income > 50,00,000`
3. `agricultural_income > 5,000`
4. `house_property_count > 1`
5. `business_or_profession_income > 0`
6. `short_term_capital_gains > 0`
7. `other_capital_gains_amount > 0`
8. `ltcg_112a_amount > 1,25,000`
9. `lottery_income > 0` or `race_horse_income > 0`
10. `is_director_in_company = true`
11. `held_unlisted_equity_shares = true`
12. `has_foreign_asset = true`
13. `has_foreign_signing_authority = true`
14. `has_foreign_source_income = true`
15. `tds_under_194n = true`
16. `has_deferred_esop_tax = true`
17. `brought_forward_loss_exists = true`
18. `loss_to_carry_forward_exists = true`
19. clubbed income outside `ITR-1` limits

### ITR-2 selection

Recommend `ITR-2` when all are true:

1. `person_type = individual`
2. `not eligible for ITR-1`
3. `business_or_profession_income = 0`
4. No partnership-firm remuneration / interest / commission income treated as business-profession category

### Out-of-scope routing

If `business_or_profession_income > 0`, do not force `ITR-2`.
Return:

```json
{
  "recommended_form": null,
  "outside_scope": true,
  "next_expected_forms": ["ITR-3", "ITR-4"]
}
```

## 5. Validation Against Official Guidance

The following rules were validated against official Indian tax sources:

1. `Section 139(1)` and related provisos under the `Income-tax Act, 1961`
- Main filing obligation
- Foreign asset/signing authority filing trigger
- Seventh proviso triggers
- URL:
  - https://incometaxindia.gov.in/Acts/Income-tax%20Act%2C%201961/2025/102120000000091167.htm

2. `Rule 12AB` under the `Income-tax Rules, 1962`
- Additional prescribed filing conditions:
  - business turnover above `Rs. 60 lakh`
  - professional receipts above `Rs. 10 lakh`
  - aggregate TDS/TCS `>= Rs. 25,000`
  - aggregate TDS/TCS `>= Rs. 50,000` for resident seniors aged `60+`
  - savings bank deposits `>= Rs. 50 lakh`
- URL:
  - https://incometaxindia.gov.in/Rules/Income-Tax%20Rules/103520000000090150.htm
  - CBDT notification introducing Rule 12AB:
    https://incometaxindia.gov.in/communications/notification/notification-37-2022.pdf

3. `ITR-1` official user manual / help
- Resident individual only
- Income cap `Rs. 50 lakh`
- allowed income classes
- exclusion conditions such as RNOR/NRI, capital gains, business income, foreign assets, director, unlisted shares, 194N, deferred ESOP, multiple house properties
- URL:
  - https://www.incometax.gov.in/iec/foportal/node/11455
  - https://www.incometax.gov.in/iec/foportal/help/how-to-file-itr1-form-sahaj

4. `Salaried Individuals for AY 2026-27`
- Current portal guidance confirming `ITR-1` and `ITR-2` applicability for `AY 2026-27`
- URL:
  - https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1

5. `ITR-2` official help
- `ITR-2` for individuals/HUFs not eligible for `ITR-1` and without business/profession income
- URL:
  - https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-2

6. `Income Tax Returns FAQs`
- Confirms that `AY 2026-27` filings for `FY 2025-26` continue under the `Income-tax Act, 1961`
- URL:
  - https://www.incometax.gov.in/iec/foportal/node/11724

### Validation notes and implementation cautions

1. `ITR-1` instructions and the salaried guidance page are not identical in phrasing.
- For example, the current `AY 2026-27` salaried page explicitly allows `LTCG u/s 112A up to Rs. 1,25,000` inside `ITR-1`.
- The older help manual also lists broad capital-gain exclusions.
- Engine design should therefore use `assessment-year versioned rules` and preserve source lineage per rule.

2. `Residential status` is decisive for form selection.
- `ITR-1` is only for `resident other than not ordinarily resident`.
- `RNOR` and `non-resident` individuals should generally be routed away from `ITR-1`.

3. `Tax regime` and `basic exemption limit` should not be hardcoded in this module forever.
- They should come from a separate, versioned tax-threshold service because slabs and rebates may change by assessment year.

## 6. Suggested System Design

### Recommended services

1. `Profile Normalizer`
- Converts UI/API payloads into normalized facts.

2. `Residency Classifier`
- Computes section 6 status or accepts a verified upstream result.

3. `Filing Obligation Engine`
- Pure deterministic rules.
- Outputs `required/not_required/insufficient_data` plus reasons.

4. `ITR Eligibility Engine`
- Computes `eligible_forms`, `ineligible_forms`, `recommended_form`, and exclusion reasons.

5. `Citation Resolver`
- Attaches official legal/help references to each decision.

6. `Explanation Layer`
- Uses AI only after deterministic decision is complete.
- AI explains why `ITR-1` failed or why filing is mandatory, but never decides thresholds.

### Recommended data model

Keep a versioned knowledge base:

```text
knowledge_base/
  tax_rules/
    schema.rule.yaml
    seed.filing_obligation_itr_selection.ay2026_27.yaml
```

Each decision should be reproducible:
- input facts snapshot
- rule version
- fired rule ids
- citations
- final decision

### Evaluation pattern

1. Validate required fields
2. Derive computed facts
3. Evaluate filing-obligation rules
4. Evaluate `ITR-1` eligibility rules
5. Evaluate `ITR-2` fallback rules
6. Emit structured trace
7. Ask AI to generate human explanation from the trace

### Example API contract

```json
{
  "assessment_year": "2026-27",
  "facts": {
    "person_type": "individual",
    "residential_status": "resident_ordinary",
    "total_income": 1800000,
    "salary_income": 1750000,
    "house_property_count": 1,
    "agricultural_income": 0,
    "short_term_capital_gains": 0,
    "ltcg_112a_amount": 75000,
    "business_or_profession_income": 0,
    "has_foreign_asset": false,
    "has_foreign_signing_authority": false,
    "has_foreign_source_income": false,
    "is_director_in_company": false,
    "held_unlisted_equity_shares": false,
    "tds_under_194n": false,
    "has_deferred_esop_tax": false,
    "brought_forward_loss_exists": false,
    "loss_to_carry_forward_exists": false
  }
}
```

Expected deterministic output:

```json
{
  "filing_obligation": "required",
  "filing_obligation_reasons": [
    "TOTAL_INCOME_ABOVE_BASIC_EXEMPTION"
  ],
  "eligible_forms": ["ITR-1", "ITR-2"],
  "recommended_form": "ITR-1",
  "decision_trace": [
    "OBL_001",
    "ITR1_ELIG_001",
    "ITR2_ELIG_001"
  ]
}
```

## 7. MVP Recommendation

For the first implementation, build only these deterministic outcomes:

1. `filing_required`
2. `why_filing_required`
3. `itr1_eligible`
4. `itr1_ineligibility_reasons`
5. `recommended_form`
6. `source_citations`

This is enough to support:
- onboarding questionnaire
- tax filing readiness check
- form recommendation
- compliance explanation UI
- future extension into deduction, TDS mismatch, and return validation modules
