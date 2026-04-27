import EmptyState from "../common/EmptyState";

export default function SessionList({ sessions, activeSessionId, loading, onSelect, onNewChat }) {
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
          {sessions.map((session) => (
            <button
              key={session.session_id}
              className={`session-row ${activeSessionId === session.session_id ? "active" : ""}`}
              onClick={() => onSelect(session.session_id)}
            >
              <strong>{session.title || `Session ${session.session_id}`}</strong>
              <span>{session.status}</span>
              <small>{new Date(session.started_at).toLocaleString()}</small>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
