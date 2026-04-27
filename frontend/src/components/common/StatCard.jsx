export default function StatCard({ label, value, detail, tone = "neutral" }) {
  return (
    <article className={`stat-card stat-${tone}`}>
      <p className="eyebrow">{label}</p>
      <h3>{value}</h3>
      <p>{detail}</p>
    </article>
  );
}
