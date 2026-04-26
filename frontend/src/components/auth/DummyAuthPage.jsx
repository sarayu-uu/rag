import { ROLE_DEFINITIONS, ROLE_KEYS } from "../../lib/roles";

const ROLE_OPTIONS = [
  ROLE_KEYS.SUPER_ADMIN,
  ROLE_KEYS.ADMIN,
  ROLE_KEYS.EDITOR,
  ROLE_KEYS.VIEWER,
];

export default function DummyAuthPage({
  mode,
  form,
  onModeChange,
  onFieldChange,
  onSubmit,
}) {
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
          <input
            type="password"
            value={form.password}
            onChange={(event) => onFieldChange("password", event.target.value)}
            placeholder="••••••••"
          />
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

