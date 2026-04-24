export default function DummyTablePanel({ title, description, rows }) {
  return (
    <section className="panel right-panel">
      <header className="panel-heading">
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      <div className="scroll-region">
        {rows.map((row, index) => (
          <article key={`${title}-${index}`} className="doc-row">
            <p>
              <strong>{row.title}</strong>
            </p>
            <p className="muted-text">{row.subtitle}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

