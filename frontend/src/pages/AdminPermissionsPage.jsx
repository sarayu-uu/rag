/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import { getDocuments, updateDocumentPermissions } from "../lib/api";
import { ROLE_KEYS } from "../lib/roles";

const ROLE_OPTIONS = Object.values(ROLE_KEYS);

const INITIAL_FORM = {
  user_id: "",
  role: ROLE_KEYS.VIEWER,
  can_read: true,
  can_query: true,
  can_edit: false,
};

/**
 * Detailed function explanation:
 * - Purpose: `AdminPermissionsPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function AdminPermissionsPage() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  /**
   * Detailed function explanation:
   * - Purpose: `loadDocuments` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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

  useEffect(() => {
    loadDocuments();
  }, []);

  /**
   * Detailed function explanation:
   * - Purpose: `handleSubmit` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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
      await updateDocumentPermissions(Number(selectedDocumentId), {
        user_id: form.user_id ? Number(form.user_id) : null,
        role: form.user_id ? null : form.role,
        can_read: form.can_read,
        can_query: form.can_query,
        can_edit: form.can_edit,
      });
      setSuccess(
        form.user_id
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
