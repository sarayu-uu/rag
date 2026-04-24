import { useState } from "react";
import { uploadDocument, uploadDocumentsBatch } from "../../lib/api";

export default function IngestionPanel({ onIndexed }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const handleUpload = async () => {
    if (files.length === 0) {
      setError("Choose at least one file first.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data =
        files.length === 1
          ? await uploadDocument(files[0])
          : await uploadDocumentsBatch(files);
      setResult(data);
      onIndexed?.(data);
    } catch (uploadError) {
      setError(uploadError.message || "Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="ingestion-panel panel">
      <div className="panel-heading">
        <h2>1. Ingest & Index</h2>
        <p>Upload once, then ask questions across indexed chunks.</p>
      </div>

      <div className="ingestion-controls">
        <input
          type="file"
          multiple
          onChange={(event) => setFiles(Array.from(event.target.files || []))}
          disabled={loading}
        />
        <button onClick={handleUpload} disabled={loading || files.length === 0}>
          {loading ? "Indexing..." : files.length > 1 ? "Upload + Index All" : "Upload + Index"}
        </button>
      </div>

      <p className="muted-text">{files.length} file(s) selected</p>

      {error ? <p className="error-text">{error}</p> : null}

      {result ? (
        <div className="ingestion-result">
          {"total_files" in result ? (
            <>
              <p>
                <strong>Status:</strong> {result.status}
              </p>
              <p>
                <strong>Total Files:</strong> {result.total_files}
              </p>
              <p>
                <strong>Success:</strong> {result.success_count}
              </p>
              <p>
                <strong>Failed:</strong> {result.failure_count}
              </p>
              <pre>{JSON.stringify(result.results, null, 2)}</pre>
            </>
          ) : (
            <>
              <p>
                <strong>Status:</strong> {result.status}
              </p>
              <p>
                <strong>Document ID:</strong> {result.document_id}
              </p>
              <p>
                <strong>Chunks:</strong> {result.chunk_count}
              </p>
              <p>
                <strong>Vector Indexed:</strong> {result.vector_indexed ? "Yes" : "No"}
              </p>
              <p>
                <strong>Message:</strong> {result.message}
              </p>
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
