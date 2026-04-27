import EmptyState from "../common/EmptyState";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { evaluateQualityReport } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";

export default function SourcePanel({ answerPayload }) {
  const { user } = useAuth();
  const [hoveredCitation, setHoveredCitation] = useState(null);
  const [qualityReport, setQualityReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportError, setReportError] = useState("");
  const canViewQuality =
    user?.role === "Admin" || user?.role === "SuperAdmin" || user?.role === "Super Admin";
  const sources = answerPayload?.sources || [];
  const matches = answerPayload?.matches || [];
  const retrievalMethods = Array.from(new Set(sources.map((source) => source.retrieval_method).filter(Boolean)));
  const retrievalMethodLabel = retrievalMethods.length > 0 ? retrievalMethods.join(" + ") : "hybrid";

  const citationPreviewByKey = new Map();
  matches.forEach((match) => {
    const key = `${match.document_id}-${match.chunk_index}`;
    if (citationPreviewByKey.has(key)) {
      return;
    }
    const preview = String(match.content || "").replace(/\s+/g, " ").trim();
    citationPreviewByKey.set(key, preview);
  });

  function computePopoverPosition(rect) {
    const popupWidth = Math.min(460, Math.floor(window.innerWidth * 0.72));
    const popupHeight = 220;
    const gap = 10;
    const margin = 8;

    const fitsBelow = rect.bottom + gap + popupHeight <= window.innerHeight - margin;
    const top = fitsBelow
      ? rect.bottom + gap
      : Math.max(margin, rect.top - popupHeight - gap);
    const left = Math.min(
      Math.max(margin, rect.left),
      Math.max(margin, window.innerWidth - popupWidth - margin)
    );

    return { top, left };
  }

  function showCitationPopover(event, preview) {
    const rect = event.currentTarget.getBoundingClientRect();
    const position = computePopoverPosition(rect);
    setHoveredCitation({
      text: preview,
      top: position.top,
      left: position.left,
    });
  }

  function moveCitationPopover(event) {
    if (!hoveredCitation) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const position = computePopoverPosition(rect);
    setHoveredCitation((previous) =>
      previous
        ? {
            ...previous,
            top: position.top,
            left: position.left,
          }
        : previous
    );
  }

  function hideCitationPopover() {
    setHoveredCitation(null);
  }

  useEffect(() => {
    setQualityReport(null);
    setReportError("");
  }, [answerPayload?.question]);

  async function handleGenerateQualityReport() {
    const question = String(answerPayload?.question || "").trim();
    if (!question) {
      setReportError("No question available for evaluation yet.");
      return;
    }

    setLoadingReport(true);
    setReportError("");
    try {
      const report = await evaluateQualityReport({
        question,
        limit: 5,
        includeRagas: false,
      });
      setQualityReport(report);
    } catch (error) {
      setReportError(error.message || "Failed to generate quality report.");
    } finally {
      setLoadingReport(false);
    }
  }

  const metricGuide = qualityReport?.metric_guide || {};
  const retrievalSummary = qualityReport?.retrieval_summary || null;

  return (
    <>
      <section className="feature-card source-card">
        <div className="feature-card-header">
          <div>
            <p className="eyebrow">Evidence</p>
            <h2>Source citations</h2>
          </div>
          <small className="source-note">
            Retrieval: {retrievalMethodLabel} (semantic + keyword rerank) | Generator: Groq chat model
          </small>
        </div>

        {!answerPayload ? (
          <EmptyState
            title="No answer yet"
            message="Once the assistant responds, the supporting sources and document summary will appear here."
          />
        ) : (
          <div className="source-stack">
            {canViewQuality ? (
              <div className="source-row quality-report-card">
              <div className="quality-report-head">
                <strong>Quality Report</strong>
                <small>Fast retrieval scoring for this answer (RAGAS is available in Telemetry).</small>
              </div>
              <button className="inline-link-button" type="button" onClick={handleGenerateQualityReport} disabled={loadingReport}>
                {loadingReport ? "Generating..." : "Quality Report"}
              </button>
              {reportError ? <p className="error-copy">{reportError}</p> : null}

              {qualityReport ? (
                <div className="quality-metrics">
                  <h3>Retrieval Metrics</h3>
                  {retrievalSummary ? (
                    <ul className="quality-list">
                      <li>
                        <strong>Top rerank score:</strong> {retrievalSummary.top_rerank_score?.toFixed?.(4) ?? retrievalSummary.top_rerank_score}
                        . {metricGuide.rerank_score || "This is the highest hybrid relevance score among selected chunks."} Range: typically 0.00 to 1.15, higher is better.
                      </li>
                      <li>
                        <strong>Average rerank score:</strong> {retrievalSummary.avg_rerank_score?.toFixed?.(4) ?? retrievalSummary.avg_rerank_score}
                        . {metricGuide.avg_rerank_score || "This is the mean hybrid relevance across selected chunks."} Range: typically 0.00 to 1.15, higher is better.
                      </li>
                      <li>
                        <strong>Best semantic distance:</strong>{" "}
                        {retrievalSummary.best_semantic_distance?.toFixed?.(4) ?? retrievalSummary.best_semantic_distance}.{" "}
                        {metricGuide.semantic_distance || "Lower distance means stronger semantic similarity."} Range: 0.00 and above, lower is better.
                      </li>
                      <li>
                        <strong>Retrieval latency:</strong> {retrievalSummary.retrieval_latency_ms} ms. This is the time taken to retrieve and rank chunks. Range: 0 ms and above, lower is faster.
                      </li>
                      <li>
                        <strong>Semantic/Keyword/Hybrid candidates:</strong>{" "}
                        {retrievalSummary.retrieval_debug?.semantic_match_count ?? 0}/
                        {retrievalSummary.retrieval_debug?.keyword_match_count ?? 0}/
                        {retrievalSummary.retrieval_debug?.hybrid_match_count ?? 0}. These are candidate counts at each retrieval stage. Range: whole numbers 0 and above.
                      </li>
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </div>
            ) : null}

            <div className="source-row source-aggregate">
              <strong>Retrieved Sources ({sources.length})</strong>
              <small>Matches retrieved: {answerPayload.retrieved_match_count ?? answerPayload.match_count ?? 0}</small>
              {sources.length === 0 ? (
                <p>No source chunks were returned for this answer.</p>
              ) : (
                <ol className="source-inline-list">
                  {sources.map((source, index) => {
                    const key = `${source.document_id}-${source.chunk_index}`;
                    const preview = citationPreviewByKey.get(key) || "Preview unavailable for this citation.";
                    return (
                      <li key={`${source.id}-${source.chunk_index}`} className="citation-item">
                        <span
                          className="citation-trigger"
                          title={preview}
                          onMouseEnter={(event) => showCitationPopover(event, preview)}
                          onMouseMove={moveCitationPopover}
                          onMouseLeave={hideCitationPopover}
                        >
                          [{index + 1}] {source.source_name} | Doc {source.document_id} | Chunk {source.chunk_index}
                          {source.page_number != null ? ` | Page ${source.page_number}` : ""}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>
          </div>
        )}
      </section>

      {hoveredCitation && typeof document !== "undefined"
        ? createPortal(
            <div
              className="citation-popover-overlay"
              style={{
                top: `${hoveredCitation.top}px`,
                left: `${hoveredCitation.left}px`,
              }}
            >
              <strong>Cited text preview</strong>
              <p>{hoveredCitation.text}</p>
            </div>,
            document.body
          )
        : null}
    </>
  );
}
