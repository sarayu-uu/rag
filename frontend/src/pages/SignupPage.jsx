/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { signup } from "../lib/api";

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
 * - Purpose: `SignupPage` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export default function SignupPage() {
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();

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
      const response = await signup(form);
      navigate("/verify-otp", {
        replace: true,
        state: {
          email: form.email,
          otp: response.otp,
          otpDelivery: response.otp_delivery,
          message: response.message,
        },
      });
    } catch (signupError) {
      setError(signupError.message || "Unable to create account.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page auth-signup">
      <section className="auth-hero">
        <p className="eyebrow">Secure onboarding</p>
        <h1>Create a role-aware RAG workspace identity.</h1>
        <p>Sign up first, then confirm the OTP before you log in and start working with uploaded knowledge.</p>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-card">
          <p className="eyebrow">New account</p>
          <h2>Sign up</h2>
          <p className="section-copy">We will send or generate an OTP that must be confirmed before login.</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label>
              <span>Username</span>
              <input
                type="text"
                value={form.username}
                onChange={(event) => setForm((value) => ({ ...value, username: event.target.value }))}
                placeholder="satwik"
                required
              />
            </label>

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
                  placeholder="At least 6 characters"
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
              {submitting ? "Creating account..." : "Continue to OTP"}
            </button>
          </form>

          <div className="auth-links">
            <span>Already registered?</span>
            <Link to="/login">Log in</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
