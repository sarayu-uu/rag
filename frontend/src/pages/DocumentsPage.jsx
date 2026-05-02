/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import EmptyState from "../components/common/EmptyState";
import SectionHeader from "../components/common/SectionHeader";
import UploadCard from "../components/documents/UploadCard";
import { useAuth } from "../context/AuthContext";
import { deleteDocument, getDocuments, uploadDocument } from "../lib/api";
import { canUpload, isManagementRole } from "../lib/roles";

/**
 * Detailed function explanation:
 * - Purpose: `DocumentsPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function DocumentsPage() {
  const { user } = useAuth();
  const showUploaderColumn = isManagementRole(user?.role);
  const [documents, setDocuments] = useState([]);
  const [busy, setBusy] = useState(false);
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
      setDocuments(response.documents || []);
    } catch (documentsError) {
      setError(documentsError.message || "Failed to load documents.");
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  /**
   * Detailed function explanation:
   * - Purpose: `handleUpload` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
  async function handleUpload(file) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const response = await uploadDocument({ file });
      setSuccess(`${response.metadata?.document_name || file.name} uploaded successfully.`);
      await loadDocuments();
    } catch (uploadError) {
      setError(uploadError.message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  /**
   * Detailed function explanation:
   * - Purpose: `handleDelete` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
  async function handleDelete(documentId) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await deleteDocument(documentId);
      setSuccess("Document deleted successfully.");
      await loadDocuments();
    } catch (deleteError) {
      setError(deleteError.message || "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Knowledge base"
        title="Documents"
        description="Upload, inspect, and remove indexed material connected to the RAG workspace."
      />

      {error ? <div className="error-banner">{error}</div> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      <section className="content-grid sidebar-layout">
        <UploadCard canUpload={canUpload(user?.role)} onUpload={handleUpload} busy={busy} />

        <section className="feature-card table-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Indexed inventory</p>
              <h2>Available documents</h2>
            </div>
          </div>

          {documents.length === 0 ? (
            <EmptyState
              title="No files yet"
              message="Once you upload a document, it will appear here with status and quick actions."
            />
          ) : (
            <div className="table-shell">
              <div className={`table-row table-head documents-row ${showUploaderColumn ? "with-uploader" : ""}`}>
                <span>Name</span>
                <span>Type</span>
                {showUploaderColumn ? <span>Uploaded by</span> : null}
                <span>Status</span>
                <span>Uploaded</span>
                <span>Action</span>
              </div>
              {documents.map((document) => (
                <div key={document.id} className={`table-row documents-row ${showUploaderColumn ? "with-uploader" : ""}`}>
                  <span>{document.title}</span>
                  <span>{document.file_type}</span>
                  {showUploaderColumn ? (
                    <span>
                      {document.uploader?.name || "Unknown"} ({document.uploader?.position || "Unknown"})
                    </span>
                  ) : null}
                  <span>{document.status}</span>
                  <span>{new Date(document.uploaded_at).toLocaleDateString()}</span>
                  <span className="documents-action-cell">
                    <button
                      className="ghost-button danger-button documents-delete-button"
                      onClick={() => handleDelete(document.id)}
                      disabled={busy}
                    >
                      Delete
                    </button>
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </section>
    </div>
  );
}
