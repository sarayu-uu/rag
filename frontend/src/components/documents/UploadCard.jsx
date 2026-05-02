/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useState } from "react";

/**
 * Detailed function explanation:
 * - Purpose: `UploadCard` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function UploadCard({ canUpload, onUpload, busy }) {
  const [selectedFile, setSelectedFile] = useState(null);

  /**
   * Detailed function explanation:
   * - Purpose: `handleSubmit` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedFile || !canUpload) {
      return;
    }
    await onUpload(selectedFile);
    setSelectedFile(null);
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
            onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
            disabled={!canUpload || busy}
          />
          <small>{selectedFile ? selectedFile.name : "Choose one file to upload and index."}</small>
        </label>

        <button type="submit" disabled={!canUpload || !selectedFile || busy}>
          {busy ? "Uploading..." : "Upload to knowledge base"}
        </button>
      </form>
    </section>
  );
}
