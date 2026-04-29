import AssessmentForm from "@/components/AssessmentForm";
import { fetchKnowledgeBaseSummary } from "@/lib/api";

export default async function HomePage() {
  let knowledgeBase = null;
  let error = null;

  try {
    knowledgeBase = await fetchKnowledgeBaseSummary();
  } catch (err) {
    error = err.message;
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <span className="eyebrow">AI-assisted tax compliance MVP</span>
        <h1>Indian Filing Obligation and ITR Selection</h1>
        <p>
          A split-stack MVP with a Django knowledge-base backend and a Next.js frontend. Deterministic rules decide filing obligation and form selection; the knowledge base stays versioned for future regeneration and auditability.
        </p>
      </section>
      {error ? (
        <section className="panel">
          <h2>Backend unavailable</h2>
          <p className="empty">{error}</p>
        </section>
      ) : (
        <AssessmentForm knowledgeBase={knowledgeBase} />
      )}
    </main>
  );
}
