import { ROLE_KEYS } from "./roles";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const STORAGE_KEY = "rag_auth_tokens";

let authStore = {
  accessToken: "",
  refreshToken: "",
};

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

export function normalizeRole(role) {
  return role || ROLE_KEYS.GUEST;
}

export async function signup(payload) {
  return request("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function verifyOtp(payload) {
  return request("/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getMe() {
  return request("/auth/me", {
    method: "GET",
  });
}

export async function getHealth() {
  return request("/health", {
    method: "GET",
  });
}

export async function getMetrics() {
  return request("/metrics", {
    method: "GET",
  });
}

export async function getDocuments() {
  return request("/documents", {
    method: "GET",
  });
}

export async function getDocument(documentId) {
  return request(`/documents/${documentId}`, {
    method: "GET",
  });
}

export async function deleteDocument(documentId) {
  return request(`/documents/${documentId}`, {
    method: "DELETE",
  });
}

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

export async function getChatSessions() {
  return request("/chat/sessions", {
    method: "GET",
  });
}

export async function getChatMessages(sessionId) {
  return request(`/chat/sessions/${sessionId}/messages`, {
    method: "GET",
  });
}

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

export async function getUsers() {
  return request("/admin/users", {
    method: "GET",
  });
}

export async function updateUserRole(userId, role) {
  return request(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export async function updateDocumentPermissions(documentId, payload) {
  return request(`/admin/documents/${documentId}/permissions`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
