import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="screen-state">
      <div className="state-card">
        <p className="eyebrow">404</p>
        <h1>That page does not exist.</h1>
        <p>The route you tried to open is not part of this frontend workspace.</p>
        <Link className="inline-link-button" to="/dashboard">
          Go to dashboard
        </Link>
      </div>
    </div>
  );
}
