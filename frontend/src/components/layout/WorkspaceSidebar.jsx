const TAB_LABELS = {
  chat: "Chat",
  documents: "View Documents",
  ingestion: "Ingestion",
  users: "Users",
  roles: "Roles",
  permissions: "Permissions",
  analytics: "Analytics",
};

export default function WorkspaceSidebar({
  user,
  collapsed,
  activeView,
  tabs,
  sessions,
  activeSessionId,
  sessionsLoading,
  onViewChange,
  onToggleCollapse,
  onStartNewChat,
  onRefreshSessions,
  onSelectSession,
  onLogout,
}) {
  return (
    <aside className="workspace-sidebar panel">
      <button className="collapse-btn ghost-btn" onClick={onToggleCollapse}>
        {collapsed ? ">>" : "<<"}
      </button>

      <section className="user-card">
        <p className="user-role">{user.roleLabel}</p>
        <h2>{collapsed ? user.name.slice(0, 1).toUpperCase() : user.name}</h2>
        {!collapsed ? <p className="muted-text">{user.email}</p> : null}
        <button className="ghost-btn" onClick={onLogout}>
          {collapsed ? "Role" : "Switch Role"}
        </button>
      </section>

      <button className="new-chat-btn" onClick={onStartNewChat}>
        {collapsed ? "+" : "+ New Chat"}
      </button>

      <nav className="sidebar-tabs">
        {tabs.map((tabKey) => (
          <button
            key={tabKey}
            className={activeView === tabKey ? "tab-btn active" : "tab-btn"}
            onClick={() => onViewChange(tabKey)}
            title={TAB_LABELS[tabKey] || tabKey}
          >
            {collapsed ? (TAB_LABELS[tabKey] || tabKey).slice(0, 1) : TAB_LABELS[tabKey] || tabKey}
          </button>
        ))}
      </nav>

      <section className="sidebar-sessions">
        <header>
          {!collapsed ? <h3>Sessions</h3> : <h3>Chats</h3>}
          <button className="ghost-btn" onClick={onRefreshSessions} disabled={sessionsLoading}>
            {sessionsLoading ? "..." : collapsed ? "R" : "Refresh"}
          </button>
        </header>
        <div className="sidebar-session-list">
          {sessions.length === 0 ? (
            <p className="muted-text">{collapsed ? "-" : "No sessions"}</p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.session_id}
                className={activeSessionId === session.session_id ? "session-chip active" : "session-chip"}
                onClick={() => onSelectSession(session.session_id)}
                title={session.title || `Session ${session.session_id}`}
              >
                <span>
                  {collapsed
                    ? `#${session.session_id}`
                    : session.title || `Session ${session.session_id}`}
                </span>
                {!collapsed ? <small>#{session.session_id}</small> : null}
              </button>
            ))
          )}
        </div>
      </section>
    </aside>
  );
}
