/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useRef } from "react";
import EmptyState from "../common/EmptyState";
/** Formats role. */
function formatRole(role) {
  if (!role) {
    return "Message";
  }
  return String(role).toLowerCase();
}

function renderMessageContent(content) {
  const text = String(content || "");
  const parts = text.split(/```/g);

  return parts.map((part, index) => {
    if (index % 2 === 1) {
      const lines = part.split("\n");
      const language = (lines[0] || "").trim();
      const code = lines.slice(1).join("\n").trimEnd();
      return (
        <pre key={`code-${index}`} className="message-code-block">
          <code className={language ? `language-${language}` : ""}>{code || part}</code>
        </pre>
      );
    }

    const bulletLines = part
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .filter((line) => /^[-*]\s+/.test(line));

    if (bulletLines.length >= 2 && bulletLines.length >= Math.ceil(part.split("\n").filter((line) => line.trim()).length / 2)) {
      return (
        <ul key={`list-${index}`} className="message-bullet-list">
          {bulletLines.map((line, itemIndex) => (
            <li key={`item-${index}-${itemIndex}`}>{line.replace(/^[-*]\s+/, "")}</li>
          ))}
        </ul>
      );
    }

    const paragraphs = part
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    return paragraphs.map((paragraph, paragraphIndex) => (
      <p key={`p-${index}-${paragraphIndex}`}>{paragraph}</p>
    ));
  });
}
/** Renders chat messages in transcript form. */
export default function ChatTranscript({ messages, pendingAnswer, loading, children }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!scrollRef.current) {
      return;
    }

    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, pendingAnswer, loading]);

  return (
    <section className="feature-card transcript-card">
      <div className="feature-card-header">
        <div>
          <p className="eyebrow">Conversation</p>
          <h2>Grounded responses</h2>
        </div>
      </div>

      <div className="transcript-main">
        {loading ? (
          <div className="inline-state">Loading conversation...</div>
        ) : messages.length === 0 && !pendingAnswer ? (
          <EmptyState
            title="Start asking"
            message="Ask about the documents in your workspace and the answer will appear here. Supporting citations appear in Source Citations."
          />
        ) : (
          <div ref={scrollRef} className="transcript-scroll">
            {messages.map((message) => (
              <article
                key={message.id || `${message.role}-${message.created_at}`}
                className={`message-bubble ${formatRole(message.role)}`}
              >
                <header>
                  <span>{formatRole(message.role)}</span>
                  <small>{message.created_at ? new Date(message.created_at).toLocaleTimeString() : ""}</small>
                </header>
                <div className="message-content">{renderMessageContent(message.content)}</div>
              </article>
            ))}

            {pendingAnswer ? (
              <article className="message-bubble assistant pending">
                <header>
                  <span>assistant</span>
                  <small>thinking</small>
                </header>
                <p>{pendingAnswer}</p>
              </article>
            ) : null}
          </div>
        )}
      </div>

      {children ? <div className="transcript-composer">{children}</div> : null}
    </section>
  );
}



