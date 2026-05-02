/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useState } from "react";
import { ROLE_DEFINITIONS, ROLE_KEYS } from "../../lib/roles";

const ROLE_OPTIONS = [
  ROLE_KEYS.ADMIN,
  ROLE_KEYS.MANAGER,
  ROLE_KEYS.ANALYST,
  ROLE_KEYS.VIEWER,
  ROLE_KEYS.GUEST,
];

/**
 * Detailed function explanation:
 * - Purpose: `EyeIcon` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
function EyeIcon({ open }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="password-visibility-icon">
      <path
        d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      />
      <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="1.8" />
      {open ? null : <path d="M4 4l16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />}
    </svg>
  );
}

/**
 * Detailed function explanation:
 * - Purpose: `DummyAuthPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function DummyAuthPage({
  mode,
  form,
  onModeChange,
  onFieldChange,
  onSubmit,
}) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <main className="auth-shell">
      <section className="auth-card panel">
        <header>
          <h1>RAG Workspace Access</h1>
          <p>Dummy {mode === "signin" ? "Sign In" : "Log In"} for role-based UI testing.</p>
        </header>

        <div className="auth-mode-switch">
          <button
            className={mode === "signin" ? "active-mode" : ""}
            onClick={() => onModeChange("signin")}
          >
            Sign In
          </button>
          <button
            className={mode === "login" ? "active-mode" : ""}
            onClick={() => onModeChange("login")}
          >
            Log In
          </button>
        </div>

        <label>
          Name
          <input
            value={form.name}
            onChange={(event) => onFieldChange("name", event.target.value)}
            placeholder="Ameya"
          />
        </label>

        <label>
          Email
          <input
            type="email"
            value={form.email}
            onChange={(event) => onFieldChange("email", event.target.value)}
            placeholder="you@company.com"
          />
        </label>

        <label>
          Password
          <div className="password-field">
            <input
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={(event) => onFieldChange("password", event.target.value)}
              placeholder="********"
            />
            <button
              type="button"
              className="password-visibility-toggle"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              title={showPassword ? "Hide password" : "Show password"}
            >
              <EyeIcon open={showPassword} />
            </button>
          </div>
        </label>

        <label>
          Role
          <select
            value={form.role}
            onChange={(event) => onFieldChange("role", event.target.value)}
          >
            {ROLE_OPTIONS.map((key) => (
              <option key={key} value={key}>
                {ROLE_DEFINITIONS[key].label}
              </option>
            ))}
          </select>
        </label>

        <button className="auth-submit" onClick={onSubmit}>
          Continue as {ROLE_DEFINITIONS[form.role].label}
        </button>
      </section>
    </main>
  );
}
