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

