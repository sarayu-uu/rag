/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

const TAB_LABELS = {
  documents: "View Documents",
  ingestion: "Ingestions",
  users: "Users",
  roles: "Roles",
  permissions: "Permissions",
  analytics: "Analytics",
};

/**
 * Detailed function explanation:
 * - Purpose: `Icon` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function Icon({ children }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="sidebar-icon">
      {children}
    </svg>
  );
}

const TAB_ICONS = {
  documents: (
    <Icon>
      <path d="M7 3h7l5 5v13H7z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M14 3v5h5" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </Icon>
  ),
  ingestion: (
    <Icon>
      <path d="M12 4v10" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8 8l4-4 4 4" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <rect x="5" y="14" width="14" height="6" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </Icon>
  ),
  users: (
    <Icon>
      <circle cx="9" cy="9" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="16" cy="10" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4 19c0-2.3 2.2-4 5-4s5 1.7 5 4" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </Icon>
  ),
  roles: (
    <Icon>
      <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 12l2 2 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </Icon>
  ),
  permissions: (
    <Icon>
      <rect x="4" y="10" width="16" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8 10V7a4 4 0 118 0v3" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </Icon>
  ),
  analytics: (
    <Icon>
      <path d="M5 19V9M12 19V5M19 19v-7" stroke="currentColor" strokeWidth="1.8" />
    </Icon>
  ),
};

/**
 * Detailed function explanation:
 * - Purpose: `getTabsLayout` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function getTabsLayout(tabs, collapsed) {
  if (collapsed) return "layout-stack";
  const tabSet = new Set(tabs);

  if (tabs.length === 1 && tabSet.has("documents")) {
    return "layout-docs-only";
  }

  if (tabs.length === 2 && tabSet.has("documents") && tabSet.has("ingestion")) {
    return "layout-editor-two";
  }

  if (
    tabs.length === 5 &&
    tabSet.has("documents") &&
    tabSet.has("ingestion") &&
    tabSet.has("users") &&
    tabSet.has("permissions") &&
    tabSet.has("analytics")
  ) {
    return "layout-docs-plus-grid";
  }

  return "layout-stack";
}

/**
 * Detailed function explanation:
 * - Purpose: `WorkspaceSidebar` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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
  const tabsLayout = getTabsLayout(tabs, collapsed);

  return (
    <aside className="workspace-sidebar panel">
      <button className="collapse-btn ghost-btn icon-btn" onClick={onToggleCollapse} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
        {collapsed ? (
          <Icon>
            <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.8" />
          </Icon>
        ) : (
          <Icon>
            <path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" strokeWidth="1.8" />
          </Icon>
        )}
      </button>

      <section className="user-card">
        {!collapsed ? <p className="user-role">{user.roleLabel}</p> : null}
        <h2>
          {collapsed ? (
            <Icon>
              <circle cx="12" cy="8.5" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
              <path d="M5.5 19c.7-2.5 3-4 6.5-4s5.8 1.5 6.5 4" fill="none" stroke="currentColor" strokeWidth="1.8" />
            </Icon>
          ) : (
            user.name
          )}
        </h2>
        {!collapsed ? <p className="muted-text">{user.email}</p> : null}
        <button className={`ghost-btn ${collapsed ? "icon-btn" : ""}`} onClick={onLogout} title="Switch role">
          {collapsed ? (
            <Icon>
              <path d="M10 5H5v14h5" fill="none" stroke="currentColor" strokeWidth="1.8" />
              <path d="M14 8l5 4-5 4M19 12H9" fill="none" stroke="currentColor" strokeWidth="1.8" />
            </Icon>
          ) : (
            "Switch Role"
          )}
        </button>
      </section>

      <button className={`new-chat-btn ${collapsed ? "icon-btn" : ""}`} onClick={onStartNewChat} title="New chat">
        {collapsed ? (
          <Icon>
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" />
          </Icon>
        ) : (
          "+ New Chat"
        )}
      </button>

      <nav className={`sidebar-tabs ${tabsLayout}`}>
        {tabs.map((tabKey) => (
          <button
            key={tabKey}
            className={`${activeView === tabKey ? "tab-btn active" : "tab-btn"} ${collapsed ? "icon-btn" : ""} ${tabKey === "documents" ? "is-documents" : ""}`}
            onClick={() => onViewChange(tabKey)}
            title={TAB_LABELS[tabKey] || tabKey}
          >
            {collapsed ? TAB_ICONS[tabKey] : TAB_LABELS[tabKey] || tabKey}
          </button>
        ))}
      </nav>

      <section className={`sidebar-sessions ${collapsed ? "collapsed-hidden" : ""}`}>
        <header>
          <h3>Sessions</h3>
          <button className="ghost-btn" onClick={onRefreshSessions} disabled={sessionsLoading}>
            {sessionsLoading ? "..." : "Refresh"}
          </button>
        </header>
        <div className="sidebar-session-list">
          {sessions.length === 0 ? (
            <p className="muted-text">No sessions</p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.session_id}
                className={activeSessionId === session.session_id ? "session-chip active" : "session-chip"}
                onClick={() => onSelectSession(session.session_id)}
                title={session.title || `Session ${session.session_id}`}
              >
                <span>{session.title || `Session ${session.session_id}`}</span>
                <small>#{session.session_id}</small>
              </button>
            ))
          )}
        </div>
      </section>
    </aside>
  );
}
