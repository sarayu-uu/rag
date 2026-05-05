/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
/** Blocks access for signed-in users on public pages. */
export default function PublicOnlyRoute() {
  const { isAuthenticated, booting } = useAuth();

  if (booting) {
    return (
      <div className="screen-state">
        <div className="state-card">
          <span className="status-dot" />
          <h1>Loading access state</h1>
          <p>Checking whether you already have an active session.</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}


