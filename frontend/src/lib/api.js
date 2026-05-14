/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { ROLE_KEYS } from "./roles";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const STORAGE_KEY = "rag_auth_tokens";

let authStore = {
  accessToken: "",
  refreshToken: "",
};
/** Gets saved auth tokens from local storage. */
export function getStoredTokens() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { accessToken: "", refreshToken: "" };
    }

    const parsed = JSON.parse(raw);
    return {
      accessToken: parsed?.accessToken || "",
      refreshToken: parsed?.refreshToken || "",
    };
  } catch {
    return { accessToken: "", refreshToken: "" };
  }
}
/** Saves auth tokens to local storage and memory. */
export function setStoredTokens(tokens) {
  authStore = {
    accessToken: tokens?.accessToken || "",
    refreshToken: tokens?.refreshToken || "",
  };

  if (!authStore.accessToken && !authStore.refreshToken) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(authStore));
}

authStore = getStoredTokens();
/** Parses an API response and raises an error for failed requests. */
async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    let detail = data?.detail || data?.message || `Request failed (${response.status})`;
    if (Array.isArray(detail)) {
      detail = detail
        .map((item) => {
          if (typeof item === "string") {
            return item;
          }
          if (item?.msg) {
            return item.msg;
          }
          return JSON.stringify(item);
        })
        .join("; ");
    } else if (detail && typeof detail === "object") {
      detail = detail.msg || detail.message || JSON.stringify(detail);
    } else if (detail !== null && detail !== undefined) {
      detail = String(detail);
    }

    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    error.payload = data;
    throw error;
  }
  return data;
}
/** Requests a new access token using the refresh token. */
async function refreshAccessToken() {
  if (!authStore.refreshToken) {
    throw new Error("No refresh token available.");
  }

  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: authStore.refreshToken }),
  });
  const data = await parseResponse(response);
  setStoredTokens({
    accessToken: data.access_token,
    refreshToken: data.refresh_token || authStore.refreshToken,
  });
  return authStore.accessToken;
}
/** Sends an API request and retries once after token refresh. */
async function request(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (authStore.accessToken) {
    headers.set("Authorization", `Bearer ${authStore.accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && retry && authStore.refreshToken) {
    try {
      await refreshAccessToken();
      return request(path, options, false);
    } catch (refreshError) {
      setStoredTokens(null);
      throw refreshError;
    }
  }

  return parseResponse(response);
}

async function requestBlob(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  if (authStore.accessToken) {
    headers.set("Authorization", `Bearer ${authStore.accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    redirect: "follow",
  });

  if (response.status === 401 && retry && authStore.refreshToken) {
    try {
      await refreshAccessToken();
      return requestBlob(path, options, false);
    } catch (refreshError) {
      setStoredTokens(null);
      throw refreshError;
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    let detail = data?.detail || data?.message || `Request failed (${response.status})`;
    if (Array.isArray(detail)) {
      detail = detail
        .map((item) => {
          if (typeof item === "string") {
            return item;
          }
          if (item?.msg) {
            return item.msg;
          }
          return JSON.stringify(item);
        })
        .join("; ");
    } else if (detail && typeof detail === "object") {
      detail = detail.msg || detail.message || JSON.stringify(detail);
    } else if (detail !== null && detail !== undefined) {
      detail = String(detail);
    }

    const error = new Error(detail || `Request failed (${response.status})`);
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return response.blob();
}
/** Normalizes role into a consistent format. */
export function normalizeRole(role) {
  return role || ROLE_KEYS.VIEWER;
}
/** Signs up a new user. */
export async function signup(payload) {
  return request("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
/** Verifies otp. */
export async function verifyOtp(payload) {
  return request("/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
/** Logs the user in. */
export async function login(payload) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
/** Gets me. */
export async function getMe() {
  return request("/auth/me", {
    method: "GET",
  });
}
/** Gets health. */
export async function getHealth() {
  return request("/health", {
    method: "GET",
  });
}
/** Gets metrics. */
export async function getMetrics() {
  return request("/metrics", {
    method: "GET",
  });
}
/** Gets telemetry. */
export async function getTelemetry({ hours = 24 } = {}) {
  return request(`/telemetry?hours=${hours}`, {
    method: "GET",
  });
}
/** Gets documents. */
export async function getDocuments() {
  return request("/documents", {
    method: "GET",
  });
}
/** Gets document. */
export async function getDocument(documentId) {
  return request(`/documents/${documentId}`, {
    method: "GET",
  });
}
/** Deletes document. */
export async function deleteDocument(documentId) {
  return request(`/documents/${documentId}`, {
    method: "DELETE",
  });
}
/** Opens a document in a new browser tab using authenticated download. */
export async function openDocumentView(documentId) {
  const blob = await requestBlob(`/documents/${documentId}/view`, {
    method: "GET",
  });
  const blobUrl = URL.createObjectURL(blob);
  window.open(blobUrl, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}
/** Uploads a document file or URL. */
export async function uploadDocument({ file = null, url = "", chunkSize = 500, chunkOverlap = 100, permissionsTags = [] }) {
  const formData = new FormData();
  if (file) {
    formData.append("file", file);
  } else if (url && String(url).trim()) {
    formData.append("url", String(url).trim());
  } else {
    throw new Error("Provide either a file or a URL to upload.");
  }
  formData.append("chunk_size", String(chunkSize));
  formData.append("chunk_overlap", String(chunkOverlap));
  formData.append("permissions_tags", JSON.stringify(permissionsTags));

  return request("/documents/upload", {
    method: "POST",
    body: formData,
  });
}
/** Uploads multiple documents. */
export async function uploadDocumentsBatch({ files, chunkSize = 500, chunkOverlap = 100, permissionsTags = [] }) {
  const formData = new FormData();
  for (const file of files || []) {
    formData.append("files", file);
  }
  formData.append("chunk_size", String(chunkSize));
  formData.append("chunk_overlap", String(chunkOverlap));
  formData.append("permissions_tags", JSON.stringify(permissionsTags));

  return request("/documents/upload-batch", {
    method: "POST",
    body: formData,
  });
}
/** Gets chat sessions. */
export async function getChatSessions() {
  return request("/chat/sessions", {
    method: "GET",
  });
}
/** Gets chat messages. */
export async function getChatMessages(sessionId) {
  return request(`/chat/sessions/${sessionId}/messages`, {
    method: "GET",
  });
}
/** Deletes chat session. */
export async function deleteChatSession(sessionId) {
  return request(`/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}
/** Sends a question to the chat API. */
export async function queryChat({ question, limit = 5, sessionId = null, documentIds = null }) {
  const payload = {
    question,
    limit,
    ...(Array.isArray(documentIds) ? { document_ids: documentIds } : {}),
    ...(sessionId ? { session_id: sessionId } : {}),
  };
  return request("/chat/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
/** Runs the answer quality evaluation request. */
export async function evaluateQualityReport({ question, groundTruth = "", limit = 5, includeRagas = true }) {
  const payload = {
    question,
    limit,
    include_ragas: Boolean(includeRagas),
    ...(groundTruth.trim() ? { ground_truth: groundTruth.trim() } : {}),
  };
  return request("/test/evaluate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
/** Gets users. */
export async function getUsers() {
  return request("/admin/users", {
    method: "GET",
  });
}
/** Updates user role. */
export async function updateUserRole(userId, role, managerUserId = null) {
  return request(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({
      role,
      manager_user_id: managerUserId,
    }),
  });
}
/** Deletes user. */
export async function deleteUser(userId) {
  return request(`/admin/users/${userId}`, {
    method: "DELETE",
  });
}
/** Gets one user's usage insights for admin controls. */
export async function getUserUsageDetails(userId) {
  return request(`/admin/users/${userId}/usage`, {
    method: "GET",
  });
}
/** Updates document permissions. */
export async function updateDocumentPermissions(documentId, payload) {
  return request(`/admin/documents/${documentId}/permissions`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}



