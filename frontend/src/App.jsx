import { useEffect, useMemo, useState } from "react";
import DummyAuthPage from "./components/auth/DummyAuthPage";
import IngestionPanel from "./components/ingestion/IngestionPanel";
import ChatWindow from "./components/chat/ChatWindow";
import ChatComposer from "./components/chat/ChatComposer";
import WorkspaceSidebar from "./components/layout/WorkspaceSidebar";
import DocumentsPanel from "./components/panels/DocumentsPanel";
import DummyTablePanel from "./components/panels/DummyTablePanel";
import { getSessionMessages, listSessions, queryChat } from "./lib/api";
import { getRoleDefinition, ROLE_KEYS } from "./lib/roles";

const DUMMY_TABLES = {
  users: [
    { title: "Priya Shah", subtitle: "Analyst | Active | Last login 5m ago" },
    { title: "Akash Verma", subtitle: "Editor | Active | Last login 14m ago" },
    { title: "Nina Roy", subtitle: "Viewer | Active | Last login 35m ago" },
  ],
  roles: [
    { title: "SUPER_ADMIN", subtitle: "Global governance, policy, and override access" },
    { title: "ADMIN", subtitle: "Workspace-level users, documents, and permissions" },
    { title: "EDITOR", subtitle: "Ingest, re-index, and manage knowledge quality" },
    { title: "VIEWER", subtitle: "Ask questions and consume grounded answers only" },
  ],
  permissions: [
    { title: "finance_q4.pdf", subtitle: "EDITOR: query+edit | VIEWER: query" },
    { title: "legal_policy_v2.docx", subtitle: "ADMIN: full | EDITOR: query | VIEWER: none" },
    { title: "onboarding_manual.pptx", subtitle: "All roles: query" },
  ],
  analytics: [
    { title: "Daily Queries", subtitle: "1,284 total | 98.7% successful" },
    { title: "Ingestion Throughput", subtitle: "52 files indexed in last 24h" },
    { title: "Average Response Time", subtitle: "1.84s median answer latency" },
  ],
};

export default function App() {
  const [authMode, setAuthMode] = useState("signin");
  const [authForm, setAuthForm] = useState({
    name: "Ameya",
    email: "ameya@example.com",
    password: "",
    role: ROLE_KEYS.VIEWER,
  });
  const [user, setUser] = useState(null);

  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [lastQueryInfo, setLastQueryInfo] = useState(null);
  const [activeView, setActiveView] = useState("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [indexedDocuments, setIndexedDocuments] = useState([]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.session_id === activeSessionId) || null,
    [sessions, activeSessionId]
  );
  const roleDefinition = useMemo(() => getRoleDefinition(user?.role), [user]);

  async function refreshSessions() {
    setSessionsLoading(true);
    try {
      const data = await listSessions();
      setSessions(data.sessions || []);
    } catch (sessionError) {
      setError(sessionError.message || "Failed to load sessions.");
    } finally {
      setSessionsLoading(false);
    }
  }

  async function loadSession(sessionId) {
    setMessagesLoading(true);
    setError("");
    try {
      const data = await getSessionMessages(sessionId);
      setActiveSessionId(sessionId);
      setSessionInfo({
        session_id: data.session_id,
        created: false,
      });
      setMessages(data.messages || []);
      setActiveView("chat");
    } catch (loadError) {
      setError(loadError.message || "Failed to load session messages.");
    } finally {
      setMessagesLoading(false);
    }
  }

  function startNewChat() {
    setActiveSessionId(null);
    setSessionInfo(null);
    setMessages([]);
    setLastQueryInfo(null);
    setError("");
    setActiveView("chat");
  }

  function handleRoleSubmit() {
    const roleMeta = getRoleDefinition(authForm.role);
    setUser({
      name: authForm.name.trim() || "Demo User",
      email: authForm.email.trim() || "demo@example.com",
      role: authForm.role,
      roleLabel: roleMeta.label,
    });
    setActiveView("chat");
    refreshSessions();
  }

  function handleAuthFieldChange(field, value) {
    setAuthForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  }

  function handleLogout() {
    setUser(null);
    setMessages([]);
    setSessionInfo(null);
    setActiveSessionId(null);
    setActiveView("chat");
  }

  function handleIngestionIndexed(result) {
    const records = [];

    if (result && typeof result === "object" && "results" in result && Array.isArray(result.results)) {
      for (const row of result.results) {
        if (row.status === "success") {
          records.push(row);
        }
      }
    } else if (result && typeof result === "object") {
      records.push({
        file_name: result?.metadata?.document_name || result?.metadata?.stored_as || "Document",
        document_id: result?.document_id,
        chunk_count: result?.chunk_count,
        vector_indexed: Boolean(result?.vector_indexed),
      });
    }

    if (records.length > 0) {
      setIndexedDocuments((previous) => [...records, ...previous]);
    }
  }

  async function handleSend(question, limit) {
    setSending(true);
    setError("");
    setMessages((previous) => [
      ...previous,
      {
        id: `pending-user-${Date.now()}`,
        role: "user",
        content: question,
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      const result = await queryChat({
        question,
        limit,
        sessionId: activeSessionId,
      });

      const nextSessionId = result.session?.session_id;
      setSessionInfo(result.session || null);
      setLastQueryInfo({
        retrieved_match_count: result.retrieved_match_count,
        retrieval_debug: result.retrieval_debug,
      });

      if (nextSessionId) {
        await loadSession(nextSessionId);
      }
      await refreshSessions();
    } catch (chatError) {
      setError(chatError.message || "Chat query failed.");
      setMessages((previous) =>
        previous.filter((message) => !String(message.id).startsWith("pending-user-"))
      );
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    if (user) {
      refreshSessions();
    }
  }, [user]);

  function renderMainContent() {
    if (activeView === "chat") {
      return (
        <>
          <header className="workspace-chat-header panel">
            <h1>New chat</h1>
            <p>{user.roleLabel} | {roleDefinition.description}</p>
            {error ? <p className="error-banner">{error}</p> : null}
          </header>
          <ChatWindow
            sessionInfo={sessionInfo || (activeSession ? { session_id: activeSession.session_id } : null)}
            messages={messages}
            loadingMessages={messagesLoading}
            sending={sending}
            lastQueryInfo={lastQueryInfo}
          />
          <ChatComposer disabled={sending} onSend={handleSend} />
        </>
      );
    }

    if (activeView === "documents") {
      return <DocumentsPanel documents={indexedDocuments} />;
    }

    if (activeView === "ingestion") {
      return <IngestionPanel onIndexed={handleIngestionIndexed} />;
    }

    if (activeView === "users") {
      return (
        <DummyTablePanel
          title="Users"
          description="Dummy users for role-based UI preview."
          rows={DUMMY_TABLES.users}
        />
      );
    }

    if (activeView === "roles") {
      return (
        <DummyTablePanel
          title="Role Catalog"
          description="Dummy role matrix until backend auth/authorization is wired."
          rows={DUMMY_TABLES.roles}
        />
      );
    }

    if (activeView === "permissions") {
      return (
        <DummyTablePanel
          title="Permissions"
          description="Dummy document-level ACL preview."
          rows={DUMMY_TABLES.permissions}
        />
      );
    }

    if (activeView === "analytics") {
      return (
        <DummyTablePanel
          title="Analytics"
          description="Dummy metrics panel for operational visibility."
          rows={DUMMY_TABLES.analytics}
        />
      );
    }

    return null;
  }

  if (!user) {
    return (
      <DummyAuthPage
        mode={authMode}
        form={authForm}
        onModeChange={setAuthMode}
        onFieldChange={handleAuthFieldChange}
        onSubmit={handleRoleSubmit}
      />
    );
  }

  return (
    <main className={`workspace-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <WorkspaceSidebar
        user={user}
        collapsed={sidebarCollapsed}
        activeView={activeView}
        tabs={roleDefinition.tabs}
        sessions={sessions}
        activeSessionId={activeSessionId}
        sessionsLoading={sessionsLoading}
        onViewChange={setActiveView}
        onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
        onStartNewChat={startNewChat}
        onRefreshSessions={refreshSessions}
        onSelectSession={loadSession}
        onLogout={handleLogout}
      />

      <section className={`workspace-main ${activeView === "chat" ? "" : "single-view"}`}>
        {renderMainContent()}
      </section>
    </main>
  );
}
