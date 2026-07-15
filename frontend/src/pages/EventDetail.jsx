import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { ConfirmDialog, ReportDialog } from "../components/dialogs.jsx";

const ACTIVE = ["invited", "going", "maybe", "attended"];

export default function EventDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  // Event + participants load together; either failing shows one error.
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

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

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
  const cancelEvent = () =>
    act(() => api.patch(`/api/events/${id}`, { status: "cancelled" }));

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
    <div className="detail-layout">
      <div className="detail-main">
        <Link to="/map" className="muted">
          ← Back to map
        </Link>
        <div className="card">
          <span className={`tag tag-${event.kind}`}>
            {event.kind === "help_request" ? "Help request" : "Gathering"}
          </span>
          <h1>{event.title}</h1>
          <p className="muted">
            {new Date(event.starts_at).toLocaleString()}
            {event.status !== "open" && ` · ${event.status}`}
          </p>
          {event.description && <p>{event.description}</p>}
          {event.address ? (
            <p>
              <strong>Address:</strong> {event.address}
            </p>
          ) : (
            <p className="muted">Exact address shown once you're going.</p>
          )}
          <p className="muted">
            {event.participant_count} going
            {event.capacity != null && ` · capacity ${event.capacity}`}
          </p>

          {actionError && <div className="alert">{actionError}</div>}
          {notice && <p className="muted">{notice}</p>}

          {/* RSVP controls — hidden from the host, who owns the event. */}
          {!isHost && (
            <div className="row-actions">
              <button
                onClick={() => rsvp("going")}
                className={mine?.status === "going" ? "" : "secondary"}
              >
                Going
              </button>
              <button
                onClick={() => rsvp("maybe")}
                className={mine?.status === "maybe" ? "" : "secondary"}
              >
                Maybe
              </button>
              <button
                onClick={() => rsvp("declined")}
                className={mine?.status === "declined" ? "" : "secondary"}
              >
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
              <button className="secondary" onClick={cancelEvent}>
                Cancel event
              </button>
              <button className="danger" onClick={() => setDialog("delete")}>
                Delete
              </button>
            </div>
          )}
          {!isHost && (
            <button className="link-button" onClick={() => setDialog("report")}>
              Report this event
            </button>
          )}
        </div>

        <ConfirmDialog
          open={dialog === "delete"}
          title="Delete this event?"
          body="This permanently removes the event, its RSVPs, and its messages. To call it off but keep the record, use Cancel event instead."
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

      <aside className="detail-side">
        <Participants participants={participants} />
        {canParticipate && <InvitePanel eventId={id} onInvited={reload} />}
      </aside>
    </div>
  );
}

function Participants({ participants }) {
  return (
    <div className="card">
      <h2>Who's coming</h2>
      {participants.length === 0 && <p className="muted">No one yet.</p>}
      <ul className="plain-list">
        {participants.map((p) => (
          <li key={p.user_id}>
            <Link to={`/profile/${p.user_id}`}>{p.display_name}</Link>
            <span className="muted"> · {p.status}</span>
          </li>
        ))}
      </ul>
    </div>
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
    <div className="card">
      <h2>Coordination</h2>
      <p className="muted">Messages are visible to everyone attending.</p>
      {error && <div className="alert">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : (
        <ul className="messages">
          {data.map((m) => (
            <li key={m.id} className={m.sender_id === user.id ? "msg msg-mine" : "msg"}>
              <span className="msg-author">{m.display_name}</span>
              <span className="msg-body">{m.body}</span>
              <span className="msg-time muted">
                {new Date(m.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </li>
          ))}
          {data.length === 0 && <p className="muted">No messages yet.</p>}
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
        />
        <button type="submit">Send</button>
      </form>
    </div>
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
    <div className="card">
      <h2>Invite a connection</h2>
      {status && <p className="muted">{status}</p>}
      {!connections || connections.length === 0 ? (
        <p className="muted">
          You have no connections yet. <Link to="/connections">Find people</Link>.
        </p>
      ) : (
        <ul className="plain-list">
          {connections.map((c) => (
            <li key={c.id} className="invite-row">
              <span>{c.display_name}</span>
              <button className="secondary" onClick={() => invite(c.user_id, c.display_name)}>
                Invite
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
