import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { ConfirmDialog, ReportDialog } from "../components/dialogs.jsx";
import { tagIcon } from "../lib/tagIcons.js";
import { isHelpKind, kindLabel } from "../lib/eventKinds.js";

const ACTIVE = ["invited", "going", "maybe", "attended"];
// Mirrors the backend: without an end time an event is assumed to run 3 hours.
const ASSUMED_HOURS = 3;
const MIN_REFLECTION_WORDS = 20;

function initial(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}
function tint(seed) {
  return (String(seed).charCodeAt(0) || 0) % 2 ? "warm" : "";
}

function hasEnded(event) {
  const end = event.ends_at
    ? new Date(event.ends_at)
    : new Date(new Date(event.starts_at).getTime() + ASSUMED_HOURS * 3600 * 1000);
  return end < new Date();
}

function countWords(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
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
  const ended = hasEnded(event);

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
              <span className={`tag tag-${event.kind}`}>{kindLabel(event.kind)}</span>
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

          {/* After the event: confirm you were there, or (for a help request
              you posted) thank the neighbors who turned up. */}
          {ended && !isHost && mine?.status !== "attended" && (
            <AttendanceCard eventId={id} onDone={reload} />
          )}
          {ended && mine?.status === "attended" && (
            <p className="muted attendance-done">
              ✓ You confirmed you were here — it counts toward your record.
            </p>
          )}
          {ended && isHost && isHelpKind(event.kind) && (
            <ThanksPanel
              eventId={id}
              participants={participants}
              volunteer={event.kind === "volunteer_work"}
            />
          )}

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

// Self-confirming attendance. The reflection is required: it's what keeps the
// public count honest, and it stays private to whoever wrote it.
function AttendanceCard({ eventId, onDone }) {
  const [reflection, setReflection] = useState("");
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const words = countWords(reflection);
  const short = words < MIN_REFLECTION_WORDS;

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.post(`/api/events/${eventId}/attendance`, { reflection });
      await onDone?.();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <section className="card attendance-card">
      <h2 style={{ fontSize: "20px", margin: 0 }}>Were you there?</h2>
      <p className="muted" style={{ margin: 0 }}>
        Confirm it and jot down how it went. Your note stays private — only the
        confirmation counts toward your record.
      </p>
      {error && <div className="alert">{error}</div>}
      <form onSubmit={submit} style={{ display: "grid", gap: "10px" }}>
        <textarea
          value={reflection}
          onChange={(e) => setReflection(e.target.value)}
          rows={3}
          maxLength={2000}
          placeholder="Who did you meet? What would you do differently next time?"
          aria-label="Your reflection"
        />
        <div className="attendance-foot">
          <span className={short ? "muted" : "words-ok"}>
            {words} / {MIN_REFLECTION_WORDS} words
          </span>
          <button type="submit" disabled={short || saving}>
            {saving ? "Saving…" : "I was there"}
          </button>
        </div>
      </form>
    </section>
  );
}

// Only the neighbor who asked for help can confirm who actually helped, which
// is what makes the "helped" count on a profile worth anything.
function ThanksPanel({ eventId, participants, volunteer = false }) {
  const { data: thanked, reload } = useApi(
    () => api.get(`/api/events/${eventId}/thanks`),
    [eventId],
  );
  const [openFor, setOpenFor] = useState(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState(null);

  const helpers = participants.filter((p) => ACTIVE.includes(p.status));
  if (helpers.length === 0) return null;

  async function send(helperId) {
    setError(null);
    try {
      await api.post(`/api/events/${eventId}/thanks`, {
        helper_id: helperId,
        note: note.trim() || null,
      });
      setOpenFor(null);
      setNote("");
      await reload();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="card">
      <h2 style={{ fontSize: "20px", margin: 0 }}>
        {volunteer ? "Who volunteered?" : "Who helped you out?"}
      </h2>
      <p className="muted" style={{ margin: 0 }}>
        {volunteer
          ? "Confirming adds to each volunteer's record — and sends them your note."
          : "Saying thanks adds to their record — and sends them your note."}
      </p>
      {error && <div className="alert">{error}</div>}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "12px" }}>
        {helpers.map((p) => {
          const already = thanked?.includes(p.user_id);
          return (
            <li key={p.user_id} style={{ display: "grid", gap: "8px" }}>
              <div className="invite-row">
                <span style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
                  <span className={`avatar-initial sm ${tint(p.display_name)}`}>
                    {initial(p.display_name)}
                  </span>
                  {p.display_name}
                </span>
                {already ? (
                  <span className="muted">{volunteer ? "✓ Confirmed" : "✓ Thanked"}</span>
                ) : (
                  <button
                    className="secondary"
                    style={{ fontSize: "12px", padding: "6px 14px" }}
                    onClick={() => setOpenFor(openFor === p.user_id ? null : p.user_id)}
                  >
                    {volunteer ? "Confirm" : "Say thanks"}
                  </button>
                )}
              </div>
              {openFor === p.user_id && (
                <div style={{ display: "grid", gap: "8px" }}>
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={2}
                    maxLength={500}
                    placeholder={`A quick note to ${p.display_name} (optional)`}
                    aria-label="Thank-you note"
                  />
                  <div className="row-actions" style={{ marginTop: 0 }}>
                    <button onClick={() => send(p.user_id)}>
                      {volunteer ? "Confirm volunteer" : "Send thanks"}
                    </button>
                    <button className="link-button" onClick={() => setOpenFor(null)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
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
