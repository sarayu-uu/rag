/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

/**
 * Detailed function explanation:
 * - Purpose: `SessionSidebar` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function SessionSidebar({
  sessions,
  activeSessionId,
  loading,
  onRefresh,
  onSelectSession,
  onStartNewChat,
}) {
  return (
    <aside className="session-sidebar panel">
      <div className="panel-heading sidebar-head">
        <h2>2. Sessions</h2>
        <div className="sidebar-actions">
          <button onClick={onStartNewChat}>New Chat</button>
          <button className="ghost-btn" onClick={onRefresh} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      <div className="session-list">
        {sessions.length === 0 ? (
          <p className="muted-text">No saved sessions yet.</p>
        ) : (
          sessions.map((session) => (
            <button
              key={session.session_id}
              className={`session-item ${activeSessionId === session.session_id ? "active" : ""}`}
              onClick={() => onSelectSession(session.session_id)}
            >
              <span className="session-title">
                {session.title || `Session ${session.session_id}`}
              </span>
              <span className="session-meta">
                #{session.session_id} • {session.tokens_used_total}/{session.token_limit}
              </span>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}

