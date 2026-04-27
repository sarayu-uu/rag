import EmptyState from "../common/EmptyState";

export default function SourcePanel({ answerPayload }) {
  const sources = answerPayload?.sources || [];
  const documentsUsed = answerPayload?.documents_used || [];

  return (
    <section className="feature-card source-card">
      <div className="feature-card-header">
        <div>
          <p className="eyebrow">Evidence</p>
          <h2>Source citations</h2>
        </div>
      </div>

      {!answerPayload ? (
        <EmptyState
          title="No answer yet"
          message="Once the assistant responds, the supporting sources and document summary will appear here."
        />
      ) : (
        <div className="source-stack">
          <div className="source-answer">
            <h3>Latest answer</h3>
            <p>{answerPayload.answer}</p>
          </div>

          <div className="source-summary-grid">
            <div className="source-summary-box">
              <span>Matches retrieved</span>
              <strong>{answerPayload.retrieved_match_count ?? answerPayload.match_count ?? 0}</strong>
            </div>
            <div className="source-summary-box">
              <span>Documents used</span>
              <strong>{documentsUsed.length}</strong>
            </div>
          </div>

          <div className="source-list">
            {sources.map((source) => (
              <article key={`${source.id}-${source.chunk_index}`} className="source-row">
                <strong>{source.label}</strong>
                <p>{source.source_name}</p>
                <small>
                  Document {source.document_id} | Chunk {source.chunk_index}
                  {source.page_number != null ? ` | Page ${source.page_number}` : ""}
                </small>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
