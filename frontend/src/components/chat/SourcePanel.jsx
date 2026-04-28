import EmptyState from "../common/EmptyState";
import { useState } from "react";
import { createPortal } from "react-dom";

export default function SourcePanel({ answerPayload }) {
  const [hoveredCitation, setHoveredCitation] = useState(null);
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
