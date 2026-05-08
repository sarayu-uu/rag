/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import { getDocuments, getUsers, updateDocumentPermissions } from "../lib/api";
import { ROLE_KEYS } from "../lib/roles";
import { useAuth } from "../context/AuthContext";

const ROLE_OPTIONS = Object.values(ROLE_KEYS);

const INITIAL_FORM = {
  user_id: "",
  role: ROLE_KEYS.VIEWER,
  analyst_scope: "single",
  can_read: true,
  can_query: true,
  can_edit: false,
};
/** Renders the document permissions admin page. */
export default function AdminPermissionsPage() {
  const { user: currentUser } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [users, setUsers] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  /** Loads documents. */
  async function loadDocuments() {
    try {
      const response = await getDocuments();
      const docs = response.documents || [];
      setDocuments(docs);
      if (!selectedDocumentId && docs[0]?.id) {
        setSelectedDocumentId(String(docs[0].id));
      }
    } catch (documentsError) {
      setError(documentsError.message || "Failed to load documents.");
    }
  }
  /** Loads users for manager analyst targeting. */
  async function loadUsers() {
    try {
      const response = await getUsers();
      setUsers(response.users || []);
    } catch {
      setUsers([]);
    }
  }

  useEffect(() => {
    loadDocuments();
    loadUsers();
  }, []);

  const isManager = currentUser?.role === ROLE_KEYS.MANAGER;
  const teamAnalysts = users.filter(
    (item) => item.role === ROLE_KEYS.ANALYST && Number(item.manager_user_id) === Number(currentUser?.id)
  );
  const managerAnalystMode = isManager && form.role === ROLE_KEYS.ANALYST;

  /** Submits the current form action. */
  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedDocumentId) {
      setError("Choose a document first.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const useAllTeamAnalysts = managerAnalystMode && form.analyst_scope === "all_team";
      if (managerAnalystMode && !useAllTeamAnalysts && !form.user_id) {
        setError("Choose one analyst from your team, or select all team analysts.");
        setSubmitting(false);
        return;
      }

      await updateDocumentPermissions(Number(selectedDocumentId), {
        all_team_analysts: useAllTeamAnalysts,
        user_id: useAllTeamAnalysts ? null : form.user_id ? Number(form.user_id) : null,
        role: useAllTeamAnalysts || form.user_id ? null : form.role,
        can_read: form.can_read,
        can_query: form.can_query,
        can_edit: form.can_edit,
      });
      setSuccess(
        useAllTeamAnalysts
          ? "Permission rule applied for all analysts in your team."
          : form.user_id
          ? "User permission rule updated successfully."
          : `${form.role} role permission rule updated successfully.`
      );
    } catch (permissionError) {
      setError(permissionError.message || "Failed to update permissions.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Governance"
        title="Document permissions"
        description="Grant a selected file to a role or a specific user for reading and chat retrieval."
      />

      {error ? <div className="error-banner">{error}</div> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      <section className="content-grid sidebar-layout">
        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Target</p>
              <h2>Select a document</h2>
            </div>
          </div>
          <div className="document-selector-list">
            {documents.map((document) => (
              <button
                key={document.id}
                className={`session-row ${String(document.id) === selectedDocumentId ? "active" : ""}`}
                onClick={() => setSelectedDocumentId(String(document.id))}
              >
                <strong>{document.title}</strong>
                <span>{document.file_type} | {document.status}</span>
              </button>
            ))}
          </div>
        </article>

        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Policy patch</p>
              <h2>Update permission rule</h2>
            </div>
          </div>

          <form className="auth-form compact-form" onSubmit={handleSubmit}>
            <label>
              <span>User ID</span>
              <input
                type="number"
                value={form.user_id}
                onChange={(event) => setForm((value) => ({ ...value, user_id: event.target.value }))}
                placeholder="Optional. Leave blank to grant by role."
                disabled={managerAnalystMode && form.analyst_scope === "all_team"}
              />
            </label>

            <label>
              <span>Role</span>
              <select
                value={form.role}
                onChange={(event) => setForm((value) => ({ ...value, role: event.target.value }))}
                disabled={Boolean(form.user_id)}
              >
                {ROLE_OPTIONS.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </label>

            {managerAnalystMode ? (
              <>
                <label>
                  <span>Analyst scope</span>
                  <select
                    value={form.analyst_scope}
                    onChange={(event) =>
                      setForm((value) => ({
                        ...value,
                        analyst_scope: event.target.value,
                        user_id: event.target.value === "all_team" ? "" : value.user_id,
                      }))
                    }
                  >
                    <option value="single">One analyst in my team</option>
                    <option value="all_team">All analysts in my team</option>
                  </select>
                </label>

                {form.analyst_scope === "single" ? (
                  <label>
                    <span>Team analyst</span>
                    <select
                      value={form.user_id}
                      onChange={(event) => setForm((value) => ({ ...value, user_id: event.target.value }))}
                    >
                      <option value="">Select analyst</option>
                      {teamAnalysts.map((analyst) => (
                        <option key={analyst.id} value={analyst.id}>
                          {analyst.username} ({analyst.email})
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </>
            ) : null}

            <label className="toggle-row">
              <input
                type="checkbox"
                checked={form.can_read}
                onChange={(event) => setForm((value) => ({ ...value, can_read: event.target.checked }))}
              />
              <span>Can read</span>
            </label>

            <label className="toggle-row">
              <input
                type="checkbox"
                checked={form.can_query}
                onChange={(event) => setForm((value) => ({ ...value, can_query: event.target.checked }))}
              />
              <span>Can query</span>
            </label>

            <label className="toggle-row">
              <input
                type="checkbox"
                checked={form.can_edit}
                onChange={(event) => setForm((value) => ({ ...value, can_edit: event.target.checked }))}
              />
              <span>Can edit</span>
            </label>

            <button type="submit" disabled={submitting}>
              {submitting ? "Updating..." : "Apply permission rule"}
            </button>
          </form>
        </article>
      </section>
    </div>
  );
}



