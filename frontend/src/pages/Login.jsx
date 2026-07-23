import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { HeartMark } from "../components/Logo.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/map";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="org auth-split">
      <aside className="auth-aside">
        <Link to="/" className="brand">
          <HeartMark size={28} color="var(--color-accent)" title="Ours" />
          <span className="wordmark">Ours</span>
        </Link>
        <div className="blob" aria-hidden="true" />
        <div className="lead">
          <p>Welcome back to the block.</p>
          <p className="sub">
            Your map is right where you left it — the gatherings, the hands to
            lend, the neighbors you've met.
          </p>
        </div>
        <span className="foot">Neighbors helping neighbors</span>
      </aside>

      <main className="auth-main">
        <form onSubmit={handleSubmit}>
          <h1>Log in</h1>
          <p className="auth-lead">
            New here? <Link to="/register">Create an account</Link>
          </p>
          {error && <div className="alert">{error}</div>}
          <div className="field">
            <label htmlFor="lg-email">Email</label>
            <input
              id="lg-email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label htmlFor="lg-pw">Password</label>
            <input
              id="lg-pw"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <button type="submit" className="btn-block" disabled={submitting}>
            {submitting ? "Logging in…" : "Log in →"}
          </button>
          <p
            className="muted"
            style={{ textAlign: "center", marginTop: "26px" }}
          >
            Free · Non-partisan · Built to be used less
          </p>
        </form>
      </main>
    </div>
  );
}
