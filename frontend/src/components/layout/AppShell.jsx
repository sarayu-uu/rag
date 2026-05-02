/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMemo, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { getRoleDefinition, isManagementRole } from "../../lib/roles";

const NAV_ITEMS = [
  { key: "dashboard", label: "Overview", to: "/dashboard", accent: "signal" },
  { key: "documents", label: "Documents", to: "/documents", accent: "document" },
  { key: "chat", label: "Workspace", to: "/chat", accent: "chat" },
  { key: "telemetry", label: "Telemetry", to: "/telemetry", accent: "admin" },
  { key: "profile", label: "Profile", to: "/profile", accent: "profile" },
  { key: "users", label: "Users", to: "/admin/users", accent: "admin" },
  { key: "permissions", label: "Permissions", to: "/admin/permissions", accent: "policy" },
];

/**
 * Detailed function explanation:
 * - Purpose: `ShellIcon` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function ShellIcon({ children }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="nav-icon">
      {children}
    </svg>
  );
}

const NAV_ICONS = {
  dashboard: (
    <ShellIcon>
      <path d="M4 13h7V4H4zm9 7h7V11h-7zm0-16v5h7V4zM4 20h7v-5H4z" fill="currentColor" />
    </ShellIcon>
  ),
  documents: (
    <ShellIcon>
      <path d="M7 3h7l5 5v13H7z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M14 3v5h5" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </ShellIcon>
  ),
  chat: (
    <ShellIcon>
      <path d="M5 6h14v9H9l-4 4z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </ShellIcon>
  ),
  profile: (
    <ShellIcon>
      <circle cx="12" cy="8.2" r="3.1" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5.5 19c.8-2.6 3.1-4.1 6.5-4.1s5.7 1.5 6.5 4.1" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </ShellIcon>
  ),
  users: (
    <ShellIcon>
      <circle cx="9" cy="9" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="16.5" cy="10" r="2.3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4 19c0-2.3 2.2-4 5-4s5 1.7 5 4" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </ShellIcon>
  ),
  permissions: (
    <ShellIcon>
      <rect x="4" y="10" width="16" height="10" rx="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8 10V7a4 4 0 118 0v3" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </ShellIcon>
  ),
  telemetry: (
    <ShellIcon>
      <path d="M4 18h16M7 15V9m5 6V6m5 9v-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </ShellIcon>
  ),
};

/**
 * Detailed function explanation:
 * - Purpose: `AppShell` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function AppShell() {
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const roleDefinition = getRoleDefinition(user?.role);

  const allowedItems = useMemo(() => {
    return NAV_ITEMS.filter((item) => {
      if (item.key === "users" || item.key === "permissions" || item.key === "telemetry") {
        return isManagementRole(user?.role);
      }
      return roleDefinition.navigation.includes(item.key);
    });
  }, [roleDefinition.navigation, user?.role]);

  const activeLabel = useMemo(() => {
    const match = allowedItems.find((item) => location.pathname.startsWith(item.to));
    return match?.label || "Workspace";
  }, [allowedItems, location.pathname]);
  const isChatRoute = location.pathname.startsWith("/chat");

  /**
   * Detailed function explanation:
   * - Purpose: `handleLogout` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
  function handleLogout() {
    signOut();
    navigate("/login");
  }

  return (
    <div className={`app-shell ${menuOpen ? "menu-open" : ""} ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="app-sidebar">
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarCollapsed((value) => !value)}
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ShellIcon>
            <path
              d={sidebarCollapsed ? "M9 6l6 6-6 6" : "M15 6l-6 6 6 6"}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </ShellIcon>
        </button>

        <div className="brand-mark">
          <div className="brand-badge">RG</div>
          <div className="brand-copy">
            <p className="eyebrow">Grounded AI Workspace</p>
            <h1>WHAT?, you ask?</h1>
          </div>
        </div>

        <div className="sidebar-card">
          <div className="sidebar-card-copy">
            <p className="eyebrow">Signed in as</p>
            <h2>{user?.username}</h2>
            <p>{user?.email}</p>
            <div className="role-chip">{roleDefinition.label}</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {allowedItems.map((item) => (
            <NavLink
              key={item.key}
              to={item.to}
              className={({ isActive }) => `nav-item nav-${item.accent} ${isActive ? "active" : ""}`}
              onClick={() => setMenuOpen(false)}
              title={item.label}
            >
              <span className="nav-icon-wrap">{NAV_ICONS[item.key]}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <p>{roleDefinition.description}</p>
          <button className="ghost-button" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </aside>

      <div className="app-stage">
        <header className="topbar">
          <div>
            <p className="eyebrow">Current section</p>
            <h2>{activeLabel}</h2>
          </div>
          <div className="topbar-actions">
            <div className="status-chip">
              <span className="status-dot" />
              <span>FastAPI connected</span>
            </div>
            <button className="ghost-button mobile-menu-button" onClick={() => setMenuOpen((value) => !value)}>
              {menuOpen ? "Close" : "Menu"}
            </button>
          </div>
        </header>

        <main className={`app-content ${isChatRoute ? "app-content-chat" : ""}`}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
