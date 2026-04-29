const API_BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:9010";

export async function fetchKnowledgeBaseSummary() {
  const response = await fetch(`${API_BASE}/api/knowledge-base/summary/`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to load knowledge base summary.");
  }

  return response.json();
}

export async function evaluateAssessment(payload) {
  const response = await fetch(`${API_BASE}/api/assessments/evaluate/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to evaluate assessment.");
  }

  return response.json();
}
