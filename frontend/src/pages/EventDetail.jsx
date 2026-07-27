import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { ConfirmDialog, ReportDialog } from "../components/dialogs.jsx";
import { tagIcon } from "../lib/tagIcons.js";

const ACTIVE = ["invited", "going", "maybe", "attended"];

function initial(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}
function tint(seed) {
  return (String(seed).charCodeAt(0) || 0) % 2 ? "warm" : "";
}

export default function EventDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data, error, loading, reload } = useApi(async () => {
    const [event, participants] = await Promise.all([
      api.get(`/api/events/${id}`),
      api.get(`/api/events/${id}/participants`),
    ]);
    return { event, participants };
  }, [id]);

  const [actionError, setActionError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [dialog, setDialog] = useState(null); // "delete" | "report" | null

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

  const { event, participants } = data;
  const isHost = event.host_id === user.id;
  const mine = participants.find((p) => p.user_id === user.id);
  const canParticipate = isHost || (mine && ACTIVE.includes(mine.status));

  async function act(fn) {
    setActionError(null);
    try {
      await fn();
      await reload();
    } catch (err) {
      setActionError(err.message);
    }
  }

  const rsvp = (status) => act(() => api.put(`/api/events/${id}/rsvp`, { status }));
  const withdraw = () => act(() => api.del(`/api/events/${id}/rsvp`));
  const cancelEvent = () => act(() => api.patch(`/api/events/${id}`, { status: "cancelled" }));

  async function deleteEvent() {
    setDialog(null);
    try {
      await api.del(`/api/events/${id}`);
      navigate("/map");
    } catch (err) {
      setActionError(err.message);
    }
  }

  async function report(reason) {
    setDialog(null);
    setNotice(null);
    try {
      await api.post("/api/reports", { reported_event_id: id, reason });
      setNotice("Thanks — this has been sent to the moderators.");
    } catch (err) {
      setActionError(err.message);
    }
  }

  return (
    <div className="org">
      <Link to="/map" className="link-button" style={{ display: "inline-block", marginBottom: "22px" }}>
        ← Back to map
      </Link>

      <div className="detail-layout" style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "24px", alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "20px", minWidth: 0 }}>
          <section className="card" style={{ padding: "30px", gap: "16px", marginBottom: 0 }}>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <span className={`tag tag-${event.kind}`}>
                {event.kind === "help_request" ? "Help request" : "Gathering"}
              </span>
              {event.tag_name && (
                <span className="tag tag-category">
                  {tagIcon(event.tag_slug)} {event.tag_name}
                </span>
              )}
              {event.source === "imported" && (
                <span className="tag tag-imported" title="Found outside Ours">
                  Imported ↗
                </span>
              )}
            </div>
            <h1 style={{ margin: 0 }}>{event.title}</h1>
            <p className="muted" style={{ margin: 0 }}>
              {new Date(event.starts_at).toLocaleString([], {
                weekday: "long",
                month: "long",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
              {event.status !== "open" && ` · ${event.status}`}
            </p>
            {event.description && (
              <p style={{ margin: 0, fontSize: "16px", lineHeight: 1.65 }}>{event.description}</p>
            )}
            {event.address ? (
              <p style={{ margin: 0, fontSize: "14px" }}>
                <strong>Where:</strong> {event.address}
              </p>
            ) : (
              <p className="muted" style={{ margin: 0 }}>Exact address shown once you're going.</p>
            )}
            {event.external_url && (
              <p style={{ margin: 0 }}>
                <a href={event.external_url} target="_blank" rel="noreferrer">
                  Event page &amp; tickets ↗
                </a>
              </p>
            )}
            <p className="muted" style={{ margin: 0 }}>
              {event.participant_count} going
              {event.capacity != null && ` · capacity ${event.capacity}`}
            </p>

            {actionError && <div className="alert" style={{ marginBottom: 0 }}>{actionError}</div>}
            {notice && <p className="muted" style={{ margin: 0 }}>{notice}</p>}

            {!isHost && (
              <div className="row-actions">
                <button onClick={() => rsvp("going")} className={mine?.status === "going" ? "" : "secondary"}>
                  Going
                </button>
                <button onClick={() => rsvp("maybe")} className={mine?.status === "maybe" ? "" : "secondary"}>
                  Maybe
                </button>
                <button onClick={() => rsvp("declined")} className={mine?.status === "declined" ? "" : "secondary"}>
                  Can't go
                </button>
                {mine && (
                  <button onClick={withdraw} className="link-button">
                    Withdraw
                  </button>
                )}
              </div>
            )}

            {isHost && (
              <div className="row-actions">
                <button className="secondary" onClick={() => navigate(`/events/${id}/edit`)}>
                  Edit
                </button>
                <button className="secondary" onClick={cancelEvent}>
                  Cancel event
                </button>
                <button className="danger" onClick={() => setDialog("delete")}>
                  Delete
                </button>
              </div>
            )}
            {!isHost && (
              <button className="link-button" onClick={() => setDialog("report")} style={{ alignSelf: "flex-start" }}>
                Report this event
              </button>
            )}
          </section>

          <ConfirmDialog
            open={dialog === "delete"}
            title="Delete this event?"
            body="This permanently removes the event, its RSVPs, and its messages. Attendees will be notified. To call it off but keep the record, use Cancel event instead."
            confirmLabel="Delete forever"
            danger
            onConfirm={deleteEvent}
            onClose={() => setDialog(null)}
          />
          <ReportDialog
            open={dialog === "report"}
            what="this event"
            onSubmit={report}
            onClose={() => setDialog(null)}
          />

          {canParticipate && <Messages eventId={id} />}
        </div>

        <aside style={{ display: "flex", flexDirection: "column", gap: "20px", minWidth: 0 }}>
          <Participants participants={participants} />
          {canParticipate && <InvitePanel eventId={id} onInvited={reload} />}
        </aside>
      </div>
    </div>
  );
}

function Participants({ participants }) {
  return (
    <section className="card" style={{ padding: "24px", gap: "12px", marginBottom: 0 }}>
      <h2 style={{ fontSize: "18px", margin: 0 }}>Who's coming</h2>
      {participants.length === 0 && <p className="muted" style={{ margin: 0 }}>No one yet.</p>}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "12px" }}>
        {participants.map((p) => (
          <li key={p.user_id} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span className={`avatar-initial sm ${tint(p.display_name)}`}>{initial(p.display_name)}</span>
            <Link to={`/profile/${p.user_id}`} style={{ fontSize: "14px", fontWeight: 600, textDecoration: "none" }}>
              {p.display_name}
            </Link>
            <span className="muted" style={{ fontSize: "12px" }}>· {p.status}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Messages({ eventId }) {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi(
    () => api.get(`/api/events/${eventId}/messages`),
    [eventId],
  );
  const [body, setBody] = useState("");
  const [sendError, setSendError] = useState(null);

  async function send(e) {
    e.preventDefault();
    setSendError(null);
    try {
      await api.post(`/api/events/${eventId}/messages`, { body });
      setBody("");
      await reload();
    } catch (err) {
      setSendError(err.message);
    }
  }

  return (
    <section className="card" style={{ padding: "26px", gap: "14px", marginBottom: 0 }}>
      <h2 style={{ fontSize: "20px", margin: 0 }}>Coordination</h2>
      <p className="muted" style={{ margin: 0 }}>Messages are visible to everyone attending.</p>
      {error && <div className="alert">{error}</div>}
      {loading ? (
        <p className="muted" style={{ margin: 0 }}>Loading…</p>
      ) : (
        <ul className="messages">
          {data.map((m) => (
            <li key={m.id} className={m.sender_id === user.id ? "msg msg-mine" : "msg"}>
              <span className="msg-author">{m.display_name}</span>
              <span className="msg-body">{m.body}</span>
              <span className="msg-time">
                {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </li>
          ))}
          {data.length === 0 && <p className="muted" style={{ margin: 0 }}>No messages yet.</p>}
        </ul>
      )}
      {sendError && <div className="alert">{sendError}</div>}
      <form className="message-form" onSubmit={send}>
        <input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write a message…"
          maxLength={2000}
          required
          style={{ flex: 1 }}
        />
        <button type="submit">Send</button>
      </form>
    </section>
  );
}

function InvitePanel({ eventId, onInvited }) {
  const { data: connections } = useApi(() => api.get("/api/connections"));
  const [status, setStatus] = useState(null);

  async function invite(userId, name) {
    setStatus(null);
    try {
      await api.post(`/api/events/${eventId}/invites`, { user_id: userId });
      setStatus(`Invited ${name}.`);
      onInvited?.();
    } catch (err) {
      setStatus(err.message);
    }
  }

  return (
    <section className="card" style={{ padding: "24px", gap: "12px", marginBottom: 0 }}>
      <h2 style={{ fontSize: "18px", margin: 0 }}>Invite a connection</h2>
      {status && <p className="muted" style={{ margin: 0 }}>{status}</p>}
      {!connections || connections.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>
          You have no connections yet. <Link to="/connections">Find people</Link>.
        </p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "10px" }}>
          {connections.map((c) => (
            <li key={c.id} className="invite-row">
              <span style={{ fontSize: "14px" }}>{c.display_name}</span>
              <button className="secondary" onClick={() => invite(c.user_id, c.display_name)} style={{ fontSize: "12px", padding: "6px 14px" }}>
                Invite
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
