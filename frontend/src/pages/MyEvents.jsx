import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

function formatWhen(iso) {
  return new Date(iso).toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// The user's personal event lists: what they created, and what they've said
// they're going to. Both endpoints drop events once they've ended, so this
// page only shows things still to come (or happening now).
export default function Events() {
  const { data, error, loading } = useApi(async () => {
    const [created, attending] = await Promise.all([
      api.get("/api/users/me/events"),
      api.get("/api/users/me/attending"),
    ]);
    return { created, attending };
  });

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

  return (
    <div className="org wide">
      <div className="page-head">
        <div>
          <span className="kicker">Yours</span>
          <h1>Your events</h1>
        </div>
        <Link to="/events/new" className="btn">
          <span aria-hidden="true">+</span> New event
        </Link>
      </div>

      <section style={{ marginBottom: "36px" }}>
        <h2>Hosting</h2>
        {data.created.length === 0 ? (
          <p className="muted">
            You haven't created anything yet.{" "}
            <Link to="/events/new">Create an event or help request</Link>.
          </p>
        ) : (
          <EventGrid events={data.created} showAdd />
        )}
      </section>

      <section>
        <h2>Going to</h2>
        {data.attending.length === 0 ? (
          <p className="muted">
            You're not going to anything yet.{" "}
            <Link to="/map">Find something nearby</Link>.
          </p>
        ) : (
          <EventGrid events={data.attending} />
        )}
      </section>
    </div>
  );
}

function EventGrid({ events, showAdd }) {
  return (
    <div className="card-grid">
      {events.map((e) => {
        const help = e.kind === "help_request";
        const status =
          e.my_rsvp && e.my_rsvp !== "attended"
            ? e.my_rsvp === "maybe"
              ? "Maybe"
              : "Going"
            : e.status !== "open"
              ? e.status
              : null;
        return (
          <Link key={e.id} to={`/events/${e.id}`} className="card ev-card">
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <span className={`tag tag-${e.kind}`}>
                {help ? "Help request" : "Gathering"}
              </span>
              {e.tag_name && <span className="tag tag-neutral">{e.tag_name}</span>}
            </div>
            <h3>{e.title}</h3>
            <p className="muted" style={{ margin: 0 }}>
              {formatWhen(e.starts_at)}
            </p>
            {status && (
              <span
                style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "var(--color-accent-700)",
                }}
              >
                {status}
              </span>
            )}
          </Link>
        );
      })}
      {showAdd && (
        <Link to="/events/new" className="card-add">
          <span
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              background: "var(--color-surface)",
              display: "grid",
              placeContent: "center",
              fontSize: "24px",
              lineHeight: 1,
            }}
            aria-hidden="true"
          >
            +
          </span>
          Host something new
        </Link>
      )}
    </div>
  );
}
