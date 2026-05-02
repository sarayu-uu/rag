/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

/**
 * Detailed function explanation:
 * - Purpose: `HistoryInspector` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function HistoryInspector({ activeSessionId, sessionPayload }) {
  return (
    <section className="history-panel panel">
      <div className="panel-heading">
        <h2>4. Saved History</h2>
        <p>Uses GET /chat/sessions/{activeSessionId || "{id}"}/messages</p>
      </div>

      {!activeSessionId ? (
        <p className="muted-text">Pick a session or send a new message first.</p>
      ) : !sessionPayload ? (
        <p className="muted-text">No history payload loaded.</p>
      ) : (
        <div className="history-content">
          <p>
            <strong>Session:</strong> #{sessionPayload.session_id}
          </p>
          <p>
            <strong>Title:</strong> {sessionPayload.title}
          </p>
          <p>
            <strong>Status:</strong> {sessionPayload.status}
          </p>
          <p>
            <strong>Messages saved:</strong> {sessionPayload.messages?.length || 0}
          </p>
          <pre>{JSON.stringify(sessionPayload, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}

