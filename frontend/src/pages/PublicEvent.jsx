import { Link, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { HeartMark } from "../components/Logo.jsx";
import { kindLabel } from "../lib/eventKinds.js";

// What someone sees after scanning a flyer's QR code. The only page in the app
// that shows event data without a login — everything else lives behind
// ProtectedRoute.
//
// It reads from /api/public/events/{id}, which serves public-visibility events
// only and withholds a help request's address. This page can't widen that: it
// renders what it is given.
//
// The job here is not to be an event page. It is to answer "what is this poster
// about, and should I bother signing up" in about four seconds.

function formatWhen(iso) {
  return new Date(iso).toLocaleString([], {
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function PublicEvent() {
  const { id } = useParams();
  const { data: event, error, loading } = useApi(
    () => api.get(`/api/public/events/${id}`),
    [id],
  );

  if (loading) return <div className="org centered muted">Loading…</div>;

  // A flyer outlives the event it advertises, so "not found" is a normal state
  // here, not an error. Say so plainly and offer the way in anyway.
  if (error || !event)
    return (
      <div className="org public-event">
        <Link to="/" className="public-brand">
          <HeartMark size={26} />
          <span className="wordmark">Ours</span>
        </Link>
        <div className="public-card">
          <h1>This one's finished</h1>
          <p className="muted">
            The event on that flyer has ended, been cancelled, or isn't public.
            There's usually something else going on nearby.
          </p>
          <Link className="btn btn-primary" to="/register">
            See what's happening near you
          </Link>
        </div>
      </div>
    );

  return (
    <div className="org public-event">
      <Link to="/" className="public-brand">
        <HeartMark size={26} />
        <span className="wordmark">Ours</span>
      </Link>

      <div className="public-card">
        <div className="notice-tags">
          <span className={`tag tag-${event.kind}`}>{kindLabel(event.kind)}</span>
          {event.tag_name && <span className="tag tag-neutral">{event.tag_name}</span>}
        </div>

        <h1>{event.title}</h1>

        <dl className="public-facts">
          <div>
            <dt>When</dt>
            <dd>{formatWhen(event.starts_at)}</dd>
          </div>
          <div>
            <dt>Where</dt>
            {/* address is null for a help request by design; the neighbourhood
                is what a stranger gets instead. */}
            <dd>{event.address || event.neighborhood || "Nearby"}</dd>
          </div>
          {event.host_name && (
            <div>
              <dt>Hosted by</dt>
              <dd>{event.host_name}</dd>
            </div>
          )}
        </dl>

        {event.description && <p className="public-description">{event.description}</p>}

        <div className="public-cta">
          <Link className="btn btn-primary" to="/register">
            Join and RSVP
          </Link>
          <Link className="btn btn-secondary" to="/login">
            I already have an account
          </Link>
        </div>
        <p className="muted public-footnote">
          Ours is a neighborhood app for meeting the people who live around you.
          No feed, no endless scrolling — just what's happening nearby.
        </p>
      </div>
    </div>
  );
}
