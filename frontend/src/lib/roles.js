export const ROLE_KEYS = {
  SUPER_ADMIN: "SUPER_ADMIN",
  ADMIN: "ADMIN",
  EDITOR: "EDITOR",
  VIEWER: "VIEWER",
};

export const ROLE_DEFINITIONS = {
  [ROLE_KEYS.SUPER_ADMIN]: {
    label: "Super Admin",
    description: "Platform governance and global security control.",
    responsibilities: [
      "Define RBAC model and policy boundaries for all tenants and teams.",
      "Override document and session access during audits or incidents.",
      "Approve sensitive permission grants and revoke emergency access.",
      "Monitor platform-wide ingestion, retrieval, and model usage health.",
    ],
    tabs: ["documents", "ingestion", "users", "permissions", "analytics"],
  },
  [ROLE_KEYS.ADMIN]: {
    label: "Admin",
    description: "Operational control for a business unit or workspace.",
    responsibilities: [
      "Manage users in assigned workspace and map them to approved roles.",
      "Control document lifecycle: archive, restore, and retention actions.",
      "Assign document-level query/edit permissions for business teams.",
      "Track usage analytics and escalate anomalies to Super Admin.",
    ],
    tabs: ["documents", "ingestion", "users", "permissions", "analytics"],
  },
  [ROLE_KEYS.EDITOR]: {
    label: "Editor",
    description: "Knowledge curator for ingestion and document quality.",
    responsibilities: [
      "Upload single or batch files and maintain source metadata quality.",
      "Trigger ingestion and re-indexing for updated business documents.",
      "Validate chunk quality and resolve ingestion failures for owned docs.",
      "Maintain permission tags and source labels for retrievable context.",
    ],
    tabs: ["documents", "ingestion"],
  },
  [ROLE_KEYS.VIEWER]: {
    label: "Viewer",
    description: "Consumer of grounded answers and approved documents.",
    responsibilities: [
      "Ask questions and review grounded responses with source citations.",
      "Browse accessible documents and session history for traceability.",
      "Flag unclear or low-confidence responses back to Editors/Admins.",
      "Cannot upload, re-index, or change permissions.",
    ],
    tabs: ["documents"],
  },
};

export function getRoleDefinition(roleKey) {
  return ROLE_DEFINITIONS[roleKey] || ROLE_DEFINITIONS[ROLE_KEYS.VIEWER];
}
