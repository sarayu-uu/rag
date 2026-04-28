import EmptyState from "../common/EmptyState";

function getUsagePercent(session) {
  const used = Number(session?.tokens_used_total ?? 0);
  const limit = Number(session?.token_limit ?? 0);
  if (!limit || limit <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round((used / limit) * 100)));
}

export default function SessionList({ sessions, activeSessionId, loading, deletingSessionId, onDelete, onSelect, onNewChat }) {
  return (
    <section className="feature-card session-list-card">
      <div className="feature-card-header">
        <div>
          <p className="eyebrow">History</p>
          <h2>Chat sessions</h2>
        </div>
        <button className="ghost-button" onClick={onNewChat}>
          New chat
        </button>
      </div>

      {loading ? (
        <div className="inline-state">Loading saved sessions...</div>
      ) : sessions.length === 0 ? (
        <EmptyState
          title="No chats yet"
          message="Start a fresh conversation and your session history will appear here."
        />
      ) : (
        <div className="session-list">
          {sessions.map((session) => {
            const usagePercent = getUsagePercent(session);

            return (
              <div
                key={session.session_id}
                className={`session-row ${activeSessionId === session.session_id ? "active" : ""}`}
              >
                <button
                  type="button"
                  className="session-select-button"
                  onClick={() => onSelect(session.session_id)}
                >
                  <strong>{session.title || `Session ${session.session_id}`}</strong>
                  <span>{session.status}</span>
                  <span className="session-token-usage">
                    Tokens: {session.tokens_used_total ?? 0}
                    {typeof session.token_limit === "number" ? ` / ${session.token_limit}` : ""}
                  </span>
                  <div className="session-usage-meter" aria-hidden="true">
                    <div className="session-usage-fill" style={{ width: `${usagePercent}%` }} />
                  </div>
                  <small>{usagePercent}% of chat budget used</small>
                  <small>{new Date(session.started_at).toLocaleString()}</small>
                </button>

                <button
                  type="button"
                  className="ghost-button danger-button session-delete-button"
                  onClick={() => onDelete(session)}
                  disabled={deletingSessionId === session.session_id}
                >
                  {deletingSessionId === session.session_id ? "Deleting..." : "Delete"}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
