export default function EmptyState({ title, message, action }) {
  return (
    <div className="empty-state">
      <div className="empty-orb" />
      <h3>{title}</h3>
      <p>{message}</p>
      {action}
    </div>
  );
}
