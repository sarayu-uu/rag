/**
 * File purpose:
 * - Renders file picker and upload button.
 * - Sends selected file to the one-step ingestion upload endpoint and shows response.
 */

import { useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

type UploadResponse = {
  status: string;
  message: string;
  document_id: number;
  chunk_count: number;
  vector_indexed: boolean;
  vector_collection?: string;
  raw_text_preview?: string;
  cleaned_text_preview?: string;
  detail?: string;
};

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string>("");

  const handleUpload = async () => {
    if (!file) {
      setError("Please choose a file first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE_URL}/ingestion/upload`, {
        method: "POST",
        body: formData,
      });

      const data = (await res.json()) as UploadResponse;

      if (!res.ok) {
        setError(data.detail || "Upload failed.");
      } else {
        setResult(data);
      }
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card">
      <input
        type="file"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <button onClick={handleUpload} disabled={loading || !file}>
        {loading ? "Uploading..." : "Upload"}
      </button>

      {error ? <p className="error">{error}</p> : null}
      {result ? (
        <div>
          <p><strong>Status:</strong> {result.status}</p>
          <p><strong>Message:</strong> {result.message}</p>
          <p><strong>Document ID:</strong> {result.document_id}</p>
          <p><strong>Chunks:</strong> {result.chunk_count}</p>
          <p><strong>Indexed In Chroma:</strong> {result.vector_indexed ? "Yes" : "No"}</p>
          {result.vector_collection ? <p><strong>Collection:</strong> {result.vector_collection}</p> : null}
          <pre>{result.cleaned_text_preview || result.raw_text_preview || ""}</pre>
        </div>
      ) : null}
    </section>
  );
}
