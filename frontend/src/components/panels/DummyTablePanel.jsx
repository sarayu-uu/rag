/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

/**
 * Detailed function explanation:
 * - Purpose: `DummyTablePanel` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function DummyTablePanel({ title, description, rows }) {
  return (
    <section className="panel right-panel">
      <header className="panel-heading">
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      <div className="scroll-region">
        {rows.map((row, index) => (
          <article key={`${title}-${index}`} className="doc-row">
            <p>
              <strong>{row.title}</strong>
            </p>
            <p className="muted-text">{row.subtitle}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

