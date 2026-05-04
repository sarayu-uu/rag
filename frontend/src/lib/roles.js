/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

export const ROLE_KEYS = {
  ADMIN: "Admin",
  MANAGER: "Manager",
  ANALYST: "Analyst",
  VIEWER: "Viewer",
  GUEST: "Guest",
};

export const ROLE_DEFINITIONS = {
  [ROLE_KEYS.ADMIN]: {
    label: "Admin",
    tone: "Command",
    description: "Owns global operations, access, and oversight across the workspace.",
    navigation: ["dashboard", "documents", "chat", "profile", "users", "permissions", "telemetry"],
  },
  [ROLE_KEYS.MANAGER]: {
    label: "Manager",
    tone: "Control",
    description: "Manages teams, documents, and permission policies for business workflows.",
    navigation: ["dashboard", "documents", "chat", "profile", "users", "permissions", "telemetry"],
  },
  [ROLE_KEYS.ANALYST]: {
    label: "Analyst",
    tone: "Research",
    description: "Uploads knowledge sources and runs grounded analysis across sessions.",
    navigation: ["dashboard", "documents", "chat", "profile"],
  },
  [ROLE_KEYS.VIEWER]: {
    label: "Viewer",
    tone: "Read",
    description: "Reviews approved documents, conversations, and cited answers.",
    navigation: ["dashboard", "documents", "chat", "profile"],
  },
  [ROLE_KEYS.GUEST]: {
    label: "Guest",
    tone: "Limited",
    description: "Has a minimal experience with restricted access to approved content only.",
    navigation: ["dashboard", "chat", "profile"],
  },
};
/** Gets role definition. */
export function getRoleDefinition(role) {
  return ROLE_DEFINITIONS[role] || ROLE_DEFINITIONS[ROLE_KEYS.GUEST];
}
/** Checks whether management role. */
export function isManagementRole(role) {
  return role === ROLE_KEYS.ADMIN || role === ROLE_KEYS.MANAGER;
}
/** Checks whether upload. */
export function canUpload(role) {
  return role === ROLE_KEYS.ADMIN || role === ROLE_KEYS.MANAGER || role === ROLE_KEYS.ANALYST;
}


