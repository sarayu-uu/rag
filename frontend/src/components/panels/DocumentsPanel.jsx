export default function DocumentsPanel({ documents }) {
  return (
    <section className="panel right-panel">
      <header className="panel-heading">
        <h2>Documents</h2>
        <p>Indexed files available for retrieval.</p>
      </header>
      <div className="scroll-region">
        {documents.length === 0 ? (
          <p className="muted-text">No indexed documents in this UI session yet.</p>
        ) : (
          documents.map((doc, index) => (
            <article key={`${doc.document_id || "doc"}-${index}`} className="doc-row">
              <p>
                <strong>{doc.file_name || doc.title || "Document"}</strong>
              </p>
              <p className="muted-text">
                Doc ID: {doc.document_id ?? "-"} | Chunks: {doc.chunk_count ?? "-"} | Indexed:{" "}
                {doc.vector_indexed ? "Yes" : "No"}
              </p>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

