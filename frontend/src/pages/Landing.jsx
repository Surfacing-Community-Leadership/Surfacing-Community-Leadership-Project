import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { BrandLock, HeartMark } from "../components/Logo.jsx";

// The public front door. Reachable by anyone, including signed-in users (they
// land here from the logo), so the calls-to-action adapt: members are pointed
// at their map, everyone else is offered a way in.
export default function Landing() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  if (loading) return <div className="centered muted">Loading…</div>;

  const primary = user
    ? { label: "Open your map", to: "/map" }
    : { label: "Get started", to: "/register" };

  return (
    <div className="lp">
      <header className="poster-nav">
        <div className="poster-nav-inner">
          <a
            className="nav-brand"
            href="/"
            onClick={(e) => {
              e.preventDefault();
              navigate("/");
            }}
          >
            <BrandLock heartSize={24} />
          </a>
          <button
            className="secondary"
            style={{ background: "var(--reverse)" }}
            onClick={() => navigate(user ? "/map" : "/login")}
          >
            {user ? "Open your map" : "Log in"}
          </button>
        </div>
      </header>

      {/* Hero — the product (a live local map) is the most characteristic thing */}
      <section className="hero">
        <div className="hero-grid">
          <div className="hero-copy">
            <span className="eyebrow">A map, not a feed</span>
            <h1 className="hero-head">
              Your
              <br />
              neighborhood,
              <br />
              <span className="under">in person</span>
            </h1>
            <p className="hero-sub">
              Ours opens to a live map of what's happening right around you —
              gatherings to join and neighbors to lend a hand. Not one more
              thing to scroll. A nudge to get into a room together.
            </p>
            <div className="hero-actions">
              <button onClick={() => navigate(primary.to)}>
                {primary.label}
                <span aria-hidden="true">→</span>
              </button>
              {!user && (
                <button className="secondary" onClick={() => navigate("/login")}>
                  I have an account
                </button>
              )}
            </div>
            <p className="hero-meta">Free · Non-partisan · Built to be used less</p>
          </div>

          <div className="hero-visual" aria-hidden="true">
            <div className="plate">
              <span className="plate-label">Live · your area</span>

              <span className="plate-pin" style={{ top: "15%", left: "16%" }}>
                🎵
              </span>
              <span
                className="plate-pin help"
                style={{ top: "26%", left: "66%" }}
              >
                🧰
              </span>
              <span className="plate-pin" style={{ top: "64%", left: "18%" }}>
                🍽️
              </span>
              <span className="plate-pin" style={{ top: "72%", left: "60%" }}>
                📚
              </span>
              <span
                className="plate-pin help"
                style={{ top: "48%", left: "80%" }}
              >
                🌱
              </span>

              <span
                className="plate-you-label"
                style={{ top: "34%", left: "40%" }}
              >
                You
              </span>
              <span
                className="plate-pin you"
                style={{ top: "43%", left: "40%" }}
              >
                <HeartMark size={30} color="var(--text)" />
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Creed — the belief that makes the product different */}
      <section className="creed">
        <div className="creed-inner">
          <div>
            <span className="eyebrow">Why we're built differently</span>
            <p className="creed-statement">
              Success is time spent <span className="accent">together</span> —
              not time on a screen.
            </p>
          </div>
          <div className="creed-foot">
            <p>
              Most apps that promise community make money by keeping you
              scrolling, so they can never really want you to leave. Ours wants
              the opposite: get you into a room with the people nearby, then get
              out of the way.
            </p>
            <p>
              Every message lives inside a real event — there's no open feed,
              because the point was never the app. If you need us a little less
              each month, it's working.
            </p>
          </div>
        </div>
      </section>

      {/* Three principles */}
      <section className="tenets">
        <div className="tenets-head">
          <span className="eyebrow">How it works</span>
        </div>
        <div className="tenets-grid">
          <div className="tenet">
            <span className="tenet-num">01</span>
            <h3>See what's near</h3>
            <p>
              Open to a live map of local gatherings and help requests — the
              real ones happening this week, not a timeline tuned to hold your
              attention.
            </p>
          </div>
          <div className="tenet">
            <span className="tenet-num">02</span>
            <h3>Lend a hand</h3>
            <p>
              Ask a neighbor for help with a task, or answer someone who did.
              Small, specific, and close to home — the way trust actually
              starts.
            </p>
          </div>
          <div className="tenet">
            <span className="tenet-num">03</span>
            <h3>Meet, then log off</h3>
            <p>
              RSVP, show up, swap numbers. Coordination stays inside the event,
              and once you've met, you don't need Ours to keep in touch.
            </p>
          </div>
        </div>
      </section>

      {/* Marquee call to action */}
      <section className="marquee">
        <div className="marquee-card">
          <span className="eyebrow">Start where you live</span>
          <h2>Open the map. See who's around.</h2>
          <button className="cta-btn" onClick={() => navigate(primary.to)}>
            {user ? "Open your map" : "Get started"}
            <span aria-hidden="true">→</span>
          </button>
          <span className="marquee-heart">
            <HeartMark size={180} color="var(--accent-deep)" />
          </span>
        </div>
      </section>

      <footer className="poster-foot">
        <div className="poster-foot-inner">
          <a
            className="nav-brand"
            href="/"
            onClick={(e) => {
              e.preventDefault();
              navigate("/");
            }}
          >
            <BrandLock heartSize={22} />
          </a>
          <span className="poster-foot-note">
            Neighbors helping neighbors · Non-partisan, always
          </span>
        </div>
      </footer>
    </div>
  );
}
