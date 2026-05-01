import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import ChatTranscript from "../components/chat/ChatTranscript";
import SessionList from "../components/chat/SessionList";
import SourcePanel from "../components/chat/SourcePanel";
import { deleteChatSession, getChatMessages, getChatSessions, queryChat } from "../lib/api";

export default function ChatPage() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [answerPayload, setAnswerPayload] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState(null);
  const [error, setError] = useState("");
  const activeSession = sessions.find((session) => session.session_id === activeSessionId) || null;
  const activeSessionPercent = activeSession?.token_limit
    ? Math.min(100, Math.round(((activeSession?.tokens_used_total ?? 0) / Math.max(activeSession.token_limit, 1)) * 100))
    : 0;
  const isActiveSessionAtLimit =
    Boolean(activeSessionId) &&
    Boolean(activeSession?.token_limit) &&
    Number(activeSession?.tokens_used_total ?? 0) >= Number(activeSession?.token_limit ?? 0);

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

  useEffect(() => {
    loadSessions();
  }, []);

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

  function startNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setAnswerPayload(null);
    setQuestion("");
    setError("");
  }

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

  async function handleAsk(event) {
    event.preventDefault();
    if (!question.trim() || isActiveSessionAtLimit) {
      return;
    }

    setSending(true);
    setError("");
    try {
      const response = await queryChat({
        question: question.trim(),
        limit: 5,
        sessionId: activeSessionId,
      });
      setAnswerPayload(response);
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
