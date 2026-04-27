import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import StatCard from "../components/common/StatCard";
import { useAuth } from "../context/AuthContext";
import { getDocuments, getHealth, getMetrics } from "../lib/api";
import { getRoleDefinition } from "../lib/roles";

export default function DashboardPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState("");
  const roleDefinition = getRoleDefinition(user?.role);

  useEffect(() => {
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

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow={roleDefinition.tone}
        title={`Welcome back, ${user?.username}`}
        description={roleDefinition.description}
      />

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="stats-grid">
        <StatCard
          label="API health"
          value={health?.status || "Loading"}
          detail={`Database: ${health?.database || "checking"} | Vector store: ${health?.vector_store || "checking"}`}
          tone="signal"
        />
        <StatCard
          label="Visible documents"
          value={documents.length}
          detail="Documents currently accessible in your workspace."
          tone="document"
        />
        <StatCard
          label="Tracked requests"
          value={metricTotals.request_count ?? 0}
          detail={`Metrics scope: ${metrics?.scope || "current_user"}`}
          tone="chat"
        />
        <StatCard
          label="Avg latency"
          value={`${metricTotals.avg_latency_ms ?? 0} ms`}
          detail="Observed average latency from the current metrics endpoint."
          tone="admin"
        />
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
