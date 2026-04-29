export const metadata = {
  title: "Tax Compliance Workflow",
  description: "Guided workflow for taxpayer onboarding, source capture, ITR recommendation, and final validation.",
};

const globalStyles = `
  :root {
    --bg: #f3efe5;
    --panel: rgba(255, 252, 245, 0.82);
    --panel-strong: #fffaf0;
    --text: #1d2430;
    --muted: #5f6776;
    --line: rgba(29, 36, 48, 0.12);
    --accent: #0e6d5d;
    --accent-strong: #09483e;
    --accent-soft: #d9efe6;
    --warning: #c57d19;
    --danger: #b7463f;
    --success: #16794f;
    --shadow: 0 22px 60px rgba(46, 37, 22, 0.12);
  }

  * {
    box-sizing: border-box;
  }

  html {
    min-height: 100%;
    background:
      radial-gradient(circle at top left, rgba(14, 109, 93, 0.16), transparent 26%),
      radial-gradient(circle at right, rgba(197, 125, 25, 0.14), transparent 18%),
      linear-gradient(180deg, #f8f4ea 0%, #efe7d8 100%);
  }

  body {
    margin: 0;
    min-height: 100vh;
    color: var(--text);
    font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
  }

  button,
  input,
  select,
  textarea {
    font: inherit;
  }

  button {
    cursor: pointer;
  }

  .shell {
    padding: 40px 28px 64px;
  }

  .hero {
    display: grid;
    grid-template-columns: 2.2fr 1fr;
    gap: 24px;
    margin-bottom: 28px;
  }

  .hero__copy,
  .hero__panel,
  .timeline,
  .panel {
    backdrop-filter: blur(12px);
    background: var(--panel);
    border: 1px solid rgba(255, 255, 255, 0.65);
    border-radius: 28px;
    box-shadow: var(--shadow);
  }

  .hero__copy {
    padding: 32px;
  }

  .hero__copy h1 {
    margin: 0;
    max-width: 12ch;
    font-family: Georgia, "Times New Roman", serif;
    font-size: clamp(2.7rem, 6vw, 5rem);
    line-height: 0.94;
    letter-spacing: -0.04em;
  }

  .hero__lede {
    max-width: 58ch;
    color: var(--muted);
    font-size: 1.05rem;
    line-height: 1.65;
  }

  .hero__panel {
    padding: 24px;
    display: grid;
    gap: 14px;
    align-content: start;
  }

  .eyebrow,
  .workspace__eyebrow {
    margin: 0 0 10px;
    color: var(--accent-strong);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }

  .status-pill,
  .fact-card {
    padding: 14px 16px;
    background: rgba(255, 255, 255, 0.62);
    border: 1px solid var(--line);
    border-radius: 18px;
  }

  .status-pill span,
  .fact-card span {
    display: block;
    color: var(--muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .status-pill strong,
  .fact-card strong {
    font-size: 1rem;
  }

  .board {
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 24px;
  }

  .timeline {
    padding: 18px;
    display: grid;
    gap: 10px;
    align-content: start;
  }

  .timeline__item {
    border: 1px solid transparent;
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.58);
    color: var(--text);
    padding: 16px;
    display: grid;
    gap: 6px;
    justify-items: start;
    text-align: left;
    transition: transform 150ms ease, border-color 150ms ease, background 150ms ease;
  }

  .timeline__item:hover {
    transform: translateY(-1px);
    border-color: rgba(14, 109, 93, 0.24);
  }

  .timeline__item.is-active {
    background: linear-gradient(135deg, rgba(14, 109, 93, 0.16), rgba(255, 255, 255, 0.75));
    border-color: rgba(14, 109, 93, 0.34);
  }

  .timeline__item.is-complete .timeline__index {
    color: var(--success);
  }

  .timeline__index {
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.12em;
  }

  .workspace {
    display: grid;
    gap: 22px;
  }

  .workspace__header {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 16px;
  }

  .workspace__header h2 {
    margin: 0;
    font-size: clamp(1.8rem, 3vw, 2.7rem);
    font-family: Georgia, "Times New Roman", serif;
  }

  .workspace__meta {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .workspace__meta span,
  .badge {
    padding: 7px 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid var(--line);
    font-size: 0.82rem;
  }

  .panel {
    padding: 24px;
  }

  .panel__intro h3,
  .panel__intro h4,
  .comparison-row h4,
  .source-row h4 {
    margin: 0;
  }

  .panel__intro p,
  .panel__note p,
  .source-row p,
  .comparison-row p,
  .subtle {
    color: var(--muted);
  }

  .grid-form,
  .source-form,
  .field-group,
  .field-grid,
  .grid-two,
  .source-picker {
    display: grid;
    gap: 16px;
  }

  .grid-two {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .field-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  label {
    display: grid;
    gap: 8px;
    color: var(--muted);
    font-size: 0.95rem;
  }

  input,
  select,
  textarea {
    width: 100%;
    padding: 13px 14px;
    border-radius: 16px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.85);
    color: var(--text);
  }

  input:focus,
  select:focus,
  textarea:focus {
    outline: 2px solid rgba(14, 109, 93, 0.22);
    border-color: rgba(14, 109, 93, 0.4);
  }

  .actions,
  .fact-strip,
  .trace-list,
  .toggle-group,
  .workspace__meta {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .button {
    border: 1px solid var(--line);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.72);
    color: var(--text);
    padding: 12px 18px;
  }

  .button--primary,
  .toggle-group .is-selected {
    background: linear-gradient(135deg, var(--accent), var(--accent-strong));
    color: white;
    border-color: transparent;
  }

  .toggle-group button {
    padding: 12px 16px;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.72);
  }

  .banner,
  .status-card,
  .recommendation,
  .code-block,
  .report-flag,
  .comparison-row,
  .source-row,
  .error-list {
    border-radius: 20px;
    border: 1px solid var(--line);
  }

  .banner {
    padding: 14px 16px;
    margin-bottom: 20px;
  }

  .banner--error {
    background: rgba(183, 70, 63, 0.09);
    color: var(--danger);
  }

  .status-card,
  .recommendation,
  .report-flag,
  .comparison-row,
  .source-row,
  .error-list {
    padding: 16px;
    background: rgba(255, 255, 255, 0.62);
  }

  .recommendation {
    display: flex;
    justify-content: space-between;
    gap: 18px;
    align-items: center;
  }

  .recommendation__form {
    font-size: clamp(2rem, 5vw, 3.8rem);
    font-weight: 700;
    font-family: Georgia, "Times New Roman", serif;
    color: var(--accent-strong);
  }

  .code-block {
    padding: 18px;
    background: #1f2834;
    color: #edf3f7;
    overflow: auto;
    font-size: 0.88rem;
  }

  .source-list,
  .report-list,
  .comparison-list {
    display: grid;
    gap: 12px;
  }

  .source-row,
  .comparison-row {
    display: flex;
    justify-content: space-between;
    gap: 18px;
    align-items: start;
  }

  .source-row__meta {
    display: grid;
    gap: 8px;
    justify-items: end;
  }

  .badge--ready,
  .badge--success,
  .report-flag--success {
    color: var(--success);
  }

  .badge--pending,
  .badge--draft {
    color: var(--warning);
  }

  .badge--ready,
  .badge--pending,
  .badge--draft {
    background: rgba(255, 255, 255, 0.8);
  }

  .report-flag--error {
    background: rgba(183, 70, 63, 0.09);
  }

  .report-flag--warning {
    background: rgba(197, 125, 25, 0.09);
  }

  .trace-chip {
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(14, 109, 93, 0.1);
    border: 1px solid rgba(14, 109, 93, 0.18);
    font-size: 0.86rem;
  }

  @media (max-width: 1100px) {
    .hero,
    .board,
    .grid-two {
      grid-template-columns: 1fr;
    }

    .timeline {
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }
  }

  @media (max-width: 720px) {
    .shell {
      padding: 22px 16px 48px;
    }

    .hero__copy,
    .hero__panel,
    .timeline,
    .panel {
      border-radius: 22px;
    }

    .field-grid,
    .source-row,
    .comparison-row {
      grid-template-columns: 1fr;
      display: grid;
    }
  }
`;

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
        <style dangerouslySetInnerHTML={{ __html: globalStyles }} />
      </body>
    </html>
  );
}
