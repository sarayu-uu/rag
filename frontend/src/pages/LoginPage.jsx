/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

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
 * - Purpose: `LoginPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function LoginPage() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  /**
   * Detailed function explanation:
   * - Purpose: `handleSubmit` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await signIn(form);
      navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
    } catch (loginError) {
      setError(loginError.message || "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page auth-signin">
      <section className="auth-hero">
        <p className="eyebrow">RAG Platform</p>
        <h1>Ground answers in documents, not guesswork.</h1>
        <p>
          Securely upload internal knowledge, run retrieval-backed conversations, and manage access with role-aware
          controls.
        </p>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-card">
          <p className="eyebrow">Welcome back</p>
          <h2>Log in</h2>
          <p className="section-copy">Use your verified account to access the workspace.</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm((value) => ({ ...value, email: event.target.value }))}
                placeholder="you@gmail.com"
                required
              />
            </label>

            <label>
              <span>Password</span>
              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={(event) => setForm((value) => ({ ...value, password: event.target.value }))}
                  placeholder="Enter your password"
                  required
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

            {error ? <div className="error-banner">{error}</div> : null}

            <button type="submit" disabled={submitting}>
              {submitting ? "Signing in..." : "Access workspace"}
            </button>
          </form>

          <div className="auth-links">
            <span>Need an account?</span>
            <Link to="/signup">Create one</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
