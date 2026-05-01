export default function StatCard({ label, value, detail, tone = "neutral", hint = "" }) {
  return (
    <article className={`stat-card stat-${tone}`}>
      <div className="stat-card-head">
        <p className="eyebrow">{label}</p>
        {hint ? (
          <span className="metric-help" tabIndex={0} aria-label={`${label} info`}>
            i
            <span className="metric-tooltip">{hint}</span>
          </span>
        ) : null}
      </div>
      <h3>{value}</h3>
      <p>{detail}</p>
    </article>
  );
}
