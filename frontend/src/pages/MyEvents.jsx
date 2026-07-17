import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

// The user's personal event lists: what they created, and what they've said
// they're going to. Both are backed by endpoints that drop events once they've
// ended, so this page only shows things still to come (or happening now).
export default function Events() {
  const { data, error, loading } = useApi(async () => {
    const [created, attending] = await Promise.all([
      api.get("/api/users/me/events"),
      api.get("/api/users/me/attending"),
    ]);
    return { created, attending };
  });

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

  return (
    <div className="narrow">
      <h1>Events</h1>

      <section>
        <h2>Hosting</h2>
        {data.created.length === 0 ? (
          <p className="muted">
            You haven't created anything yet.{" "}
            <Link to="/events/new">Create an event or help request</Link>.
          </p>
        ) : (
          <EventList events={data.created} />
        )}
      </section>

      <section>
        <h2>Going to</h2>
        {data.attending.length === 0 ? (
          <p className="muted">
            You're not going to anything yet. <Link to="/map">Find something nearby</Link>.
          </p>
        ) : (
          <EventList events={data.attending} />
        )}
      </section>
    </div>
  );
}

function EventList({ events }) {
  return (
    <ul className="plain-list">
      {events.map((e) => (
        <li key={e.id} className="invite-row">
          <Link to={`/events/${e.id}`} className="event-list-item">
            <span className={`dot dot-${e.kind}`} />
            <span className="event-list-body">
              <strong>{e.title}</strong>
              <span className="muted">
                {e.kind === "help_request" ? "Help request" : "Gathering"}
                {" · "}
                {new Date(e.starts_at).toLocaleDateString()}
                {e.my_rsvp
                  ? ` · ${e.my_rsvp === "maybe" ? "Maybe" : "Going"}`
                  : e.status !== "open" && ` · ${e.status}`}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
