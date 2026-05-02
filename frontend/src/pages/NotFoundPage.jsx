/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { Link } from "react-router-dom";

/**
 * Detailed function explanation:
 * - Purpose: `NotFoundPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function NotFoundPage() {
  return (
    <div className="screen-state">
      <div className="state-card">
        <p className="eyebrow">404</p>
        <h1>That page does not exist.</h1>
        <p>The route you tried to open is not part of this frontend workspace.</p>
        <Link className="inline-link-button" to="/dashboard">
          Go to dashboard
        </Link>
      </div>
    </div>
  );
}
