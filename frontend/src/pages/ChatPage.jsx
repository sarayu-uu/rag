import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import ChatTranscript from "../components/chat/ChatTranscript";
import SessionList from "../components/chat/SessionList";
import SourcePanel from "../components/chat/SourcePanel";
import { getChatMessages, getChatSessions, queryChat } from "../lib/api";

export default function ChatPage() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [answerPayload, setAnswerPayload] = useState(null);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

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

  async function handleAsk(event) {
    event.preventDefault();
    if (!question.trim()) {
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
    <div className="page-stack">
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
          onSelect={openSession}
          onNewChat={startNewChat}
        />

        <div className="chat-center-column">
          <ChatTranscript messages={messages} pendingAnswer={sending ? "Generating a grounded answer..." : ""} loading={loadingMessages} />

          <form className="composer-card" onSubmit={handleAsk}>
            <label>
              <span className="eyebrow">Question</span>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a question about your uploaded documents..."
              />
            </label>
            <div className="composer-actions">
              <small>{activeSessionId ? `Continuing session ${activeSessionId}` : "A new session will be created."}</small>
              <button type="submit" disabled={sending || !question.trim()}>
                {sending ? "Sending..." : "Ask with citations"}
              </button>
            </div>
          </form>
        </div>

        <SourcePanel answerPayload={answerPayload} />
      </section>
    </div>
  );
}
