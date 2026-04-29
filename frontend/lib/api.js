const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.API_BASE_URL ||
  "http://localhost:9010";

function buildUrl(path, query) {
  const url = new URL(path, API_BASE_URL);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }
  return url.toString();
}

function coerceErrorPayload(error) {
  if (Array.isArray(error)) {
    return error;
  }

  if (typeof error === "string") {
    try {
      const parsed = JSON.parse(error);
      if (Array.isArray(parsed)) {
        return parsed;
      }
    } catch (_) {
      return [{ message: error }];
    }
  }

  if (error && typeof error === "object") {
    return [error];
  }

  return [{ message: "Unexpected error." }];
}

async function request(path, options = {}) {
  const response = await fetch(buildUrl(path, options.query), {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || "Request failed.");
    error.status = response.status;
    error.details = coerceErrorPayload(data.error);
    error.payload = data;
    throw error;
  }
  return data;
}

export function fetchHealth() {
  return request("/api/health/");
}

export function fetchKnowledgeBaseSummary() {
  return request("/api/knowledge-base/summary/");
}

export function fetchKnowledgeBaseVersions() {
  return request("/api/knowledge-base/versions/");
}

export function fetchKnowledgeBaseVersionDetail(versionId) {
  return request(`/api/knowledge-base/versions/${versionId}/`);
}

export function importKnowledgeBasePackage(payload) {
  return request("/api/knowledge-base/import/", {
    method: "POST",
    body: payload,
  });
}

export function validateKnowledgeBaseVersion(versionId) {
  return request(`/api/knowledge-base/versions/${versionId}/validate/`, {
    method: "POST",
  });
}

export function activateKnowledgeBaseVersion(versionId) {
  return request(`/api/knowledge-base/versions/${versionId}/activate/`, {
    method: "POST",
  });
}

export function fetchKnowledgeBaseBundles(versionId) {
  return request(`/api/knowledge-base/versions/${versionId}/bundles/`);
}

export function activateKnowledgeBaseBundle(versionId, bundleCode) {
  return request(`/api/knowledge-base/versions/${versionId}/bundles/${bundleCode}/activate/`, {
    method: "POST",
  });
}

export function deactivateKnowledgeBaseBundle(versionId, bundleCode) {
  return request(`/api/knowledge-base/versions/${versionId}/bundles/${bundleCode}/deactivate/`, {
    method: "POST",
  });
}

export function createTaxUserSession(payload) {
  return request("/api/return-sources/sessions/", {
    method: "POST",
    body: payload,
  });
}

export function fetchReturnSourceSessions() {
  return request("/api/return-sources/sessions/");
}

export function fetchReturnSourceTypes(returnType) {
  return request("/api/return-sources/types/", {
    query: { return_type: returnType },
  });
}

export function fetchReturnSourceTestRecords(returnType, sourceType) {
  return request("/api/return-sources/test-records/", {
    query: { return_type: returnType, source_type: sourceType },
  });
}

export function fetchReturnSourceSession(sessionId) {
  return request(`/api/return-sources/sessions/${sessionId}/`);
}

export function saveReturnSourceRecord(sessionId, payload) {
  return request(`/api/return-sources/sessions/${sessionId}/records/`, {
    method: "POST",
    body: payload,
  });
}

export function evaluateAssessment(payload) {
  return request("/api/assessments/evaluate/", {
    method: "POST",
    body: payload,
  });
}

export function prepareValidation(payload) {
  return request("/api/returns/prepare-validation/", {
    method: "POST",
    body: payload,
  });
}
