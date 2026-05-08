/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import ChatTranscript from "../components/chat/ChatTranscript";
import SessionList from "../components/chat/SessionList";
import SourcePanel from "../components/chat/SourcePanel";
import { deleteChatSession, getChatMessages, getChatSessions, getDocuments, queryChat } from "../lib/api";
/** Renders the main chat workspace. */
export default function ChatPage() {
  const [sessions, setSessions] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [answerPayload, setAnswerPayload] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState(null);
  const [error, setError] = useState("");
  const [pipelineTrace, setPipelineTrace] = useState([]);
  const activeSession = sessions.find((session) => session.session_id === activeSessionId) || null;
  const activeSessionPercent = activeSession?.token_limit
    ? Math.min(100, Math.round(((activeSession?.tokens_used_total ?? 0) / Math.max(activeSession.token_limit, 1)) * 100))
    : 0;
  const isActiveSessionAtLimit =
    Boolean(activeSessionId) &&
    Boolean(activeSession?.token_limit) &&
    Number(activeSession?.tokens_used_total ?? 0) >= Number(activeSession?.token_limit ?? 0);
  /** Loads sessions. */
  async function loadSessions() {
    setLoadingSessions(true);
    try {
      const response = await getChatSessions();
      setSessions(response.sessions || []);
    } catch (sessionError) {
      setError(sessionError.message || "Failed to load sessions.");
    } finally {
      setLoadingSessions(false);
    }
  }

  async function loadDocuments() {
    try {
      const response = await getDocuments();
      setDocuments(response.documents || []);
    } catch (documentsError) {
      setError(documentsError.message || "Failed to load documents.");
    }
  }

  useEffect(() => {
    loadSessions();
    loadDocuments();
  }, []);
  /** Opens session. */
  async function openSession(sessionId, options = {}) {
    setLoadingMessages(true);
    setError("");
    try {
      const response = await getChatMessages(sessionId);
      setActiveSessionId(sessionId);
      setMessages(response.messages || []);
      if (!options.keepAnswerPayload) {
        setAnswerPayload(null);
      }
    } catch (messageError) {
      setError(messageError.message || "Failed to load session.");
    } finally {
      setLoadingMessages(false);
    }
  }
  /** Starts new chat. */
  function startNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setAnswerPayload(null);
    setQuestion("");
    setError("");
  }

  function toggleDocumentSelection(documentId) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId) ? current.filter((id) => id !== documentId) : [...current, documentId]
    );
  }
  /** Deletes the selected chat session. */
  async function handleDeleteSession(session) {
    const confirmed = window.confirm(`Delete chat session "${session.title || `Session ${session.session_id}`}"?`);
    if (!confirmed) {
      return;
    }

    setDeletingSessionId(session.session_id);
    setError("");
    try {
      await deleteChatSession(session.session_id);
      setSessions((current) => current.filter((item) => item.session_id !== session.session_id));

      if (activeSessionId === session.session_id) {
        setActiveSessionId(null);
        setMessages([]);
        setAnswerPayload(null);
        setQuestion("");
      }
    } catch (deleteError) {
      setError(deleteError.message || "Failed to delete session.");
    } finally {
      setDeletingSessionId(null);
    }
  }
  /** Sends the current question to the chat flow. */
  async function handleAsk(event) {
    event.preventDefault();
    if (!question.trim() || isActiveSessionAtLimit) {
      return;
    }

    setSending(true);
    setError("");
    setPipelineTrace([]);
    try {
      const response = await queryChat({
        question: question.trim(),
        limit: 5,
        sessionId: activeSessionId,
        documentIds: selectedDocumentIds.length > 0 ? selectedDocumentIds : null,
      });
      setAnswerPayload(response);
      setPipelineTrace(response.pipeline_trace || []);
      setQuestion("");
      await loadSessions();
      const nextSessionId = response.session?.session_id;
      if (nextSessionId) {
        await openSession(nextSessionId, { keepAnswerPayload: true });
      }
    } catch (chatError) {
      setError(chatError.message || "Chat request failed.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="page-stack chat-page">
      <SectionHeader
        eyebrow="RAG chat"
        title="Chat with your indexed knowledge"
        description="Resume old sessions or start a fresh conversation with retrieval-backed answers and citations."
      />

      {error ? <div className="error-banner">{error}</div> : null}
      {pipelineTrace.length ? (
        <div className="success-banner">
          <strong>Pipeline trace:</strong>
          {pipelineTrace.map((step, idx) => (
            <div key={`${idx}-${step}`}>{`${idx + 1}. ${step}`}</div>
          ))}
        </div>
      ) : null}

      <section className="chat-layout">
        <SessionList
          sessions={sessions}
          activeSessionId={activeSessionId}
          loading={loadingSessions}
          deletingSessionId={deletingSessionId}
          onDelete={handleDeleteSession}
          onSelect={openSession}
          onNewChat={startNewChat}
        />

        <div className="chat-center-column">
          <ChatTranscript messages={messages} pendingAnswer={sending ? "Generating a grounded answer..." : ""} loading={loadingMessages}>
            <form className="compact-form" onSubmit={handleAsk}>
              {isActiveSessionAtLimit ? <div className="error-banner">100% chat used. Start a new chat to continue.</div> : null}
              <label>
                <span className="eyebrow">Question</span>
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask a question about your uploaded documents..."
                  disabled={isActiveSessionAtLimit}
                />
              </label>
              <div className="document-filter-box">
                <div className="document-filter-head">
                  <span className="eyebrow">Document scope</span>
                  <small>
                    {selectedDocumentIds.length > 0
                      ? `${selectedDocumentIds.length} selected`
                      : "All accessible documents"}
                  </small>
                </div>
                <div className="document-filter-actions">
                  <button
                    type="button"
                    className="ghost-button document-filter-action"
                    onClick={() => setSelectedDocumentIds(documents.map((document) => document.id))}
                    disabled={documents.length === 0}
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    className="ghost-button document-filter-action"
                    onClick={() => setSelectedDocumentIds([])}
                    disabled={selectedDocumentIds.length === 0}
                  >
                    Clear
                  </button>
                </div>
                <div className="document-filter-list">
                  {documents.length === 0 ? (
                    <small>No documents available for selection.</small>
                  ) : (
                    documents.map((document) => (
                      <label key={document.id} className="document-filter-item">
                        <input
                          type="checkbox"
                          checked={selectedDocumentIds.includes(document.id)}
                          onChange={() => toggleDocumentSelection(document.id)}
                        />
                        <span title={document.title}>{document.title}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
              <div className="composer-actions">
                <small>
                  {activeSessionId
                    ? `Continuing session ${activeSessionId} - Tokens: ${activeSession?.tokens_used_total ?? 0}${
                        typeof activeSession?.token_limit === "number" ? ` / ${activeSession.token_limit} (${activeSessionPercent}%)` : ""
                      }`
                    : "A new session will be created."}
                </small>
                <button type="submit" disabled={sending || !question.trim() || isActiveSessionAtLimit}>
                  {sending ? "Sending..." : "Ask with citations"}
                </button>
              </div>
            </form>
          </ChatTranscript>
        </div>

        <SourcePanel answerPayload={answerPayload} />
      </section>
    </div>
  );
}



