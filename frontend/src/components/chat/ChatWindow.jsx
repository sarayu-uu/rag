import { useEffect, useRef } from "react";

function formatTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString();
}

export default function ChatWindow({
  sessionInfo,
  messages,
  loadingMessages,
  sending,
  lastQueryInfo,
}) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!scrollRef.current) {
      return;
    }
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  return (
    <section className="chat-window panel">
      <div className="chat-window-head">
        <h2>Chat</h2>
        <div className="session-pill">
          {sessionInfo?.session_id
            ? `Session #${sessionInfo.session_id} (${sessionInfo.created ? "new" : "continue"})`
            : "New session on first message"}
        </div>
      </div>

      {lastQueryInfo ? (
        <div className="query-info">
          <span>Retrieved: {lastQueryInfo.retrieved_match_count}</span>
          <span>Semantic: {lastQueryInfo.retrieval_debug?.semantic_match_count ?? 0}</span>
          <span>Keyword: {lastQueryInfo.retrieval_debug?.keyword_match_count ?? 0}</span>
        </div>
      ) : null}

      <div className="chat-scroll" ref={scrollRef}>
        {loadingMessages ? (
          <p className="muted-text">Loading session messages...</p>
        ) : messages.length === 0 ? (
          <p className="muted-text">No messages yet. Send the first question.</p>
        ) : (
          messages.map((message) => (
            <article
              key={message.id}
              className={`bubble ${message.role === "user" ? "user-bubble" : "assistant-bubble"}`}
            >
              <header>
                <strong>{message.role}</strong>
                <span>{formatTime(message.created_at)}</span>
              </header>
              <p>{message.content}</p>
            </article>
          ))
        )}

        {sending ? (
          <article className="bubble assistant-bubble pending-bubble">
            <header>
              <strong>assistant</strong>
            </header>
            <p>Generating grounded response...</p>
          </article>
        ) : null}
      </div>
    </section>
  );
}
