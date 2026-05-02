/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useRef } from "react";
import EmptyState from "../common/EmptyState";

/**
 * Detailed function explanation:
 * - Purpose: `formatRole` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function formatRole(role) {
  if (!role) {
    return "Message";
  }
  return String(role).toLowerCase();
}

/**
 * Detailed function explanation:
 * - Purpose: `ChatTranscript` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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
                <p>{message.content}</p>
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
