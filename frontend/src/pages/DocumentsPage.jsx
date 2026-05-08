/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import EmptyState from "../components/common/EmptyState";
import SectionHeader from "../components/common/SectionHeader";
import UploadCard from "../components/documents/UploadCard";
import { useAuth } from "../context/AuthContext";
import { deleteDocument, getDocuments, openDocumentView, uploadDocument, uploadDocumentsBatch } from "../lib/api";
import { canUpload, isManagementRole } from "../lib/roles";
/** Renders the documents management page. */
export default function DocumentsPage() {
  const { user } = useAuth();
  const showUploaderColumn = isManagementRole(user?.role);
  const [documents, setDocuments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pipelineTrace, setPipelineTrace] = useState([]);
  /** Loads documents. */
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
  /** Uploads the selected file or form data. */
  async function handleUpload(files) {
    setBusy(true);
    setError("");
    setSuccess("");
    setPipelineTrace([]);
    try {
      const selectedFiles = Array.isArray(files) ? files : [files];
      if (selectedFiles.length === 1) {
        const response = await uploadDocument({ file: selectedFiles[0] });
        setSuccess(`${response.metadata?.document_name || selectedFiles[0].name} uploaded successfully. Document ID: ${response.document_id}`);
        setPipelineTrace(response.pipeline_trace || []);
      } else {
        const response = await uploadDocumentsBatch({ files: selectedFiles });
        const successIds = (response.results || [])
          .filter((item) => item.status === "success")
          .map((item) => item.document_id)
          .filter((id) => id !== undefined && id !== null);
        setSuccess(
          `Batch upload completed. Success: ${response.success_count}, Failed: ${response.failure_count}. ` +
            `Document IDs: ${successIds.join(", ")}`
        );
        setPipelineTrace([
          "batch_upload -> /documents/upload-batch",
          "per_file_pipeline -> load -> clean -> chunk -> embed -> index",
          "document_ids_assigned -> one unique document_id per successful file",
        ]);
      }
      await loadDocuments();
    } catch (uploadError) {
      setError(uploadError.message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  }
  /** Deletes the selected document and refreshes the list. */
  async function handleDelete(documentId) {
    setBusy(true);
    setError("");
    setSuccess("");
    setPipelineTrace([]);
    try {
      const response = await deleteDocument(documentId);
      setSuccess("Document deleted successfully.");
      setPipelineTrace(response.pipeline_trace || []);
      await loadDocuments();
    } catch (deleteError) {
      setError(deleteError.message || "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleView(documentId) {
    setError("");
    try {
      await openDocumentView(documentId);
    } catch (viewError) {
      setError(viewError.message || "Failed to open document.");
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
      {pipelineTrace.length ? (
        <div className="success-banner">
          <strong>Pipeline trace:</strong>
          {pipelineTrace.map((step, idx) => (
            <div key={`${idx}-${step}`}>{`${idx + 1}. ${step}`}</div>
          ))}
        </div>
      ) : null}

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
                      className="ghost-button documents-view-button"
                      onClick={() => handleView(document.id)}
                      disabled={busy}
                    >
                      View document
                    </button>
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



