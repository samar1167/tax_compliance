"use client";

import { useEffect, useMemo, useState } from "react";

import {
  activateKnowledgeBaseBundle,
  activateKnowledgeBaseVersion,
  deactivateKnowledgeBaseBundle,
  fetchHealth,
  fetchKnowledgeBaseBundles,
  fetchKnowledgeBaseSummary,
  fetchKnowledgeBaseVersionDetail,
  fetchKnowledgeBaseVersions,
  importKnowledgeBasePackage,
  validateKnowledgeBaseVersion,
} from "../lib/api";
import { titleCase } from "../lib/formatters";

function normalizeError(error) {
  if (error?.details?.length) {
    return error.details.map((item) => item.message || JSON.stringify(item)).join(" ");
  }
  return error?.message || "Request failed.";
}

export default function KnowledgeBaseApp() {
  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);
  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState(null);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [bundles, setBundles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");

  const [importPath, setImportPath] = useState("");
  const [importState, setImportState] = useState("idle");
  const [importMessage, setImportMessage] = useState("");
  const [importedVersionId, setImportedVersionId] = useState(null);

  const [versionActionState, setVersionActionState] = useState("idle");
  const [versionActionMessage, setVersionActionMessage] = useState("");

  const [bundleActionState, setBundleActionState] = useState("");
  const [bundleActionMessage, setBundleActionMessage] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      setPageError("");

      try {
        const [healthResponse, summaryResponse, versionsResponse] = await Promise.all([
          fetchHealth(),
          fetchKnowledgeBaseSummary(),
          fetchKnowledgeBaseVersions(),
        ]);

        if (cancelled) {
          return;
        }

        setHealth(healthResponse);
        setSummary(summaryResponse);
        setVersions(versionsResponse.versions || []);
        setSelectedVersionId(summaryResponse?.id || versionsResponse.versions?.[0]?.id || null);
      } catch (error) {
        if (!cancelled) {
          setPageError(normalizeError(error));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadVersionDetail() {
      if (!selectedVersionId) {
        setSelectedVersion(null);
        setBundles([]);
        return;
      }

      try {
        const [detailResponse, bundleResponse] = await Promise.all([
          fetchKnowledgeBaseVersionDetail(selectedVersionId),
          fetchKnowledgeBaseBundles(selectedVersionId),
        ]);

        if (cancelled) {
          return;
        }

        setSelectedVersion(detailResponse);
        setBundles(bundleResponse.bundles || []);
      } catch (error) {
        if (!cancelled) {
          setVersionActionMessage(normalizeError(error));
        }
      }
    }

    loadVersionDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedVersionId]);

  const selectedVersionSummary = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) || null,
    [selectedVersionId, versions]
  );

  async function refreshVersions(preferredVersionId) {
    const [summaryResponse, versionsResponse] = await Promise.all([
      fetchKnowledgeBaseSummary(),
      fetchKnowledgeBaseVersions(),
    ]);

    setSummary(summaryResponse);
    setVersions(versionsResponse.versions || []);
    setSelectedVersionId(preferredVersionId || summaryResponse?.id || versionsResponse.versions?.[0]?.id || null);
  }

  async function handleImportPackage(event) {
    event.preventDefault();
    setImportState("loading");
    setImportMessage("");

    try {
      const response = await importKnowledgeBasePackage({ package_path: importPath });
      setImportedVersionId(response.version?.id || null);
      await refreshVersions(response.version?.id);
      setImportState("ready");
      setImportMessage(
        response.validation_errors?.length
          ? `Imported with validation issues. ${response.validation_errors.length} error(s) returned.`
          : "Schema/package imported successfully as a new draft version."
      );
    } catch (error) {
      setImportState("error");
      setImportMessage(normalizeError(error));
    }
  }

  async function handleValidateVersion(versionId) {
    setVersionActionState(`validate-${versionId}`);
    setVersionActionMessage("");

    try {
      const response = await validateKnowledgeBaseVersion(versionId);
      await refreshVersions(versionId);
      setVersionActionMessage(
        response.validation_errors?.length
          ? `Testing and validation completed with ${response.validation_errors.length} error(s).`
          : "Testing and validation passed successfully."
      );
    } catch (error) {
      setVersionActionMessage(normalizeError(error));
    } finally {
      setVersionActionState("idle");
    }
  }

  async function handleActivateVersion(versionId) {
    setVersionActionState(`activate-${versionId}`);
    setVersionActionMessage("");

    try {
      await activateKnowledgeBaseVersion(versionId);
      await refreshVersions(versionId);
      setVersionActionMessage("Version finalized and activated. Any older active version for the same module/year is now retired.");
    } catch (error) {
      setVersionActionMessage(normalizeError(error));
    } finally {
      setVersionActionState("idle");
    }
  }

  async function handleToggleBundle(bundle) {
    setBundleActionState(bundle.bundle_code);
    setBundleActionMessage("");

    try {
      if (bundle.is_active) {
        await deactivateKnowledgeBaseBundle(selectedVersionId, bundle.bundle_code);
      } else {
        await activateKnowledgeBaseBundle(selectedVersionId, bundle.bundle_code);
      }

      const [detailResponse, bundleResponse] = await Promise.all([
        fetchKnowledgeBaseVersionDetail(selectedVersionId),
        fetchKnowledgeBaseBundles(selectedVersionId),
      ]);
      setSelectedVersion(detailResponse);
      setBundles(bundleResponse.bundles || []);
      setBundleActionMessage(
        `${bundle.bundle_code} ${bundle.is_active ? "deactivated" : "activated"} successfully.`
      );
    } catch (error) {
      setBundleActionMessage(normalizeError(error));
    } finally {
      setBundleActionState("");
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <div className="hero__copy">
          <p className="eyebrow">Knowledge Base Operations</p>
          <h1>KB Manager</h1>
          <div className="actions">
            <a className="button" href="/">
              Tax Workflow
            </a>
          </div>
        </div>
        <div className="hero__panel">
          <StatusPill label="Backend" value={health?.status || (loading ? "checking" : "offline")} />
          <StatusPill label="Active KB" value={summary?.version || "n/a"} />
          <StatusPill label="Package" value={summary?.package_id || "n/a"} />
          <StatusPill label="Assessment Year" value={summary?.assessment_year || "n/a"} />
        </div>
      </section>

      {pageError ? <Banner tone="error" message={pageError} /> : null}

      <section className="panel">
        <div className="workspace__header">
          <div>
            <p className="workspace__eyebrow">Version Control</p>
            <h2>{selectedVersionSummary?.version || "Select a knowledge-base version"}</h2>
          </div>
          <div className="workspace__meta">
            <span>{selectedVersionSummary?.package_id || "No package selected"}</span>
            <span>{selectedVersionSummary?.status || "n/a"}</span>
            <span>{selectedVersionSummary?.assessment_year || "n/a"}</span>
          </div>
        </div>

        <div className="grid-two">
          <section className="panel">
            <div className="panel__intro">
              <h3>Version Selection</h3>
              <p>Select the KB version you want to inspect, test, validate, finalize, or adjust via bundles.</p>
            </div>

            <label>
              Version
              <select
                onChange={(event) => setSelectedVersionId(Number(event.target.value))}
                value={selectedVersionId || ""}
              >
                <option value="" disabled>
                  Select a version
                </option>
                {versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    #{version.id} | {version.version} | {version.status}
                  </option>
                ))}
              </select>
            </label>

            <div className="fact-strip">
              <FactCard label="Selected Rules" value={String(selectedVersion?.rule_count || 0)} />
              <FactCard label="Selected Tests" value={String(selectedVersion?.test_case_count || 0)} />
              <FactCard label="Bundles" value={String(selectedVersion?.bundle_count || 0)} />
              <FactCard label="Validation Errors" value={String(selectedVersion?.validation_error_count || 0)} />
            </div>

            <div className="actions">
              <button
                className="button button--primary"
                disabled={!selectedVersion || versionActionState === `validate-${selectedVersion?.id}`}
                onClick={() => handleValidateVersion(selectedVersion.id)}
                type="button"
              >
                {versionActionState === `validate-${selectedVersion?.id}` ? "Testing and validating..." : "Test and validate"}
              </button>
              <button
                className="button"
                disabled={!selectedVersion || versionActionState === `activate-${selectedVersion?.id}`}
                onClick={() => handleActivateVersion(selectedVersion.id)}
                type="button"
              >
                {versionActionState === `activate-${selectedVersion?.id}` ? "Finalizing..." : "Finalize version"}
              </button>
            </div>

            <div className="panel__note">
              <strong>Activation behavior</strong>
              <p>Direct deactivation is not exposed by the backend. Finalizing another version automatically retires the currently active version for the same module and assessment year.</p>
            </div>
          </section>

          <section className="panel">
            <div className="panel__intro">
              <h3>Current Active Baseline</h3>
              <p>Use this summary to compare the current production version against the draft or candidate you are reviewing.</p>
            </div>

            <div className="fact-strip">
              <FactCard label="Version" value={summary?.version || "n/a"} />
              <FactCard label="Status" value={summary?.status || "n/a"} />
              <FactCard label="Rules" value={String(summary?.rule_count || 0)} />
              <FactCard label="Bundles" value={String(summary?.bundle_count || 0)} />
            </div>

            {summary?.required_input_paths?.length ? (
              <div className="comparison-list">
                {summary.required_input_paths.map((path) => (
                  <article className="comparison-row" key={path}>
                    <div>
                      <h4>{titleCase(path)}</h4>
                      <p>{path}</p>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="subtle">No required input paths available.</p>
            )}
          </section>
        </div>

        {versionActionMessage ? (
          <Banner
            tone={versionActionMessage.toLowerCase().includes("error") || versionActionMessage.toLowerCase().includes("cannot") ? "error" : "info"}
            message={versionActionMessage}
          />
        ) : null}
      </section>

      <section className="grid-two">
        <section className="panel">
          <div className="panel__intro">
            <h3>Add New Rules</h3>
            <p>Import a schema/package directory, then convert that imported draft into a tested, validated, and finalized version.</p>
          </div>

          <form className="grid-form" onSubmit={handleImportPackage}>
            <label>
              Schema or package path
              <input
                onChange={(event) => setImportPath(event.target.value)}
                placeholder="knowledge_base/packages/ay2026_27_v1_1_bundle_experiment"
                value={importPath}
              />
            </label>

            <div className="actions">
              <button className="button button--primary" disabled={importState === "loading"} type="submit">
                {importState === "loading" ? "Importing..." : "Import as new draft"}
              </button>
            </div>
          </form>

          {importMessage ? (
            <Banner tone={importState === "error" ? "error" : "info"} message={importMessage} />
          ) : null}

          <div className="comparison-list">
            <article className="comparison-row">
              <div>
                <h4>1. Import schema/package</h4>
                <p>Create a draft version from the rule files and metadata package.</p>
              </div>
            </article>
            <article className="comparison-row">
              <div>
                <h4>2. Test and validate</h4>
                <p>Run the backend’s validation routine, which includes package validation, dependency checks, and bundled regression tests.</p>
              </div>
            </article>
            <article className="comparison-row">
              <div>
                <h4>3. Review results</h4>
                <p>Inspect validation errors, rules, required inputs, test cases, and bundle configuration.</p>
              </div>
            </article>
            <article className="comparison-row">
              <div>
                <h4>4. Finalize</h4>
                <p>Activate the candidate to make it the new KB version in force.</p>
              </div>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="panel__intro">
            <h3>Imported Draft Actions</h3>
            <p>After import, jump directly to that version for testing, validating, and finalizing.</p>
          </div>

          {importedVersionId ? (
            <>
              <div className="fact-strip">
                <FactCard label="Imported Version ID" value={String(importedVersionId)} />
                <FactCard label="Selected Version ID" value={String(selectedVersionId || "n/a")} />
              </div>

              <div className="actions">
                <button className="button" onClick={() => setSelectedVersionId(importedVersionId)} type="button">
                  Open imported version
                </button>
                <button
                  className="button button--primary"
                  disabled={selectedVersionId !== importedVersionId || versionActionState === `validate-${importedVersionId}`}
                  onClick={() => handleValidateVersion(importedVersionId)}
                  type="button"
                >
                  {versionActionState === `validate-${importedVersionId}` ? "Testing..." : "Test imported draft"}
                </button>
                <button
                  className="button"
                  disabled={selectedVersionId !== importedVersionId || versionActionState === `activate-${importedVersionId}`}
                  onClick={() => handleActivateVersion(importedVersionId)}
                  type="button"
                >
                  {versionActionState === `activate-${importedVersionId}` ? "Finalizing..." : "Finalize imported draft"}
                </button>
              </div>
            </>
          ) : (
            <p className="subtle">No newly imported draft selected yet.</p>
          )}
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
