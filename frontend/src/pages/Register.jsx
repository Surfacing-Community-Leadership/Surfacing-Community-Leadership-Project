import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { HeartMark } from "../components/Logo.jsx";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, displayName);
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="org auth-split">
      <aside className="auth-aside accent">
        <Link to="/" className="brand">
          <HeartMark size={28} color="var(--color-bg)" title="Ours" />
          <span className="wordmark">Ours</span>
        </Link>
        <div className="blob" aria-hidden="true" />
        <div className="lead">
          <p>Meet the people three doors down.</p>
          <ol>
            <li>
              <b>01</b> See what's happening this week nearby
            </li>
            <li>
              <b>02</b> Host a gathering or ask for a hand
            </li>
            <li>
              <b>03</b> Show up, then get on with your life
            </li>
          </ol>
        </div>
        <span className="foot">Neighbors helping neighbors</span>
      </aside>

      <main className="auth-main">
        <form onSubmit={handleSubmit}>
          <h1>Create your account</h1>
          <p className="auth-lead">
            Already a neighbor? <Link to="/login">Log in</Link>
          </p>
          {error && <div className="alert">{error}</div>}
          <div className="field">
            <label htmlFor="rg-name">Display name</label>
            <input
              id="rg-name"
              className="input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              maxLength={80}
            />
          </div>
          <div className="field">
            <label htmlFor="rg-email">Email</label>
            <input
              id="rg-email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label htmlFor="rg-pw">Password</label>
            <input
              id="rg-pw"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
            <span className="field-hint">At least 8 characters.</span>
          </div>
          <button type="submit" className="btn-block" disabled={submitting}>
            {submitting ? "Creating account…" : "Create account →"}
          </button>
          <p
            className="field-hint"
            style={{ marginTop: "18px", lineHeight: 1.55 }}
          >
            By joining you agree to keep it neighborly — no politics, no spam,
            real people only.
          </p>
        </form>
      </main>
    </div>
  );
}
