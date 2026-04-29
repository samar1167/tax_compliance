"use client";

import { useState } from "react";

import { evaluateAssessment } from "@/lib/api";

const initialForm = {
  residential_status: "resident_ordinary",
  age_on_previous_year_end: 30,
  total_income: 1200000,
  total_income_before_specified_exemptions_and_chapter_via: 1200000,
  house_property_count: 1,
  agricultural_income: 0,
  short_term_capital_gains: 0,
  ltcg_112a_amount: 0,
  other_capital_gains_amount: 0,
  current_account_deposits: 0,
  foreign_travel_expenditure: 0,
  electricity_expenditure: 0,
  aggregate_tds_tcs: 0,
  savings_bank_deposits: 0,
  is_director_in_company: false,
  held_unlisted_equity_shares: false,
  has_foreign_asset: false,
  has_foreign_signing_authority: false,
  has_foreign_source_income: false,
  has_deferred_esop_tax: false,
  tds_under_194n: false,
  brought_forward_loss_exists: false,
  loss_to_carry_forward_exists: false,
};

function toBoolean(value) {
  return value === "true" || value === true;
}

export default function AssessmentForm({ knowledgeBase }) {
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("Ready to evaluate.");

  function updateField(event) {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setStatus("Evaluating taxpayer facts against the knowledge base...");

    try {
      const payload = {
        context: {
          assessment_year: knowledgeBase.assessment_year,
          financial_year: knowledgeBase.financial_year,
          basic_exemption_limit: 300000,
        },
        profile: {
          person_type: "individual",
          residential_status: form.residential_status,
          age_on_previous_year_end: Number(form.age_on_previous_year_end),
          is_director_in_company: toBoolean(form.is_director_in_company),
          held_unlisted_equity_shares: toBoolean(form.held_unlisted_equity_shares),
          has_foreign_asset: toBoolean(form.has_foreign_asset),
          has_foreign_signing_authority: toBoolean(form.has_foreign_signing_authority),
          has_foreign_source_income: toBoolean(form.has_foreign_source_income),
          has_deferred_esop_tax: toBoolean(form.has_deferred_esop_tax),
          tds_under_194n: toBoolean(form.tds_under_194n),
        },
        income: {
          total_income: Number(form.total_income),
          total_income_before_specified_exemptions_and_chapter_via: Number(
            form.total_income_before_specified_exemptions_and_chapter_via
          ),
          house_property_count: Number(form.house_property_count),
          agricultural_income: Number(form.agricultural_income),
          short_term_capital_gains: Number(form.short_term_capital_gains),
          ltcg_112a_amount: Number(form.ltcg_112a_amount),
          other_capital_gains_amount: Number(form.other_capital_gains_amount),
          brought_forward_loss_exists: toBoolean(form.brought_forward_loss_exists),
          loss_to_carry_forward_exists: toBoolean(form.loss_to_carry_forward_exists),
        },
        specified_triggers: {
          current_account_deposits: Number(form.current_account_deposits),
          foreign_travel_expenditure: Number(form.foreign_travel_expenditure),
          electricity_expenditure: Number(form.electricity_expenditure),
          aggregate_tds_tcs: Number(form.aggregate_tds_tcs),
          savings_bank_deposits: Number(form.savings_bank_deposits),
        },
      };

      const response = await evaluateAssessment(payload);
      setResult(response.result);
      setStatus(`Assessment created with id ${response.assessment_id}.`);
    } catch (error) {
      setStatus(error.message);
    }
  }

  function handleReset() {
    setForm(initialForm);
    setResult(null);
    setStatus("Form reset.");
  }

  const flagFields = [
    ["is_director_in_company", "Director in company"],
    ["held_unlisted_equity_shares", "Held unlisted equity shares"],
    ["has_foreign_asset", "Foreign asset"],
    ["has_foreign_signing_authority", "Foreign signing authority"],
    ["has_foreign_source_income", "Foreign source income"],
    ["has_deferred_esop_tax", "Deferred ESOP tax"],
    ["tds_under_194n", "TDS under section 194N"],
    ["brought_forward_loss_exists", "Brought-forward loss"],
    ["loss_to_carry_forward_exists", "Loss to carry forward"],
  ];

  return (
    <div className="grid">
      <section className="panel">
        <h2>Assessment Inputs</h2>
        <p className="empty">
          This MVP evaluates filing obligation and form recommendation using the current seeded rules for{" "}
          {knowledgeBase.assessment_year}.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="residential_status">Residential status</label>
              <select id="residential_status" name="residential_status" value={form.residential_status} onChange={updateField}>
                <option value="resident_ordinary">Resident ordinary</option>
                <option value="resident_not_ordinary">Resident not ordinary</option>
                <option value="non_resident">Non-resident</option>
                <option value="deemed_resident_not_ordinary">Deemed resident not ordinary</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="age_on_previous_year_end">Age on year end</label>
              <input id="age_on_previous_year_end" name="age_on_previous_year_end" type="number" value={form.age_on_previous_year_end} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="total_income">Total income</label>
              <input id="total_income" name="total_income" type="number" value={form.total_income} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="total_income_before_specified_exemptions_and_chapter_via">Pre-deduction income</label>
              <input
                id="total_income_before_specified_exemptions_and_chapter_via"
                name="total_income_before_specified_exemptions_and_chapter_via"
                type="number"
                value={form.total_income_before_specified_exemptions_and_chapter_via}
                onChange={updateField}
              />
            </div>
            <div className="field">
              <label htmlFor="house_property_count">House property count</label>
              <input id="house_property_count" name="house_property_count" type="number" value={form.house_property_count} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="agricultural_income">Agricultural income</label>
              <input id="agricultural_income" name="agricultural_income" type="number" value={form.agricultural_income} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="short_term_capital_gains">Short-term capital gains</label>
              <input id="short_term_capital_gains" name="short_term_capital_gains" type="number" value={form.short_term_capital_gains} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="ltcg_112a_amount">LTCG u/s 112A</label>
              <input id="ltcg_112a_amount" name="ltcg_112a_amount" type="number" value={form.ltcg_112a_amount} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="other_capital_gains_amount">Other capital gains</label>
              <input id="other_capital_gains_amount" name="other_capital_gains_amount" type="number" value={form.other_capital_gains_amount} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="current_account_deposits">Current account deposits</label>
              <input id="current_account_deposits" name="current_account_deposits" type="number" value={form.current_account_deposits} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="foreign_travel_expenditure">Foreign travel expenditure</label>
              <input id="foreign_travel_expenditure" name="foreign_travel_expenditure" type="number" value={form.foreign_travel_expenditure} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="electricity_expenditure">Electricity expenditure</label>
              <input id="electricity_expenditure" name="electricity_expenditure" type="number" value={form.electricity_expenditure} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="aggregate_tds_tcs">Aggregate TDS/TCS</label>
              <input id="aggregate_tds_tcs" name="aggregate_tds_tcs" type="number" value={form.aggregate_tds_tcs} onChange={updateField} />
            </div>
            <div className="field">
              <label htmlFor="savings_bank_deposits">Savings bank deposits</label>
              <input id="savings_bank_deposits" name="savings_bank_deposits" type="number" value={form.savings_bank_deposits} onChange={updateField} />
            </div>
          </div>
          <div className="card-stack" style={{ marginTop: 18 }}>
            {flagFields.map(([key, label]) => (
              <label key={key} className="field" style={{ gridTemplateColumns: "20px 1fr", alignItems: "center" }}>
                <input type="checkbox" name={key} checked={Boolean(form[key])} onChange={updateField} />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <div className="form-actions">
            <button className="button" type="submit">
              Evaluate
            </button>
            <button className="button secondary" type="button" onClick={handleReset}>
              Reset
            </button>
            <span className="status">{status}</span>
          </div>
        </form>
      </section>

      <section className="card-stack">
        <div className="panel">
          <h2 className="result-title">Knowledge Base</h2>
          <span className="tag">{knowledgeBase.assessment_year}</span>
          <span className="tag">{knowledgeBase.rule_count} rules</span>
          <span className="tag">{knowledgeBase.source_count} official sources</span>
          <p className="empty">
            Seeded from a versioned YAML knowledge base so deterministic behavior can evolve through content updates instead of hardcoded logic changes.
          </p>
        </div>

        <div className="panel">
          <h2 className="result-title">Decision</h2>
          {!result ? (
            <p className="empty">Run an assessment to see filing obligation, eligible forms, and the decision trace.</p>
          ) : (
            <>
              <span className="tag">Filing: {result.filing_obligation}</span>
              {result.recommended_form ? <span className="tag">Recommended: {result.recommended_form}</span> : null}
              {result.outside_scope ? <span className="tag">Outside current form scope</span> : null}
              <h3>Reasons</h3>
              <ul className="list">
                {result.filing_obligation_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <h3>ITR-1 ineligibility reasons</h3>
              <ul className="list">
                {result.itr1_ineligibility_reasons.length ? (
                  result.itr1_ineligibility_reasons.map((reason) => <li key={reason}>{reason}</li>)
                ) : (
                  <li>No ineligibility reasons triggered.</li>
                )}
              </ul>
            </>
          )}
        </div>

        <div className="panel">
          <h2 className="result-title">Trace</h2>
          <pre className="code-block">{JSON.stringify(result, null, 2)}</pre>
        </div>
      </section>
    </div>
  );
}
