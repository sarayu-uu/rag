/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
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

function buildTurns(messages, qaInsightsByAssistantId) {
  const turns = [];
  const messageIdToTurnIndex = new Map();
  let pendingUser = null;

  for (const message of messages || []) {
    const role = String(message?.role || "").toUpperCase();
    if (role === "USER") {
      pendingUser = message;
      continue;
    }
    if (role !== "ASSISTANT") {
      continue;
    }

    const insight = message?.id ? qaInsightsByAssistantId?.[message.id] : null;
    const turn = {
      userMessage: pendingUser,
      assistantMessage: message,
      inputTokens: Number(insight?.inputTokens ?? pendingUser?.token_count ?? 0),
      outputTokens: Number(insight?.outputTokens ?? message?.token_count ?? 0),
      totalTokens: Number(insight?.totalTokens ?? (Number(pendingUser?.token_count || 0) + Number(message?.token_count || 0))),
      chunks: Array.isArray(insight?.chunks) ? insight.chunks : [],
      question: insight?.question || pendingUser?.content || "",
      retrievedMatchCount: Number(insight?.retrievedMatchCount ?? 0),
    };
    turns.push(turn);
    const turnIndex = turns.length - 1;
    if (pendingUser?.id) {
      messageIdToTurnIndex.set(pendingUser.id, turnIndex);
    }
    if (message?.id) {
      messageIdToTurnIndex.set(message.id, turnIndex);
    }
    pendingUser = null;
  }

  return { turns, messageIdToTurnIndex };
}
/** Renders chat messages in transcript form. */
export default function ChatTranscript({ messages, pendingAnswer, loading, children, qaInsightsByAssistantId = {} }) {
  const scrollRef = useRef(null);
  const [activeTurnIndex, setActiveTurnIndex] = useState(null);
  const { turns, messageIdToTurnIndex } = useMemo(
    () => buildTurns(messages, qaInsightsByAssistantId),
    [messages, qaInsightsByAssistantId]
  );
  const activeTurn = activeTurnIndex === null ? null : turns[activeTurnIndex] || null;

  useEffect(() => {
    if (!scrollRef.current) {
      return;
    }

    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, pendingAnswer, loading]);

  useEffect(() => {
    if (!activeTurn) {
      return;
    }
    function handleEscape(event) {
      if (event.key === "Escape") {
        setActiveTurnIndex(null);
      }
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [activeTurn]);

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
              <article key={message.id || `${message.role}-${message.created_at}`} className={`message-bubble ${formatRole(message.role)}`}>
                <header className="message-header-row">
                  <span>{formatRole(message.role)}</span>
                  <div className="message-header-actions">
                    <small>{message.created_at ? new Date(message.created_at).toLocaleTimeString() : ""}</small>
                    {message?.id && messageIdToTurnIndex.has(message.id) ? (
                      <button
                        type="button"
                        className="message-detail-toggle"
                        onClick={() => setActiveTurnIndex(messageIdToTurnIndex.get(message.id))}
                      >
                        Details
                      </button>
                    ) : null}
                  </div>
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

      {activeTurn
        ? createPortal(
            <div className="qa-modal-overlay" onClick={() => setActiveTurnIndex(null)}>
              <div className="qa-modal-card" onClick={(event) => event.stopPropagation()}>
                <div className="qa-modal-head">
                  <h3>Turn Details</h3>
                  <button type="button" className="qa-modal-close" onClick={() => setActiveTurnIndex(null)}>
                    Close
                  </button>
                </div>

                <div className="qa-token-grid">
                  <div className="qa-token-cell">
                    <span>Input tokens</span>
                    <strong>{activeTurn.inputTokens}</strong>
                  </div>
                  <div className="qa-token-cell">
                    <span>Output tokens</span>
                    <strong>{activeTurn.outputTokens}</strong>
                  </div>
                  <div className="qa-token-cell">
                    <span>Total tokens</span>
                    <strong>{activeTurn.totalTokens}</strong>
                  </div>
                </div>

                <div className="qa-modal-section">
                  <p className="eyebrow">Question</p>
                  <p>{String(activeTurn.question || "").trim() || "No question text available."}</p>
                </div>

                <div className="qa-modal-section">
                  <p className="eyebrow">
                    Related chunks
                    {activeTurn.retrievedMatchCount > 0 ? ` (${activeTurn.chunks.length} of ${activeTurn.retrievedMatchCount})` : ""}
                  </p>
                  {activeTurn.chunks.length === 0 ? (
                    <p className="muted-copy">Chunk details are available for newly asked questions in this session.</p>
                  ) : (
                    <div className="qa-chunk-list">
                      {activeTurn.chunks.map((chunk, index) => (
                        <article key={`${chunk.id || index}-${chunk.document_id}-${chunk.chunk_index}`} className="qa-chunk-card">
                          <header>
                            <strong>{chunk.source_name || `Document ${chunk.document_id}`}</strong>
                            <small>
                              doc {chunk.document_id} | chunk {chunk.chunk_index}
                            </small>
                          </header>
                          <p>{String(chunk.content || "").trim().slice(0, 360)}{String(chunk.content || "").trim().length > 360 ? "..." : ""}</p>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>,
            document.body
          )
        : null}
    </section>
  );
}



