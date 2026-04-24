const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data?.detail || `Request failed (${response.status})`;
    throw new Error(detail);
  }

  return data;
}

export function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  return request("/ingestion/upload", {
    method: "POST",
    body: formData,
  });
}

export function uploadDocumentsBatch(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  return request("/ingestion/upload-batch", {
    method: "POST",
    body: formData,
  });
}

export function queryChat({ question, limit = 5, sessionId = null }) {
  const payload = {
    question,
    limit,
    ...(sessionId ? { session_id: sessionId } : {}),
  };

  return request("/chat/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function listSessions() {
  return request("/chat/sessions");
}

export function getSessionMessages(sessionId) {
  return request(`/chat/sessions/${sessionId}/messages`);
}
