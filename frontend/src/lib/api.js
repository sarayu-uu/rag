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

/**
 * Detailed function explanation:
 * - Purpose: `getStoredTokens` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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

/**
 * Detailed function explanation:
 * - Purpose: `setStoredTokens` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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

/**
 * Detailed function explanation:
 * - Purpose: `parseResponse` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || data?.message || `Request failed (${response.status})`;
    const error = new Error(detail);
    error.status = response.status;
    error.payload = data;
    throw error;
  }
  return data;
}

/**
 * Detailed function explanation:
 * - Purpose: `refreshAccessToken` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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

/**
 * Detailed function explanation:
 * - Purpose: `request` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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

/**
 * Detailed function explanation:
 * - Purpose: `normalizeRole` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export function normalizeRole(role) {
  return role || ROLE_KEYS.GUEST;
}

/**
 * Detailed function explanation:
 * - Purpose: `signup` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function signup(payload) {
  return request("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `verifyOtp` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function verifyOtp(payload) {
  return request("/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `login` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function login(payload) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getMe` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getMe() {
  return request("/auth/me", {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getHealth` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getHealth() {
  return request("/health", {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getMetrics` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getMetrics() {
  return request("/metrics", {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getTelemetry` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getTelemetry({ hours = 24 } = {}) {
  return request(`/telemetry?hours=${hours}`, {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getDocuments` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getDocuments() {
  return request("/documents", {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getDocument` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getDocument(documentId) {
  return request(`/documents/${documentId}`, {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `deleteDocument` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function deleteDocument(documentId) {
  return request(`/documents/${documentId}`, {
    method: "DELETE",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `uploadDocument` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function uploadDocument({ file, chunkSize = 500, chunkOverlap = 100, permissionsTags = [] }) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("chunk_size", String(chunkSize));
  formData.append("chunk_overlap", String(chunkOverlap));
  formData.append("permissions_tags", JSON.stringify(permissionsTags));

  return request("/documents/upload", {
    method: "POST",
    body: formData,
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getChatSessions` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getChatSessions() {
  return request("/chat/sessions", {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `getChatMessages` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getChatMessages(sessionId) {
  return request(`/chat/sessions/${sessionId}/messages`, {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `deleteChatSession` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function deleteChatSession(sessionId) {
  return request(`/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `queryChat` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function queryChat({ question, limit = 5, sessionId = null }) {
  const payload = {
    question,
    limit,
    ...(sessionId ? { session_id: sessionId } : {}),
  };
  return request("/chat/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `evaluateQualityReport` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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

/**
 * Detailed function explanation:
 * - Purpose: `getUsers` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function getUsers() {
  return request("/admin/users", {
    method: "GET",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `updateUserRole` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function updateUserRole(userId, role) {
  return request(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `deleteUser` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function deleteUser(userId) {
  return request(`/admin/users/${userId}`, {
    method: "DELETE",
  });
}

/**
 * Detailed function explanation:
 * - Purpose: `updateDocumentPermissions` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export async function updateDocumentPermissions(documentId, payload) {
  return request(`/admin/documents/${documentId}/permissions`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
