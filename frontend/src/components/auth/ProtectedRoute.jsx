/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

/**
 * Detailed function explanation:
 * - Purpose: `ProtectedRoute` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function ProtectedRoute({ roles = [] }) {
  const { user, booting, isAuthenticated } = useAuth();
  const location = useLocation();

  if (booting) {
    return (
      <div className="screen-state">
        <div className="state-card">
          <span className="status-dot" />
          <h1>Preparing workspace</h1>
          <p>Restoring your session and reconnecting to the RAG platform.</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (roles.length > 0 && !roles.includes(user?.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
