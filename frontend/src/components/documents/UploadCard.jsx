/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useState } from "react";
/** Uploads card. */
export default function UploadCard({ canUpload, onUpload, busy }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  /** Submits the current form action. */
  async function handleSubmit(event) {
    event.preventDefault();
    if (selectedFiles.length === 0 || !canUpload) {
      return;
    }
    await onUpload(selectedFiles);
    setSelectedFiles([]);
    event.target.reset();
  }

  return (
    <section className="feature-card">
      <div className="feature-card-header">
        <div>
          <p className="eyebrow">Ingestion</p>
          <h2>Upload a fresh source</h2>
        </div>
        <span className={`pill ${canUpload ? "pill-success" : "pill-muted"}`}>
          {canUpload ? "Enabled" : "Read only"}
        </span>
      </div>
      <p className="section-copy">
        Push PDFs, DOCX files, PPTX decks, and other supported sources into the retrieval workspace.
      </p>

      <form className="upload-form" onSubmit={handleSubmit}>
        <label className="dropzone">
          <span>Select a document</span>
          <input
            type="file"
            multiple
            onChange={(event) => setSelectedFiles(Array.from(event.target.files || []))}
            disabled={!canUpload || busy}
          />
          <small>
            {selectedFiles.length > 0
              ? `${selectedFiles.length} file(s) selected`
              : "Choose one or more files to upload and index."}
          </small>
        </label>

        <button type="submit" disabled={!canUpload || selectedFiles.length === 0 || busy}>
          {busy ? "Uploading..." : "Upload to knowledge base"}
        </button>
      </form>
    </section>
  );
}


