import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import StatCard from "../components/common/StatCard";
import { getHealth, getTelemetry } from "../lib/api";

export default function TelemetryPage() {
  const [hours, setHours] = useState(24);
  const [telemetry, setTelemetry] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadTelemetry(windowHours = hours) {
    setLoading(true);
    setError("");
    try {
      const [telemetryResponse, healthResponse] = await Promise.all([
        getTelemetry({ hours: windowHours }),
        getHealth(),
      ]);
      setTelemetry(telemetryResponse);
      setHealth(healthResponse);
    } catch (telemetryError) {
      setError(telemetryError.message || "Failed to load telemetry.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTelemetry(hours);
  }, []);

  const logging = telemetry?.logging || {};
  const usage = telemetry?.usage_tracking || {};
  const modelPerformance = telemetry?.model_performance || {};
  const system = telemetry?.system_health_monitoring || {};

  return (
    <div className="page-stack">
      <SectionHeader
        eyebrow="Telemetry & Observability"
        title="Telemetry"
        description="Request logs, usage, model performance, and system health from metrics_usage."
        action={(
          <div className="toggle-row">
            <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={72}>Last 72 hours</option>
              <option value={168}>Last 7 days</option>
            </select>
            <button
              className="ghost-button"
              onClick={() => loadTelemetry(hours)}
              disabled={loading}
            >
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        )}
      />

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="stats-grid">
        <StatCard
          label="Requests"
          value={logging.request_count ?? 0}
          detail={`Errors: ${logging.error_count ?? 0} | Error rate: ${logging.error_rate ?? 0}`}
          tone="signal"
        />
        <StatCard
          label="Latency"
          value={`${logging.avg_latency_ms ?? 0} ms`}
          detail={`Max latency: ${logging.max_latency_ms ?? 0} ms`}
          tone="chat"
        />
        <StatCard
          label="Token usage"
          value={usage.token_total ?? 0}
          detail={`Input: ${usage.token_input ?? 0} | Output: ${usage.token_output ?? 0}`}
          tone="document"
        />
        <StatCard
          label="Estimated cost"
          value={`$${Number(usage.estimated_cost ?? 0).toFixed(6)}`}
          detail={`Window: ${telemetry?.window_hours ?? hours}h | Scope: ${telemetry?.scope ?? "n/a"}`}
          tone="admin"
        />
      </section>

      <section className="content-grid two-up">
        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Model performance</p>
              <h2>Latency components</h2>
            </div>
          </div>
          <div className="data-list">
            <div className="data-row">
              <strong>Ingestion</strong>
              <span>{modelPerformance.avg_ingestion_time_ms ?? 0} ms</span>
            </div>
            <div className="data-row">
              <strong>Retrieval</strong>
              <span>{modelPerformance.avg_retrieval_latency_ms ?? 0} ms</span>
            </div>
            <div className="data-row">
              <strong>Model response</strong>
              <span>{modelPerformance.avg_model_latency_ms ?? 0} ms</span>
            </div>
          </div>
        </article>

        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">System health</p>
              <h2>Live status</h2>
            </div>
          </div>
          <div className="data-list">
            <div className="data-row">
              <strong>API</strong>
              <span>{system.api_status || health?.status || "unknown"}</span>
            </div>
            <div className="data-row">
              <strong>Database</strong>
              <span>{system.database || health?.database || "unknown"}</span>
            </div>
            <div className="data-row">
              <strong>Vector store</strong>
              <span>{system.vector_store || health?.vector_store || "unknown"}</span>
            </div>
            {system.database_detail ? (
              <div className="error-banner">{system.database_detail}</div>
            ) : null}
          </div>
        </article>
      </section>

      <section className="content-grid two-up">
        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Request classes</p>
              <h2>By request type</h2>
            </div>
          </div>
          <div className="data-list">
            {(usage.by_request_type || []).map((row) => (
              <div key={row.request_type} className="data-row">
                <strong>{row.request_type}</strong>
                <span>
                  req: {row.request_count} | err: {row.error_count} | tok: {row.token_total}
                </span>
              </div>
            ))}
            {(usage.by_request_type || []).length === 0 ? <p className="muted-copy">No data.</p> : null}
          </div>
        </article>

        <article className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">User usage</p>
              <h2>Top users in window</h2>
            </div>
          </div>
          <div className="data-list">
            {(usage.per_user_usage || []).map((row) => (
              <div key={`u-${row.user_id ?? "none"}`} className="data-row">
                <strong>User {row.user_id ?? "N/A"}</strong>
                <span>
                  req: {row.request_count} | tok: {row.token_total} | ${Number(row.estimated_cost ?? 0).toFixed(6)}
                </span>
              </div>
            ))}
            {(usage.per_user_usage || []).length === 0 ? <p className="muted-copy">No data.</p> : null}
          </div>
        </article>
      </section>
    </div>
  );
}
