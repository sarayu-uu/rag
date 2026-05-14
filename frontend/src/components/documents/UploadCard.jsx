/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useState } from "react";
/** Uploads card. */
export default function UploadCard({ canUpload, onUpload, busy }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [urlValue, setUrlValue] = useState("");
  /** Submits the current form action. */
  async function handleSubmit(event) {
    event.preventDefault();
    if (!canUpload) {
      return;
    }
    const trimmedUrl = urlValue.trim();
    if (trimmedUrl) {
      await onUpload({ type: "url", url: trimmedUrl });
      setUrlValue("");
      setSelectedFiles([]);
      event.target.reset();
      return;
    }
    if (selectedFiles.length === 0) {
      return;
    }
    await onUpload({ type: "files", files: selectedFiles });
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
        Push PDFs, DOCX files, PPTX decks, and other supported sources, or provide a URL, into the retrieval workspace.
      </p>

      <form className="upload-form" onSubmit={handleSubmit}>
        <label>
          <span className="eyebrow">Source URL (optional)</span>
          <input
            type="url"
            placeholder="https://example.com/article"
            value={urlValue}
            onChange={(event) => setUrlValue(event.target.value)}
            disabled={!canUpload || busy || selectedFiles.length > 0}
          />
          <small>If URL is provided, file selection is ignored for this submission.</small>
        </label>

        <label className="dropzone">
          <span>Select a document</span>
          <input
            type="file"
            multiple
            onChange={(event) => setSelectedFiles(Array.from(event.target.files || []))}
            disabled={!canUpload || busy || urlValue.trim().length > 0}
          />
          <small>
            {selectedFiles.length > 0
              ? `${selectedFiles.length} file(s) selected`
              : "Choose one or more files to upload and index, or enter a URL above."}
          </small>
        </label>

        <button
          type="submit"
          disabled={!canUpload || (selectedFiles.length === 0 && urlValue.trim().length === 0) || busy}
        >
          {busy ? "Uploading..." : "Upload to knowledge base"}
        </button>
      </form>
    </section>
  );
}


