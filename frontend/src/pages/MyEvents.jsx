import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

// Everything the current user has created — both gatherings they're hosting
// and help requests they've posted. Backed by GET /api/users/me/events, which
// (unlike the map) shows events in any status, including cancelled and past.
export default function MyEvents() {
  const { data, error, loading } = useApi(() => api.get("/api/users/me/events"));

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

  return (
    <div className="narrow">
      <h1>Your events</h1>
      <p className="muted">Everything you're hosting or have asked for help with.</p>

      {data.length === 0 ? (
        <p className="muted">
          You haven't created anything yet.{" "}
          <Link to="/events/new">Create an event or help request</Link>.
        </p>
      ) : (
        <ul className="plain-list">
          {data.map((e) => (
            <li key={e.id} className="invite-row">
              <Link to={`/events/${e.id}`} className="event-list-item">
                <span className={`dot dot-${e.kind}`} />
                <span className="event-list-body">
                  <strong>{e.title}</strong>
                  <span className="muted">
                    {e.kind === "help_request" ? "Help request" : "Gathering"}
                    {" · "}
                    {new Date(e.starts_at).toLocaleDateString()}
                    {e.status !== "open" && ` · ${e.status}`}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
