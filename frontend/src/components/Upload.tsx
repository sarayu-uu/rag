/**
 * File purpose:
 * - Renders file picker and upload button.
 * - Sends selected file to backend /upload and shows response.
 */

import { useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

type UploadResponse = {
  status: string;
  message: string;
  text_preview: string;
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
      const res = await fetch(`${API_BASE_URL}/upload`, {
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
          <pre>{result.text_preview}</pre>
        </div>
      ) : null}
    </section>
  );
}