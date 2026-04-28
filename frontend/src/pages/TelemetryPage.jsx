import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import StatCard from "../components/common/StatCard";
import { evaluateQualityReport, getHealth, getTelemetry } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function TelemetryPage() {
  const { user } = useAuth();
  const [hours, setHours] = useState(24);
  const [telemetry, setTelemetry] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evalQuestion, setEvalQuestion] = useState("");
  const [evalGroundTruth, setEvalGroundTruth] = useState("");
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState("");
  const [evalResult, setEvalResult] = useState(null);
  const canRunEval =
    user?.role === "Admin" || user?.role === "SuperAdmin" || user?.role === "Super Admin";

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

  async function runEvaluation(event) {
    event.preventDefault();
    if (!evalQuestion.trim()) {
      setEvalError("Enter a question to evaluate.");
      return;
    }
    setEvalLoading(true);
    setEvalError("");
    try {
      const payload = await evaluateQualityReport({
        question: evalQuestion.trim(),
        groundTruth: evalGroundTruth.trim(),
        limit: 5,
        includeRagas: true,
      });
      setEvalResult(payload);
    } catch (evaluationError) {
      setEvalError(evaluationError.message || "Failed to run evaluation.");
    } finally {
      setEvalLoading(false);
    }
  }

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

      {canRunEval ? (
        <section className="feature-card">
          <div className="feature-card-header">
            <div>
              <p className="eyebrow">Evaluation</p>
              <h2>RAGAS + Retrieval Test</h2>
            </div>
          </div>
          <form className="compact-form" onSubmit={runEvaluation}>
            <label>
              <span className="eyebrow">Question</span>
              <textarea
                value={evalQuestion}
                onChange={(event) => setEvalQuestion(event.target.value)}
                placeholder="Type a question to evaluate RAG quality."
              />
            </label>
            <label>
              <span className="eyebrow">Ground Truth (Optional)</span>
              <textarea
                value={evalGroundTruth}
                onChange={(event) => setEvalGroundTruth(event.target.value)}
                placeholder="Reference answer. Improves context_precision/context_recall quality."
              />
            </label>
            <div className="composer-actions">
              <small>Runs full retrieval + RAGAS evaluation. This can take longer than chat.</small>
              <button type="submit" disabled={evalLoading}>
                {evalLoading ? "Evaluating..." : "Run RAGAS Test"}
              </button>
            </div>
          </form>

          {evalError ? <div className="error-banner">{evalError}</div> : null}

          {evalResult ? (
            <div className="quality-metrics">
              <h3>Retrieval Metrics</h3>
              <ul className="quality-list">
                <li>
                  <strong>Top rerank score:</strong> {Number(evalResult.retrieval_summary?.top_rerank_score ?? 0).toFixed(4)}.
                </li>
                <li>
                  <strong>Average rerank score:</strong> {Number(evalResult.retrieval_summary?.avg_rerank_score ?? 0).toFixed(4)}.
                </li>
                <li>
                  <strong>Best semantic distance:</strong> {Number(evalResult.retrieval_summary?.best_semantic_distance ?? 0).toFixed(4)}.
                </li>
                <li>
                  <strong>Retrieval latency:</strong> {evalResult.retrieval_summary?.retrieval_latency_ms ?? 0} ms.
                </li>
                <li>
                  <strong>Semantic/Keyword/Hybrid candidates:</strong>{" "}
                  {evalResult.retrieval_summary?.retrieval_debug?.semantic_match_count ?? 0}/
                  {evalResult.retrieval_summary?.retrieval_debug?.keyword_match_count ?? 0}/
                  {evalResult.retrieval_summary?.retrieval_debug?.hybrid_match_count ?? 0}.
                </li>
              </ul>

              <h3>RAGAS Metrics</h3>
              {evalResult.ragas?.status !== "success" ? (
                <p className="muted-copy">{evalResult.ragas?.detail || "RAGAS metrics are unavailable for this run."}</p>
              ) : (
                <ul className="quality-list">
                  <li>
                    <strong>Faithfulness:</strong> {Number(evalResult.ragas?.metrics?.faithfulness ?? 0).toFixed(4)}.
                  </li>
                  <li>
                    <strong>Answer relevancy:</strong> {Number(evalResult.ragas?.metrics?.answer_relevancy ?? 0).toFixed(4)}.
                  </li>
                  <li>
                    <strong>Context precision:</strong> {Number(evalResult.ragas?.metrics?.context_precision ?? 0).toFixed(4)}.
                  </li>
                  <li>
                    <strong>Context recall:</strong> {Number(evalResult.ragas?.metrics?.context_recall ?? 0).toFixed(4)}.
                  </li>
                </ul>
              )}
              {(evalResult.ragas?.skipped_metrics || []).length > 0 ? (
                <p className="muted-copy">Skipped: {(evalResult.ragas?.skipped_metrics || []).join(", ")}</p>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
