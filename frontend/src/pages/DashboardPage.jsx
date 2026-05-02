/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import StatCard from "../components/common/StatCard";
import { useAuth } from "../context/AuthContext";
import { getDocuments, getHealth, getMetrics } from "../lib/api";
import { getRoleDefinition, isManagementRole, ROLE_KEYS } from "../lib/roles";

/**
 * Detailed function explanation:
 * - Purpose: `scopeCopy` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function scopeCopy(metrics, userRole) {
  if (metrics?.scope === "global" || isManagementRole(userRole)) {
    return "all users";
  }
  return "your account";
}

/**
 * Detailed function explanation:
 * - Purpose: `countForType` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function countForType(metrics, requestType) {
  return metrics?.by_request_type?.[requestType]?.request_count ?? 0;
}

/**
 * Detailed function explanation:
 * - Purpose: `buildMetricCards` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function buildMetricCards({ documents, health, metricTotals, metrics, userRole }) {
  const scope = scopeCopy(metrics, userRole);
  const documentHint = isManagementRole(userRole)
    ? "Documents returned by the documents API for your management role. This can include workspace documents you are allowed to inspect."
    : "Documents returned by the documents API for your role and permissions. Hidden documents are not counted.";
  const baseCards = [
    {
      label: "API health",
      value: health?.status || "Loading",
      detail: `Database: ${health?.database || "checking"} | Vector store: ${health?.vector_store || "checking"}`,
      tone: "signal",
      hint: "Live health response from the backend. It checks the API status, database connection, and vector store availability.",
    },
    {
      label: "Visible documents",
      value: documents.length,
      detail: `Documents visible to ${scope}.`,
      tone: "document",
      hint: documentHint,
    },
  ];

  if (isManagementRole(userRole)) {
    return [
      ...baseCards,
      {
        label: "Workspace requests",
        value: metricTotals.request_count ?? 0,
        detail: `Tracked across ${scope}.`,
        tone: "chat",
        hint: "Total logged chat, retrieval, ingestion, and document requests. Admin and Manager roles see the global workspace scope.",
      },
      {
        label: "Estimated cost",
        value: `$${Number(metricTotals.estimated_cost ?? 0).toFixed(6)}`,
        detail: `Tokens: ${metricTotals.token_total ?? 0} | Errors: ${metricTotals.error_count ?? 0}`,
        tone: "admin",
        hint: "Estimated cost from logged input and output tokens. It uses the backend telemetry cost formula, so it is an operational estimate.",
      },
    ];
  }

  if (userRole === ROLE_KEYS.ANALYST) {
    return [
      ...baseCards,
      {
        label: "My ingestion requests",
        value: countForType(metrics, "ingestion"),
        detail: `Total requests: ${metricTotals.request_count ?? 0}`,
        tone: "chat",
        hint: "Ingestion and document-processing requests logged for your account. Analysts usually see this because they can upload knowledge sources.",
      },
      {
        label: "My tokens",
        value: metricTotals.token_total ?? 0,
        detail: `Input: ${metricTotals.token_input ?? 0} | Output: ${metricTotals.token_output ?? 0}`,
        tone: "admin",
        hint: "Total input and output tokens logged for your account across chat and retrieval-backed answers.",
      },
    ];
  }

  return [
    ...baseCards,
    {
      label: "My chat requests",
      value: countForType(metrics, "chat"),
      detail: `Total requests: ${metricTotals.request_count ?? 0}`,
      tone: "chat",
      hint: "Chat requests logged for your own account. Viewer and Guest roles only see their personal metrics.",
    },
    {
      label: "Avg latency",
      value: `${metricTotals.avg_latency_ms ?? 0} ms`,
      detail: `Errors: ${metricTotals.error_count ?? 0} | Scope: ${scope}`,
      tone: "admin",
      hint: "Average backend request time for your logged activity. Lower values mean responses are returning faster.",
    },
  ];
}

/**
 * Detailed function explanation:
 * - Purpose: `DashboardPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState("");
  const roleDefinition = getRoleDefinition(user?.role);

  useEffect(() => {
    /**
     * Detailed function explanation:
     * - Purpose: `loadDashboard` handles a specific UI/data responsibility in this file.
     * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
     * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
     *   predictable UI output or data transformations used by the next step.
     */
    async function loadDashboard() {
      try {
        const [healthResponse, metricsResponse, documentsResponse] = await Promise.all([
          getHealth(),
          getMetrics(),
          getDocuments(),
        ]);
        setHealth(healthResponse);
        setMetrics(metricsResponse);
        setDocuments(documentsResponse.documents || []);
      } catch (dashboardError) {
        setError(dashboardError.message || "Failed to load dashboard.");
      }
    }

    loadDashboard();
  }, []);

  const metricTotals = metrics?.totals || {};
  const metricCards = buildMetricCards({
    documents,
    health,
    metricTotals,
    metrics,
    userRole: user?.role,
  });

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow={roleDefinition.tone}
        title={`Welcome back, ${user?.username}`}
        description={roleDefinition.description}
      />

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="stats-grid">
        {metricCards.map((card) => (
          <StatCard key={card.label} {...card} />
        ))}
      </section>

      <section className="content-grid two-up">
        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Workspace posture</p>
              <h2>Operational snapshot</h2>
            </div>
          </div>
          <ul className="feature-list">
            <li>Your frontend is now mapped to auth, document, chat, and admin API groups.</li>
            <li>Session history persists through the backend and can be resumed from the chat page.</li>
            <li>Role-aware navigation automatically hides management areas when they are not relevant.</li>
          </ul>
        </article>

        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Recent inventory</p>
              <h2>Newest documents</h2>
            </div>
          </div>
          <div className="data-list">
            {documents.slice(0, 5).map((document) => (
              <div key={document.id} className="data-row">
                <strong>{document.title}</strong>
                <span>{document.file_type} | {document.status}</span>
              </div>
            ))}
            {documents.length === 0 ? <p className="muted-copy">No documents yet.</p> : null}
          </div>
        </article>
      </section>
    </div>
  );
}
