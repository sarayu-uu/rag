/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

/**
 * Detailed function explanation:
 * - Purpose: `PublicOnlyRoute` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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
