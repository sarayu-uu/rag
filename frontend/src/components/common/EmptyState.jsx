/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */
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


