/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useEffect, useState } from "react";
import SectionHeader from "../components/common/SectionHeader";
import StatCard from "../components/common/StatCard";
import { evaluateQualityReport, getHealth, getTelemetry } from "../lib/api";
import { useAuth } from "../context/AuthContext";

/**
 * Detailed function explanation:
 * - Purpose: `MetricHelp` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function MetricHelp({ label, hint }) {
  return (
    <span className="metric-inline-label">
      <strong>{label}</strong>
      <span className="metric-help metric-help-inline" tabIndex={0} aria-label={`${label} info`}>
        i
        <span className="metric-tooltip">{hint}</span>
      </span>
    </span>
  );
}

/**
 * Detailed function explanation:
 * - Purpose: `TelemetryPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
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

  /**
   * Detailed function explanation:
   * - Purpose: `loadTelemetry` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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

  /**
   * Detailed function explanation:
   * - Purpose: `runEvaluation` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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
  const byRequestType = usage.by_request_type || [];
  const chatUsageRow = byRequestType.find((row) => String(row.request_type).toLowerCase() === "chat") || null;
  const windowHoursLabel = telemetry?.window_hours ?? hours;
  const scopeLabel = telemetry?.scope === "global" ? "all visible users" : "your account";

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
          hint="Count of logged API requests in the selected time window and scope."
        />
        <StatCard
          label="Latency"
          value={`${logging.avg_latency_ms ?? 0} ms`}
          detail={`Max latency: ${logging.max_latency_ms ?? 0} ms`}
          tone="chat"
          hint="Average backend request time for the selected time window. Max latency shows the slowest request seen."
        />
        <StatCard
          label="Window tokens"
          value={usage.token_total ?? 0}
          detail={`Chat: ${chatUsageRow?.token_total ?? 0} | Scope: ${scopeLabel}`}
          tone="document"
          hint="Aggregated token usage from telemetry logs across the selected time window. This is not the same as the token total for one chat session."
        />
        <StatCard
          label="Estimated cost"
          value={`$${Number(usage.estimated_cost ?? 0).toFixed(6)}`}
          detail={`Window: ${windowHoursLabel}h | Scope: ${scopeLabel}`}
          tone="admin"
          hint="Estimated usage cost computed from logged input and output tokens in the selected time window."
        />
      </section>

      <div className="info-banner">
        Chat page totals are per session. Telemetry totals are aggregated across the selected time window and scope.
      </div>

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
              <MetricHelp
                label="Ingestion"
                hint="Average time spent processing document ingestion requests in the selected telemetry window."
              />
              <span>{modelPerformance.avg_ingestion_time_ms ?? 0} ms</span>
            </div>
            <div className="data-row">
              <MetricHelp
                label="Retrieval"
                hint="Average time spent finding relevant document chunks for retrieval requests in the selected telemetry window."
              />
              <span>{modelPerformance.avg_retrieval_latency_ms ?? 0} ms</span>
            </div>
            <div className="data-row">
              <MetricHelp
                label="Model response"
                hint="Average time attributed to model generation for logged chat responses in the selected telemetry window."
              />
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
              <MetricHelp
                label="API"
                hint="Current backend API health status. This is live system health, not a historical request metric."
              />
              <span>{system.api_status || health?.status || "unknown"}</span>
            </div>
            <div className="data-row">
              <MetricHelp
                label="Database"
                hint="Current database connectivity check used by the backend health monitor."
              />
              <span>{system.database || health?.database || "unknown"}</span>
            </div>
            <div className="data-row">
              <MetricHelp
                label="Vector store"
                hint="Current vector database status for retrieval. If it is unavailable, document search quality can be affected."
              />
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
                <MetricHelp
                  label={row.request_type}
                  hint="Request class from telemetry logs. Counts, errors, tokens, and average latency are aggregated for this class in the selected window."
                />
                <span>
                  req: {row.request_count} | err: {row.error_count} | tok: {row.token_total} | avg: {row.avg_latency_ms} ms
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
                <MetricHelp
                  label={`User ${row.user_id ?? "N/A"}`}
                  hint="Per-user usage row for the selected telemetry window. Admin and Manager roles can see users in the global scope."
                />
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
                  <MetricHelp
                    label="Top rerank score:"
                    hint={evalResult.metric_guide?.rerank_score || "Highest hybrid relevance score among selected chunks. Higher usually means the best retrieved chunk is more relevant."}
                  />{" "}
                  {Number(evalResult.retrieval_summary?.top_rerank_score ?? 0).toFixed(4)}.
                </li>
                <li>
                  <MetricHelp
                    label="Average rerank score:"
                    hint={evalResult.metric_guide?.avg_rerank_score || "Mean hybrid relevance score across selected chunks. Higher means the retrieved context is stronger overall."}
                  />{" "}
                  {Number(evalResult.retrieval_summary?.avg_rerank_score ?? 0).toFixed(4)}.
                </li>
                <li>
                  <MetricHelp
                    label="Best semantic distance:"
                    hint={evalResult.metric_guide?.semantic_distance || "Best vector distance among retrieved chunks. Lower distance means stronger semantic similarity."}
                  />{" "}
                  {Number(evalResult.retrieval_summary?.best_semantic_distance ?? 0).toFixed(4)}.
                </li>
                <li>
                  <MetricHelp
                    label="Retrieval latency:"
                    hint="Time spent running retrieval for this evaluation request."
                  />{" "}
                  {evalResult.retrieval_summary?.retrieval_latency_ms ?? 0} ms.
                </li>
                <li>
                  <MetricHelp
                    label="Semantic/Keyword/Hybrid candidates:"
                    hint="Candidate counts found by vector search, keyword search, and the combined hybrid set before final ranking."
                  />{" "}
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
                    <MetricHelp
                      label="Faithfulness:"
                      hint={evalResult.metric_guide?.faithfulness || "Measures whether the answer is supported by the retrieved context. Higher is better."}
                    />{" "}
                    {Number(evalResult.ragas?.metrics?.faithfulness ?? 0).toFixed(4)}.
                  </li>
                  <li>
                    <MetricHelp
                      label="Answer relevancy:"
                      hint={evalResult.metric_guide?.answer_relevancy || "Measures how directly the answer addresses the question. Higher is better."}
                    />{" "}
                    {Number(evalResult.ragas?.metrics?.answer_relevancy ?? 0).toFixed(4)}.
                  </li>
                  <li>
                    <MetricHelp
                      label="Context precision:"
                      hint={evalResult.metric_guide?.context_precision || "Measures whether the highest-ranked retrieved context is useful. Higher is better."}
                    />{" "}
                    {Number(evalResult.ragas?.metrics?.context_precision ?? 0).toFixed(4)}.
                  </li>
                  <li>
                    <MetricHelp
                      label="Context recall:"
                      hint={evalResult.metric_guide?.context_recall || "Measures whether the retrieved context covers the reference answer. Higher is better."}
                    />{" "}
                    {Number(evalResult.ragas?.metrics?.context_recall ?? 0).toFixed(4)}.
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
