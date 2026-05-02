/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { getRoleDefinition, ROLE_KEYS } from "../../../lib/roles";

/**
 * Detailed function explanation:
 * - Purpose: `SuperAdminHome` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function SuperAdminHome() {
  const role = getRoleDefinition(ROLE_KEYS.SUPER_ADMIN);
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

