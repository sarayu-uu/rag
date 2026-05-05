/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { getRoleDefinition, ROLE_KEYS } from "../../../lib/roles";
/** Renders the viewer role home panel. */
export default function ViewerHome() {
  const role = getRoleDefinition(ROLE_KEYS.VIEWER);
  return (
    <section className="panel role-home">
      <h2>{role.label} Scope</h2>
      <p>{role.description}</p>
      <ul>
        {role.responsibilities.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}




