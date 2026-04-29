"use client";

import { useEffect, useMemo, useState } from "react";

import {
  createTaxUserSession,
  evaluateAssessment,
  fetchHealth,
  fetchKnowledgeBaseSummary,
  fetchReturnSourceSession,
  fetchReturnSourceTestRecords,
  fetchReturnSourceTypes,
  prepareValidation,
  saveReturnSourceRecord,
} from "../lib/api";
import { formatCurrency, titleCase } from "../lib/formatters";

const STEP_TITLES = [
  "Create Tax User",
  "Capture Source Data",
  "Declared Data",
  "Recommended ITR",
  "Final Validation",
];

const DEFAULT_USER = {
  taxpayer_name: "",
  taxpayer_pan: "",
  return_type: "ITR-1",
  assessment_year: "2026-27",
  financial_year: "2025-26",
};

const DEFAULT_DECLARED_DATA = {
  profile: {
    person_type: "individual",
    residential_status: "resident_ordinary",
    age_on_previous_year_end: 30,
    has_foreign_asset: false,
    has_foreign_signing_authority: false,
    has_foreign_source_income: false,
    is_director_in_company: false,
    held_unlisted_equity_shares: false,
    has_deferred_esop_tax: false,
    tds_under_194n: false,
    is_beneficiary_of_foreign_asset: false,
  },
  income: {
    salary_income: 0,
    total_income: 0,
    total_income_before_specified_exemptions_and_chapter_via: 0,
    house_property_count: 1,
    agricultural_income: 0,
    short_term_capital_gains: 0,
    ltcg_112a_amount: 0,
    other_capital_gains_amount: 0,
    business_or_profession_income: 0,
    business_turnover: 0,
    professional_receipts: 0,
    brought_forward_loss_exists: false,
    loss_to_carry_forward_exists: false,
    partnership_firm_interest_salary_bonus_commission: 0,
  },
  specified_triggers: {
    aggregate_tds_tcs: 0,
    current_account_deposits: 0,
    foreign_travel_expenditure: 0,
    electricity_expenditure: 0,
    savings_bank_deposits: 0,
  },
};

function serializeDocuments(session) {
  if (!session?.source_types) {
    return [];
  }

  return session.source_types
    .filter((sourceType) => sourceType.captured && sourceType.captured_record)
    .map((sourceType) => ({
      document_type: sourceType.source_type,
      data: sourceType.captured_record.source_data,
    }));
}

function toBoolean(value) {
  return value === true || value === "true";
}

function parseNumber(value) {
  if (value === "" || value === null || value === undefined) {
    return 0;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function sourceDataTemplate(definition, taxUser) {
  const template = {};
  definition.capture_fields.forEach((field) => {
    if (field === "pan") {
      template[field] = taxUser.taxpayer_pan || "";
    } else if (field === "name") {
      template[field] = taxUser.taxpayer_name || "";
    } else if (field === "residential_status") {
      template[field] = "resident_ordinary";
    } else {
      template[field] = "";
    }
  });
  return template;
}

function sourceValidationErrors(error) {
  if (!error?.details) {
    return [];
  }
  return error.details.map((detail, index) => ({
    id: `${detail.field || "error"}-${index}`,
    message: detail.message || "Unable to save source data.",
  }));
}

function getNestedValue(object, path) {
  return path.split(".").reduce((current, part) => {
    if (!current || typeof current !== "object") {
      return undefined;
    }
    return current[part];
  }, object);
}

function setNestedValue(object, path, value) {
  const parts = path.split(".");
  const nextObject = { ...object };
  let current = nextObject;

  parts.forEach((part, index) => {
    if (index === parts.length - 1) {
      current[part] = value;
      return;
    }

    current[part] = current[part] && typeof current[part] === "object" ? { ...current[part] } : {};
    current = current[part];
  });

  return nextObject;
}

function isBooleanPath(path) {
  const field = path.split(".").pop() || "";
  return (
    field.startsWith("has_") ||
    field.startsWith("is_") ||
    field.startsWith("held_") ||
    field.endsWith("_exists") ||
    field.includes("_under_")
  );
}

function isNumericPath(path) {
  return !isBooleanPath(path) && !path.endsWith("residential_status") && !path.endsWith("person_type");
}

function missingInputsFromError(error) {
  const validationErrors = error?.payload?.result?.validation_errors;
  if (!Array.isArray(validationErrors)) {
    return [];
  }

  return validationErrors
    .filter((item) => item?.code === "MISSING_REQUIRED_INPUT" && item?.path)
    .map((item) => item.path);
}

function validationErrorsFromError(error) {
  const validationErrors = error?.payload?.result?.validation_errors;
  return Array.isArray(validationErrors) ? validationErrors : [];
}

export default function WorkflowApp() {
  const [health, setHealth] = useState(null);
  const [knowledgeBase, setKnowledgeBase] = useState(null);
  const [initialError, setInitialError] = useState("");
  const [loadingBootstrap, setLoadingBootstrap] = useState(true);

  const [step, setStep] = useState(0);
  const [taxUser, setTaxUser] = useState(DEFAULT_USER);
  const [session, setSession] = useState(null);
  const [sourceTypes, setSourceTypes] = useState([]);
  const [savingUser, setSavingUser] = useState(false);
  const [userError, setUserError] = useState("");
  const [resumeSessionId, setResumeSessionId] = useState("");
  const [resumeState, setResumeState] = useState("idle");
  const [resumeError, setResumeError] = useState("");

  const [selectedSourceType, setSelectedSourceType] = useState("");
  const [sourceMode, setSourceMode] = useState("manual");
  const [sourceDraft, setSourceDraft] = useState({});
  const [testRecords, setTestRecords] = useState([]);
  const [selectedTestRecordId, setSelectedTestRecordId] = useState("");
  const [sourceLoadState, setSourceLoadState] = useState("idle");
  const [sourceSubmitState, setSourceSubmitState] = useState("idle");
  const [sourceError, setSourceError] = useState("");
  const [sourceFieldErrors, setSourceFieldErrors] = useState([]);

  const [declaredData, setDeclaredData] = useState(DEFAULT_DECLARED_DATA);
  const [assessmentState, setAssessmentState] = useState("idle");
  const [assessmentError, setAssessmentError] = useState("");
  const [assessmentMissingInputs, setAssessmentMissingInputs] = useState([]);
  const [assessmentValidationErrors, setAssessmentValidationErrors] = useState([]);
  const [assessmentResult, setAssessmentResult] = useState(null);

  const [finalState, setFinalState] = useState("idle");
  const [finalError, setFinalError] = useState("");
  const [finalResult, setFinalResult] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoadingBootstrap(true);
      setInitialError("");
      try {
        const [healthResponse, kbResponse] = await Promise.all([
          fetchHealth(),
          fetchKnowledgeBaseSummary(),
        ]);
        if (!cancelled) {
          setHealth(healthResponse);
          setKnowledgeBase(kbResponse);
        }
      } catch (error) {
        if (!cancelled) {
          setInitialError(error.message || "Unable to reach backend.");
        }
      } finally {
        if (!cancelled) {
          setLoadingBootstrap(false);
        }
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedSourceDefinition = useMemo(
    () => sourceTypes.find((item) => item.source_type === selectedSourceType) || null,
    [selectedSourceType, sourceTypes]
  );

  useEffect(() => {
    if (!selectedSourceDefinition) {
      setSourceDraft({});
      setSelectedTestRecordId("");
      setTestRecords([]);
      return;
    }

    setSourceDraft(sourceDataTemplate(selectedSourceDefinition, taxUser));
    setSelectedTestRecordId("");
    setSourceError("");
    setSourceFieldErrors([]);

    let cancelled = false;

    async function loadTestRecords() {
      setSourceLoadState("loading");
      try {
        const response = await fetchReturnSourceTestRecords(
          taxUser.return_type,
          selectedSourceDefinition.source_type
        );
        if (!cancelled) {
          setTestRecords(response.test_records || []);
          setSourceLoadState("ready");
        }
      } catch (error) {
        if (!cancelled) {
          setTestRecords([]);
          setSourceLoadState("error");
          setSourceError(error.message || "Unable to load test records.");
        }
      }
    }

    loadTestRecords();
    return () => {
      cancelled = true;
    };
  }, [selectedSourceDefinition, taxUser]);

  function handleUserChange(event) {
    const { name, value } = event.target;
    setTaxUser((current) => ({
      ...current,
      [name]: name === "taxpayer_pan" ? value.toUpperCase() : value,
    }));
  }

  async function handleCreateUser(event) {
    event.preventDefault();
    setSavingUser(true);
    setUserError("");

    try {
      const response = await createTaxUserSession(taxUser);
      setSession(response.session);
      const sourceTypeResponse = await fetchReturnSourceTypes(taxUser.return_type);
      setSourceTypes(sourceTypeResponse.source_types || []);
      setSelectedSourceType(sourceTypeResponse.source_types?.[0]?.source_type || "");
      setStep(1);
    } catch (error) {
      setUserError(error.message || "Unable to create tax user.");
    } finally {
      setSavingUser(false);
    }
  }

  async function loadExistingSession(sessionId) {
    const response = await fetchReturnSourceSession(sessionId);
    const loadedSession = response.session;
    const sourceTypeResponse = await fetchReturnSourceTypes(loadedSession.return_type);

    setSession(loadedSession);
    setSourceTypes(sourceTypeResponse.source_types || []);
    setSelectedSourceType(loadedSession.source_types?.[0]?.source_type || sourceTypeResponse.source_types?.[0]?.source_type || "");
    setTaxUser({
      taxpayer_name: loadedSession.taxpayer_name || "",
      taxpayer_pan: loadedSession.taxpayer_pan || "",
      return_type: loadedSession.return_type,
      assessment_year: loadedSession.assessment_year || "2026-27",
      financial_year: loadedSession.financial_year || "2025-26",
    });
    setStep(1);
  }

  async function handleResumeSession(event) {
    event.preventDefault();
    setResumeState("loading");
    setResumeError("");

    try {
      await loadExistingSession(resumeSessionId);
      setResumeState("ready");
    } catch (error) {
      setResumeState("error");
      setResumeError(error.message || "Unable to load previous session.");
    }
  }

  function handleSourceDraftChange(field, value) {
    setSourceDraft((current) => ({ ...current, [field]: value }));
  }

  async function refreshSessionState(sessionId) {
    await loadExistingSession(sessionId);
  }

  async function handleSaveSource(event) {
    event.preventDefault();
    if (!session || !selectedSourceDefinition) {
      return;
    }

    setSourceSubmitState("saving");
    setSourceError("");
    setSourceFieldErrors([]);

    try {
      const payload =
        sourceMode === "test_record"
          ? {
              source_type: selectedSourceDefinition.source_type,
              test_record_id: selectedTestRecordId,
            }
          : {
              source_type: selectedSourceDefinition.source_type,
              source_data: Object.fromEntries(
                Object.entries(sourceDraft).map(([key, value]) => [key, key.includes("has_") ? toBoolean(value) : value])
              ),
            };

      const response = await saveReturnSourceRecord(session.id, payload);
      setSession(response.session);
      setSourceSubmitState("saved");
    } catch (error) {
      setSourceSubmitState("error");
      setSourceError(error.message || "Unable to save source.");
      setSourceFieldErrors(sourceValidationErrors(error));
    }
  }

  function handleDeclaredNumberChange(section, field, value) {
    setDeclaredData((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [field]: parseNumber(value),
      },
    }));
  }

  function handleDeclaredBooleanChange(section, field, value) {
    setDeclaredData((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [field]: value === "true",
      },
    }));
  }

  function handleDeclaredTextChange(section, field, value) {
    setDeclaredData((current) => ({
      ...current,
      [section]: {
        ...current[section],
        [field]: value,
      },
    }));
  }

  async function handleEvaluateAssessment() {
    setAssessmentState("loading");
    setAssessmentError("");
    setAssessmentMissingInputs([]);
    setAssessmentValidationErrors([]);

    try {
      const payload = {
        context: {
          assessment_year: taxUser.assessment_year,
          financial_year: taxUser.financial_year,
          basic_exemption_limit: 300000,
        },
        ...declaredData,
      };
      const response = await evaluateAssessment(payload);
      setAssessmentResult(response);
      setAssessmentState("ready");
      setStep(3);
    } catch (error) {
      setAssessmentResult(null);
      setAssessmentState("error");
      setAssessmentError(error.message || "Unable to get recommended ITR.");
      setAssessmentMissingInputs(missingInputsFromError(error));
      setAssessmentValidationErrors(validationErrorsFromError(error));
    }
  }

  function handleDynamicMissingInputChange(path, value) {
    setDeclaredData((current) =>
      setNestedValue(
        current,
        path,
        isBooleanPath(path) ? value === "true" : isNumericPath(path) ? parseNumber(value) : value
      )
    );
  }

  async function handlePrepareValidation() {
    setFinalState("loading");
    setFinalError("");

    try {
      const payload = {
        return_type: taxUser.return_type,
        context: {
          assessment_year: taxUser.assessment_year,
          financial_year: taxUser.financial_year,
        },
        declared_data: declaredData,
        documents: serializeDocuments(session),
      };
      const response = await prepareValidation(payload);
      setFinalResult(response);
      setFinalState("ready");
      setStep(4);
    } catch (error) {
      setFinalResult(null);
      setFinalState("error");
      setFinalError(error.message || "Unable to prepare final validation.");
    }
  }

  const completionStats = useMemo(() => {
    if (!session?.source_types?.length) {
      return { captured: 0, total: 0 };
    }
    return {
      captured: session.source_types.filter((item) => item.captured).length,
      total: session.source_types.length,
    };
  }, [session]);

  const canProceedToDeclaredData =
    session?.status === "ready" && completionStats.captured >= 1;

  return (
    <main className="shell">
      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">Tax Compliance Control Room</p>
          <h1>Tax Compliance System POC</h1>
          <p className="hero__lede">
            Guide a case from taxpayer creation through document-backed validation with strong visibility into missing fields, mismatches, and the backend’s recommendation trace.
          </p>
        </div>
        <div className="hero__panel">
          <StatusPill label="Backend" value={health?.status || (loadingBootstrap ? "checking" : "offline")} />
          <StatusPill label="KB Version" value={knowledgeBase?.version || "n/a"} />
          <StatusPill label="Assessment Year" value={knowledgeBase?.assessment_year || taxUser.assessment_year} />
          <StatusPill label="Workflow Step" value={`${step + 1}/${STEP_TITLES.length}`} />
        </div>
      </section>

      {initialError ? <Banner tone="error" message={initialError} /> : null}

      <section className="board">
        <aside className="timeline">
          {STEP_TITLES.map((title, index) => (
            <button
              key={title}
              className={`timeline__item ${index === step ? "is-active" : ""} ${index < step ? "is-complete" : ""}`}
              onClick={() => setStep(index)}
              type="button"
            >
              <span className="timeline__index">0{index + 1}</span>
              <span>{title}</span>
            </button>
          ))}
        </aside>

        <section className="workspace">
          <div className="workspace__header">
            <div>
              <p className="workspace__eyebrow">Current step</p>
              <h2>{STEP_TITLES[step]}</h2>
            </div>
            {session ? (
              <div className="workspace__meta">
                <span>Session #{session.id}</span>
                <span>{session.return_type}</span>
                <span>{session.status}</span>
              </div>
            ) : null}
          </div>

          {step === 0 ? (
            <div className="grid-two">
              <form className="panel grid-form" onSubmit={handleCreateUser}>
                <div className="panel__intro">
                  <h3>Create a new tax user</h3>
                  <p>Start by creating a source-capture session tied to a taxpayer, return type, and filing period.</p>
                </div>

                <label>
                  Taxpayer name
                  <input
                    name="taxpayer_name"
                    onChange={handleUserChange}
                    placeholder="Aarav Sharma"
                    value={taxUser.taxpayer_name}
                  />
                </label>

                <label>
                  PAN
                  <input
                    name="taxpayer_pan"
                    onChange={handleUserChange}
                    placeholder="ABCDE1234F"
                    value={taxUser.taxpayer_pan}
                  />
                </label>

                <label>
                  Return type
                  <select name="return_type" onChange={handleUserChange} value={taxUser.return_type}>
                    <option value="ITR-1">ITR-1</option>
                    <option value="ITR-2">ITR-2</option>
                  </select>
                </label>

                <label>
                  Assessment year
                  <input
                    name="assessment_year"
                    onChange={handleUserChange}
                    value={taxUser.assessment_year}
                  />
                </label>

                <label>
                  Financial year
                  <input
                    name="financial_year"
                    onChange={handleUserChange}
                    value={taxUser.financial_year}
                  />
                </label>

                {userError ? <Banner tone="error" message={userError} /> : null}

                <div className="actions">
                  <button className="button button--primary" disabled={savingUser} type="submit">
                    {savingUser ? "Creating session..." : "Create tax user"}
                  </button>
                </div>
              </form>

              <form className="panel grid-form" onSubmit={handleResumeSession}>
                <div className="panel__intro">
                  <h3>Load previous session</h3>
                  <p>Resume an existing source-capture session by session ID and continue the workflow from its saved state.</p>
                </div>

                <label>
                  Session ID
                  <input
                    onChange={(event) => setResumeSessionId(event.target.value)}
                    placeholder="12"
                    type="number"
                    value={resumeSessionId}
                  />
                </label>

                {resumeError ? <Banner tone="error" message={resumeError} /> : null}

                <div className="actions">
                  <button
                    className="button button--primary"
                    disabled={resumeState === "loading" || !resumeSessionId}
                    type="submit"
                  >
                    {resumeState === "loading" ? "Loading..." : "Load session"}
                  </button>
                </div>
              </form>
            </div>
          ) : null}

          {step === 1 ? (
            <div className="grid-two">
              <section className="panel">
                <div className="panel__intro">
                  <h3>Add required source data</h3>
                  <p>Capture mandatory evidence with either manual entry or curated test records. Validation issues surface immediately.</p>
                </div>

                <div className="source-picker">
                  <label>
                    Source type
                    <select
                      onChange={(event) => setSelectedSourceType(event.target.value)}
                      value={selectedSourceType}
                    >
                      {sourceTypes.map((sourceType) => (
                        <option key={sourceType.source_type} value={sourceType.source_type}>
                          {sourceType.label} {sourceType.mandatory ? "(required)" : "(optional)"}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="toggle-group">
                    <button
                      className={sourceMode === "manual" ? "is-selected" : ""}
                      onClick={() => setSourceMode("manual")}
                      type="button"
                    >
                      Manual entry
                    </button>
                    <button
                      className={sourceMode === "test_record" ? "is-selected" : ""}
                      onClick={() => setSourceMode("test_record")}
                      type="button"
                    >
                      Test record
                    </button>
                  </div>
                </div>

                {selectedSourceDefinition ? (
                  <form className="source-form" onSubmit={handleSaveSource}>
                    <div className="panel__note">
                      <strong>{selectedSourceDefinition.label}</strong>
                      <p>{selectedSourceDefinition.description}</p>
                    </div>

                    {sourceMode === "test_record" ? (
                      <label>
                        Test record
                        <select
                          onChange={(event) => setSelectedTestRecordId(event.target.value)}
                          value={selectedTestRecordId}
                        >
                          <option value="">Select a seeded record</option>
                          {testRecords.map((record) => (
                            <option key={record.test_record_id} value={record.test_record_id}>
                              {record.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : (
                      <div className="field-grid">
                        {selectedSourceDefinition.capture_fields.map((field) => (
                          <label key={field}>
                            {titleCase(field)}
                            <input
                              onChange={(event) => handleSourceDraftChange(field, event.target.value)}
                              value={sourceDraft[field] ?? ""}
                            />
                          </label>
                        ))}
                      </div>
                    )}

                    {sourceLoadState === "loading" ? (
                      <p className="subtle">Loading test records...</p>
                    ) : null}
                    {sourceError ? <Banner tone="error" message={sourceError} /> : null}
                    {sourceFieldErrors.length ? (
                      <div className="error-list">
                        {sourceFieldErrors.map((item) => (
                          <p key={item.id}>{item.message}</p>
                        ))}
                      </div>
                    ) : null}

                    <div className="actions">
                      <button
                        className="button button--primary"
                        disabled={sourceSubmitState === "saving" || (sourceMode === "test_record" && !selectedTestRecordId)}
                        type="submit"
                      >
                        {sourceSubmitState === "saving" ? "Saving..." : "Save source"}
                      </button>
                      <button
                        className="button"
                        onClick={() => refreshSessionState(session.id)}
                        type="button"
                      >
                        Refresh session
                      </button>
                      <button
                        className="button"
                        disabled={!canProceedToDeclaredData}
                        onClick={() => setStep(2)}
                        type="button"
                      >
                        Continue to declared data
                      </button>
                    </div>
                  </form>
                ) : null}
              </section>

              <section className="panel">
                <div className="panel__intro">
                  <h3>Capture progress</h3>
                  <p>{completionStats.captured} of {completionStats.total} source types captured.</p>
                </div>

                <div className="status-card">
                  <span className={`badge badge--${session?.status || "draft"}`}>{session?.status || "draft"}</span>
                  <p>
                    Mandatory pending:{" "}
                    {session?.mandatory_source_types_pending?.length
                      ? session.mandatory_source_types_pending.join(", ")
                      : "none"}
                  </p>
                </div>

                <div className="source-list">
                  {session?.source_types?.map((sourceType) => (
                    <article className="source-row" key={sourceType.source_type}>
                      <div>
                        <h4>{sourceType.label}</h4>
                        <p>{sourceType.description}</p>
                      </div>
                      <div className="source-row__meta">
                        <span className={`badge ${sourceType.captured ? "badge--ready" : "badge--pending"}`}>
                          {sourceType.captured ? "Captured" : "Pending"}
                        </span>
                        {sourceType.captured_record ? (
                          <small>{sourceType.captured_record.input_mode.replace("_", " ")}</small>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="grid-two">
              <section className="panel">
                <div className="panel__intro">
                  <h3>Collect declared data</h3>
                  <p>Capture the taxpayer’s declared facts that feed the ITR recommendation engine before document reconciliation.</p>
                </div>

                <div className="field-group">
                  <h4>Profile</h4>
                  <label>
                    Person type
                    <select
                      onChange={(event) => handleDeclaredTextChange("profile", "person_type", event.target.value)}
                      value={declaredData.profile.person_type}
                    >
                      <option value="individual">Individual</option>
                    </select>
                  </label>
                  <label>
                    Residential status
                    <select
                      onChange={(event) => handleDeclaredTextChange("profile", "residential_status", event.target.value)}
                      value={declaredData.profile.residential_status}
                    >
                      <option value="resident_ordinary">Resident ordinary</option>
                      <option value="resident_not_ordinary">Resident not ordinary</option>
                      <option value="non_resident">Non-resident</option>
                    </select>
                  </label>
                  <label>
                    Age on previous year end
                    <input
                      onChange={(event) => handleDeclaredNumberChange("profile", "age_on_previous_year_end", event.target.value)}
                      type="number"
                      value={declaredData.profile.age_on_previous_year_end}
                    />
                  </label>
                  <BooleanField
                    label="Has foreign asset"
                    onChange={(value) => handleDeclaredBooleanChange("profile", "has_foreign_asset", value)}
                    value={declaredData.profile.has_foreign_asset}
                  />
                  <BooleanField
                    label="Has foreign signing authority"
                    onChange={(value) => handleDeclaredBooleanChange("profile", "has_foreign_signing_authority", value)}
                    value={declaredData.profile.has_foreign_signing_authority}
                  />
                  <BooleanField
                    label="Has foreign source income"
                    onChange={(value) => handleDeclaredBooleanChange("profile", "has_foreign_source_income", value)}
                    value={declaredData.profile.has_foreign_source_income}
                  />
                  <BooleanField
                    label="Director in company"
                    onChange={(value) => handleDeclaredBooleanChange("profile", "is_director_in_company", value)}
                    value={declaredData.profile.is_director_in_company}
                  />
                  <BooleanField
                    label="Held unlisted equity shares"
                    onChange={(value) => handleDeclaredBooleanChange("profile", "held_unlisted_equity_shares", value)}
                    value={declaredData.profile.held_unlisted_equity_shares}
                  />
                  <BooleanField
                    label="Deferred ESOP tax"
                    onChange={(value) => handleDeclaredBooleanChange("profile", "has_deferred_esop_tax", value)}
                    value={declaredData.profile.has_deferred_esop_tax}
                  />
                  <BooleanField
                    label="TDS under 194N"
                    onChange={(value) => handleDeclaredBooleanChange("profile", "tds_under_194n", value)}
                    value={declaredData.profile.tds_under_194n}
                  />
                  <BooleanField
                    label="Beneficiary of foreign asset"
                    onChange={(value) =>
                      handleDeclaredBooleanChange("profile", "is_beneficiary_of_foreign_asset", value)
                    }
                    value={declaredData.profile.is_beneficiary_of_foreign_asset}
                  />
                </div>

                <div className="field-group">
                  <h4>Income</h4>
                  <NumberField
                    label="Salary income"
                    onChange={(value) => handleDeclaredNumberChange("income", "salary_income", value)}
                    value={declaredData.income.salary_income}
                  />
                  <NumberField
                    label="Total income"
                    onChange={(value) => handleDeclaredNumberChange("income", "total_income", value)}
                    value={declaredData.income.total_income}
                  />
                  <NumberField
                    label="Total income before deductions/exemptions"
                    onChange={(value) =>
                      handleDeclaredNumberChange(
                        "income",
                        "total_income_before_specified_exemptions_and_chapter_via",
                        value
                      )
                    }
                    value={declaredData.income.total_income_before_specified_exemptions_and_chapter_via}
                  />
                  <NumberField
                    label="House property count"
                    onChange={(value) => handleDeclaredNumberChange("income", "house_property_count", value)}
                    value={declaredData.income.house_property_count}
                  />
                  <NumberField
                    label="Agricultural income"
                    onChange={(value) => handleDeclaredNumberChange("income", "agricultural_income", value)}
                    value={declaredData.income.agricultural_income}
                  />
                  <NumberField
                    label="Short-term capital gains"
                    onChange={(value) => handleDeclaredNumberChange("income", "short_term_capital_gains", value)}
                    value={declaredData.income.short_term_capital_gains}
                  />
                  <NumberField
                    label="LTCG 112A"
                    onChange={(value) => handleDeclaredNumberChange("income", "ltcg_112a_amount", value)}
                    value={declaredData.income.ltcg_112a_amount}
                  />
                  <NumberField
                    label="Other capital gains"
                    onChange={(value) => handleDeclaredNumberChange("income", "other_capital_gains_amount", value)}
                    value={declaredData.income.other_capital_gains_amount}
                  />
                  <NumberField
                    label="Business/profession income"
                    onChange={(value) => handleDeclaredNumberChange("income", "business_or_profession_income", value)}
                    value={declaredData.income.business_or_profession_income}
                  />
                  <NumberField
                    label="Business turnover"
                    onChange={(value) => handleDeclaredNumberChange("income", "business_turnover", value)}
                    value={declaredData.income.business_turnover}
                  />
                  <NumberField
                    label="Professional receipts"
                    onChange={(value) => handleDeclaredNumberChange("income", "professional_receipts", value)}
                    value={declaredData.income.professional_receipts}
                  />
                  <BooleanField
                    label="Brought forward loss exists"
                    onChange={(value) => handleDeclaredBooleanChange("income", "brought_forward_loss_exists", value)}
                    value={declaredData.income.brought_forward_loss_exists}
                  />
                  <BooleanField
                    label="Loss to carry forward exists"
                    onChange={(value) => handleDeclaredBooleanChange("income", "loss_to_carry_forward_exists", value)}
                    value={declaredData.income.loss_to_carry_forward_exists}
                  />
                  <NumberField
                    label="Partnership firm interest/salary/bonus/commission"
                    onChange={(value) =>
                      handleDeclaredNumberChange(
                        "income",
                        "partnership_firm_interest_salary_bonus_commission",
                        value
                      )
                    }
                    value={declaredData.income.partnership_firm_interest_salary_bonus_commission}
                  />
                </div>

                <div className="field-group">
                  <h4>Specified triggers</h4>
                  <NumberField
                    label="Aggregate TDS/TCS"
                    onChange={(value) => handleDeclaredNumberChange("specified_triggers", "aggregate_tds_tcs", value)}
                    value={declaredData.specified_triggers.aggregate_tds_tcs}
                  />
                  <NumberField
                    label="Current account deposits"
                    onChange={(value) => handleDeclaredNumberChange("specified_triggers", "current_account_deposits", value)}
                    value={declaredData.specified_triggers.current_account_deposits}
                  />
                  <NumberField
                    label="Foreign travel expenditure"
                    onChange={(value) =>
                      handleDeclaredNumberChange("specified_triggers", "foreign_travel_expenditure", value)
                    }
                    value={declaredData.specified_triggers.foreign_travel_expenditure}
                  />
                  <NumberField
                    label="Electricity expenditure"
                    onChange={(value) => handleDeclaredNumberChange("specified_triggers", "electricity_expenditure", value)}
                    value={declaredData.specified_triggers.electricity_expenditure}
                  />
                  <NumberField
                    label="Savings bank deposits"
                    onChange={(value) => handleDeclaredNumberChange("specified_triggers", "savings_bank_deposits", value)}
                    value={declaredData.specified_triggers.savings_bank_deposits}
                  />
                </div>

                <div className="actions">
                  <button className="button button--primary" onClick={handleEvaluateAssessment} type="button">
                    {assessmentState === "loading" ? "Evaluating..." : "Get recommended ITR"}
                  </button>
                </div>
                {assessmentError ? <Banner tone="error" message={assessmentError} /> : null}
                {assessmentValidationErrors.length ? (
                  <div className="error-list">
                    {assessmentValidationErrors.map((item, index) => (
                      <p key={`${item.path || item.code}-${index}`}>
                        <strong>{item.path || item.code}:</strong> {item.message}
                      </p>
                    ))}
                  </div>
                ) : null}
                {assessmentMissingInputs.length ? (
                  <div className="panel__note">
                    <strong>Missing backend-required inputs</strong>
                    <p>Fill these fields and try the recommendation again.</p>
                    <div className="field-grid">
                      {assessmentMissingInputs.map((path) => {
                        const value = getNestedValue(declaredData, path);

                        if (isBooleanPath(path)) {
                          return (
                            <label key={path}>
                              {titleCase(path)}
                              <select
                                onChange={(event) => handleDynamicMissingInputChange(path, event.target.value)}
                                value={String(Boolean(value))}
                              >
                                <option value="false">No</option>
                                <option value="true">Yes</option>
                              </select>
                            </label>
                          );
                        }

                        return (
                          <label key={path}>
                            {titleCase(path)}
                            <input
                              onChange={(event) => handleDynamicMissingInputChange(path, event.target.value)}
                              type={isNumericPath(path) ? "number" : "text"}
                              value={value ?? (isNumericPath(path) ? 0 : "")}
                            />
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </section>

              <section className="panel">
                <div className="panel__intro">
                  <h3>Backend inputs preview</h3>
                  <p>These declared facts will be sent to the assessment engine as the pre-validation recommendation payload.</p>
                </div>
                <pre className="code-block">{JSON.stringify(declaredData, null, 2)}</pre>
              </section>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="grid-two">
              <section className="panel">
                <div className="panel__intro">
                  <h3>Recommended ITR</h3>
                  <p>The backend has evaluated the declared facts. Review the recommendation before reconciling with source documents.</p>
                </div>

                {assessmentResult?.result ? (
                  <>
                    <div className="recommendation">
                      <span className="recommendation__form">
                        {assessmentResult.result.recommended_form || "No form yet"}
                      </span>
                      <div>
                        <p>Filing obligation: {assessmentResult.result.filing_obligation}</p>
                        <p>Eligible forms: {assessmentResult.result.eligible_forms.join(", ") || "none"}</p>
                      </div>
                    </div>

                    <div className="fact-strip">
                      <FactCard label="Assessment ID" value={assessmentResult.assessment_id} />
                      <FactCard label="ITR-1 Eligible" value={String(assessmentResult.result.itr1_eligible)} />
                      <FactCard label="ITR-2 Eligible" value={String(assessmentResult.result.itr2_eligible)} />
                      <FactCard label="Outside Scope" value={String(assessmentResult.result.outside_scope)} />
                    </div>

                    <div className="actions">
                      <button className="button button--primary" onClick={handlePrepareValidation} type="button">
                        Prepare final validation report
                      </button>
                    </div>
                  </>
                ) : (
                  <p className="subtle">Run step 3 to see the recommendation.</p>
                )}
                {finalError ? <Banner tone="error" message={finalError} /> : null}
              </section>

              <section className="panel">
                <div className="panel__intro">
                  <h3>Decision trace</h3>
                  <p>Useful for explaining which rules contributed to the recommendation.</p>
                </div>
                <div className="trace-list">
                  {(assessmentResult?.result?.decision_trace || []).map((ruleId) => (
                    <span className="trace-chip" key={ruleId}>
                      {ruleId}
                    </span>
                  ))}
                </div>
                <pre className="code-block">{JSON.stringify(assessmentResult?.result || {}, null, 2)}</pre>
              </section>
            </div>
          ) : null}

          {step === 4 ? (
            <div className="grid-two">
              <section className="panel">
                <div className="panel__intro">
                  <h3>Final validation and report</h3>
                  <p>Declared data is now reconciled against captured sources. The report highlights blocking issues, warnings, and the final payload sent to the rules engine.</p>
                </div>

                {finalResult ? (
                  <>
                    <div className="fact-strip">
                      <FactCard label="Return Type" value={finalResult.return_type} />
                      <FactCard label="Ready" value={String(finalResult.ready_for_validation)} />
                      <FactCard
                        label="Expected docs"
                        value={String(finalResult.expected_document_types?.length || 0)}
                      />
                      <FactCard
                        label="Flags"
                        value={String(finalResult.flags?.length || 0)}
                      />
                    </div>

                    <div className="report-list">
                      {(finalResult.flags || []).map((flag, index) => (
                        <article className={`report-flag report-flag--${flag.severity}`} key={`${flag.code}-${index}`}>
                          <strong>{flag.code}</strong>
                          <p>{flag.message}</p>
                        </article>
                      ))}
                      {!finalResult.flags?.length ? (
                        <article className="report-flag report-flag--success">
                          <strong>READY</strong>
                          <p>No blocking or warning flags were returned.</p>
                        </article>
                      ) : null}
                    </div>

                    <div className="recommendation">
                      <span className="recommendation__form">
                        {finalResult.validation_result?.recommended_form || "No form"}
                      </span>
                      <div>
                        <p>Final filing obligation: {finalResult.validation_result?.filing_obligation}</p>
                        <p>
                          Documents received: {(finalResult.documents_received || []).join(", ") || "none"}
                        </p>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="subtle">Run step 4 to generate the final report.</p>
                )}
              </section>

              <section className="panel">
                <div className="panel__intro">
                  <h3>Comparison and payload detail</h3>
                  <p>Use this to inspect which values won, which sources were compared, and what the backend validated.</p>
                </div>

                <div className="comparison-list">
                  {(finalResult?.field_comparisons || []).map((field) => (
                    <article className="comparison-row" key={field.field_code}>
                      <div>
                        <h4>{field.label}</h4>
                        <p>Status: {field.status}</p>
                      </div>
                      <div>
                        <p>Final value: {typeof field.final_value === "number" ? formatCurrency(field.final_value) : String(field.final_value)}</p>
                        <p>Source: {field.final_source_type || "n/a"}</p>
                      </div>
                    </article>
                  ))}
                </div>

                <pre className="code-block">{JSON.stringify(finalResult?.validation_payload || {}, null, 2)}</pre>
              </section>
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}

function Banner({ message, tone }) {
  return <div className={`banner banner--${tone}`}>{message}</div>;
}

function StatusPill({ label, value }) {
  return (
    <div className="status-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FactCard({ label, value }) {
  return (
    <div className="fact-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function NumberField({ label, onChange, value }) {
  return (
    <label>
      {label}
      <input onChange={(event) => onChange(event.target.value)} type="number" value={value} />
    </label>
  );
}

function BooleanField({ label, onChange, value }) {
  return (
    <label>
      {label}
      <select onChange={(event) => onChange(event.target.value)} value={String(value)}>
        <option value="false">No</option>
        <option value="true">Yes</option>
      </select>
    </label>
  );
}
