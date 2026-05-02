/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import SectionHeader from "../components/common/SectionHeader";
import { useAuth } from "../context/AuthContext";
import { getRoleDefinition } from "../lib/roles";

/**
 * Detailed function explanation:
 * - Purpose: `ProfilePage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function ProfilePage() {
  const { user } = useAuth();
  const role = getRoleDefinition(user?.role);

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Identity"
        title="Profile"
        description="A quick snapshot of the currently authenticated user and their role posture."
      />

      <section className="content-grid two-up">
        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Account</p>
              <h2>Current user</h2>
            </div>
          </div>
          <div className="profile-grid">
            <div>
              <span>Username</span>
              <strong>{user?.username}</strong>
            </div>
            <div>
              <span>Email</span>
              <strong>{user?.email}</strong>
            </div>
            <div>
              <span>Role</span>
              <strong>{role.label}</strong>
            </div>
            <div>
              <span>Active</span>
              <strong>{String(user?.is_active)}</strong>
            </div>
          </div>
        </article>

        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Role summary</p>
              <h2>{role.label}</h2>
            </div>
          </div>
          <p className="section-copy">{role.description}</p>
          <div className="role-chip large">{role.tone}</div>
        </article>
      </section>
    </div>
  );
}
