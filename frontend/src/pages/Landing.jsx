import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

// The public front door. Logged-in users skip it and go straight to the map;
// everyone else sees what Ours is and how to get in.
export default function Landing() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  if (loading) return <div className="centered muted">Loading…</div>;
  if (user) return <Navigate to="/map" replace />;

  return (
    <div className="landing">
      <header className="landing-header">
        <span className="brand">Ours</span>
        <button className="secondary" onClick={() => navigate("/login")}>
          Log in
        </button>
      </header>

      <section className="landing-hero">
        <h1>Your neighborhood, in person.</h1>
        <p className="landing-lede">
          Ours is a map of what's happening right around you — gatherings to
          join and neighbors to lend a hand. Not another feed to scroll. A
          nudge to get into a room together.
        </p>
        <div className="row-actions landing-cta">
          <button onClick={() => navigate("/register")}>Get started</button>
          <button className="secondary" onClick={() => navigate("/login")}>
            I already have an account
          </button>
        </div>
      </section>

      <section className="landing-points">
        <div className="landing-point">
          <span className="landing-emoji">🗺️</span>
          <h2>See what's nearby</h2>
          <p>
            Open the app to a live map of local events and help requests, not a
            timeline designed to keep you staring.
          </p>
        </div>
        <div className="landing-point">
          <span className="landing-emoji">🤝</span>
          <h2>Give or get a hand</h2>
          <p>
            Ask a neighbor for help with a task, or offer yours. Small acts,
            real relationships.
          </p>
        </div>
        <div className="landing-point">
          <span className="landing-emoji">🌱</span>
          <h2>Meet, then need us less</h2>
          <p>
            Messaging lives only around real events — because the point is time
            spent together, not time spent on a screen.
          </p>
        </div>
      </section>

      <footer className="landing-footer muted">
        Neighbors helping neighbors. Non-partisan, always.
      </footer>
    </div>
  );
}
