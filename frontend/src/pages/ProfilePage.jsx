/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import SectionHeader from "../components/common/SectionHeader";
import { useAuth } from "../context/AuthContext";
import { getRoleDefinition } from "../lib/roles";
/** Renders the current user profile page. */
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
              <span>User ID</span>
              <strong>{user?.id ?? "-"}</strong>
            </div>
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
          </div>
        </article>
      </section>
    </div>
  );
}


