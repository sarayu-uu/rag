import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { verifyOtp } from "../lib/api";

export default function VerifyOtpPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state || {};
  const [form, setForm] = useState({
    email: state.email || "",
    otp: state.otp || "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      await verifyOtp(form);
      setSuccess("OTP confirmed. You can log in now.");
      setTimeout(() => {
        navigate("/login", { replace: true });
      }, 900);
    } catch (otpError) {
      setError(otpError.message || "OTP verification failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page auth-verify">
      <section className="auth-hero">
        <p className="eyebrow">Confirm identity</p>
        <h1>Verify your OTP before entering the workspace.</h1>
        <p>The backend requires OTP confirmation before login, so this step is a dedicated page in the flow.</p>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-card">
          <p className="eyebrow">Confirm OTP</p>
          <h2>Verification code</h2>
          <p className="section-copy">
            Enter the OTP for your email. In development mode, the generated OTP may be shown inline after signup.
          </p>

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
              <span>OTP</span>
              <input
                type="text"
                value={form.otp}
                onChange={(event) => setForm((value) => ({ ...value, otp: event.target.value }))}
                placeholder="6-digit code"
                required
              />
            </label>

            {state.otpDelivery === "development_inline" && state.otp ? (
              <div className="info-banner">Development OTP: {state.otp}</div>
            ) : null}
            {error ? <div className="error-banner">{error}</div> : null}
            {success ? <div className="success-banner">{success}</div> : null}

            <button type="submit" disabled={submitting}>
              {submitting ? "Confirming..." : "Confirm OTP"}
            </button>
          </form>

          <div className="auth-links">
            <span>Need to start over?</span>
            <Link to="/signup">Back to signup</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
