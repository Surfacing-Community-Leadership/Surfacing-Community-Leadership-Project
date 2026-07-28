import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { categoryLabel, timeLeft } from "../lib/noticeCategories.js";

const MAX_REPLY_CHARS = 280;

function formatWhen(iso) {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// One notice, and the only place a reply can be written or read.
//
// Two quite different screens share this route. The author sees their replies
// and the controls to take the notice down; everyone else sees a single reply
// box and no hint of who else has answered.
export default function NoticeDetail() {
  const { noticeId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const { data: notice, error, loading, reload } = useApi(
    () => api.get(`/api/notices/${noticeId}`),
    [noticeId],
  );

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
        <Link className="btn btn-secondary" to="/board">
          Back to the board
        </Link>
      </div>
    );

  const isMine = notice.author_id === user?.id;
  const closed = notice.resolved || new Date(notice.expires_at) <= new Date();

  return (
    <div className="org narrow">
      <Link className="link-button" to="/board">
        ← Back to the board
      </Link>

      <div className={`notice-detail nc-${notice.category}`}>
        <div className="notice-tags">
          <span className={`tag tag-${notice.category}`}>
            {categoryLabel(notice.category)}
          </span>
          {notice.resolved && <span className="tag tag-neutral">Sorted</span>}
        </div>
        <h1>{notice.title}</h1>
        <p className="notice-detail-body">{notice.body}</p>
        <div className="notice-meta">
          <Link to={`/profile/${notice.author_id}`}>
            {notice.author_name || "A neighbor"}
            {notice.author_verified && (
              <span className="notice-verified" title="Verified organization">
                {" "}
                ✓
              </span>
            )}
          </Link>
          {notice.place_hint && <span>{notice.place_hint}</span>}
          <span>{timeLeft(notice.expires_at)}</span>
        </div>
      </div>

      {isMine ? (
        <AuthorView notice={notice} onChanged={reload} onDeleted={() => navigate("/board")} />
      ) : (
        <ReplyBox notice={notice} closed={closed} onSent={reload} />
      )}
    </div>
  );
}

// The author's side: who answered, and the controls to wrap it up.
function AuthorView({ notice, onChanged, onDeleted }) {
  const { data: replies, error, loading, reload } = useApi(
    () => api.get(`/api/notices/${notice.id}/replies`),
    [notice.id],
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);

  async function act(fn) {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="notice-owner-bar">
        {actionError && <div className="alert">{actionError}</div>}
        <div className="row-actions">
          {notice.resolved ? (
            <button
              className="btn btn-secondary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api.patch(`/api/notices/${notice.id}`, { resolved: false });
                  await onChanged();
                })
              }
            >
              Put it back up
            </button>
          ) : (
            <button
              className="btn btn-primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api.patch(`/api/notices/${notice.id}`, { resolved: true });
                  await onChanged();
                })
              }
            >
              Mark it sorted
            </button>
          )}
          <button
            className="btn btn-secondary danger"
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api.del(`/api/notices/${notice.id}`);
                onDeleted();
              })
            }
          >
            Take it down
          </button>
        </div>
        <p className="field-hint">
          Marking it sorted frees up one of your slots and keeps it readable for
          a while. Taking it down removes it and its replies for good.
        </p>
      </div>

      <h2 className="notice-replies-head">Replies</h2>
      <p className="muted">Only you can see these.</p>
      {loading ? (
        <p className="muted">Loading…</p>
      ) : error ? (
        <div className="alert">{error}</div>
      ) : replies.length === 0 ? (
        <p className="muted">Nobody has answered yet.</p>
      ) : (
        <ul className="plain-list">
          {replies.map((reply) => (
            <li key={reply.id} className="row-card notice-reply">
              <div className="notice-reply-head">
                <Link to={`/profile/${reply.author_id}`}>
                  {reply.author_name || "A neighbor"}
                </Link>
                <span className="muted">{formatWhen(reply.created_at)}</span>
              </div>
              <p>{reply.body}</p>
            </li>
          ))}
        </ul>
      )}
      <button className="link-button" onClick={reload}>
        Refresh replies
      </button>
    </>
  );
}

// Everyone else's side: one line to the poster, and nothing about who else
// answered. Sending again edits what you already said rather than piling on.
function ReplyBox({ notice, closed, onSent }) {
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [reporting, setReporting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSending(true);
    setError(null);
    try {
      await api.post(`/api/notices/${notice.id}/replies`, { body });
      setSent(true);
      setBody("");
      await onSent();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  if (closed) {
    return (
      <div className="notice-closed">
        <p className="muted">
          This one's closed — {notice.resolved ? "it's been sorted" : "it expired"}.
        </p>
        <Link className="btn btn-secondary" to="/board">
          See what else is up
        </Link>
      </div>
    );
  }

  return (
    <>
      <form className="notice-reply-form" onSubmit={submit}>
        <h2>Reply</h2>
        <p className="muted">
          Goes privately to {notice.author_name || "whoever posted this"} — the
          board has no public comments.
        </p>
        {error && <div className="alert">{error}</div>}
        {sent && !error && (
          <div className="notice-sent">
            Sent. {notice.author_name || "They"} will see it in their alerts.
          </div>
        )}
        <textarea
          className="input"
          rows={3}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          maxLength={MAX_REPLY_CHARS}
          placeholder={
            notice.i_replied
              ? "Replace what you said…"
              : "I'd love the bookshelf — I can pick it up this evening."
          }
          required
        />
        <div className="notice-reply-foot">
          <span className="muted">
            {body.length}/{MAX_REPLY_CHARS}
          </span>
          <button className="btn btn-primary" disabled={sending || !body.trim()}>
            {sending ? "Sending…" : notice.i_replied ? "Replace my reply" : "Send"}
          </button>
        </div>
        {notice.i_replied && !sent && (
          <p className="field-hint">
            You've already replied. Sending again replaces it, and won't ping
            them a second time.
          </p>
        )}
      </form>

      <div className="notice-report">
        {reporting ? (
          <ReportNotice notice={notice} onDone={() => setReporting(false)} />
        ) : (
          <button className="link-button" onClick={() => setReporting(true)}>
            Report this notice
          </button>
        )}
      </div>
    </>
  );
}

function ReportNotice({ notice, onDone }) {
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSending(true);
    setError(null);
    try {
      await api.post("/api/reports", {
        reported_notice_id: notice.id,
        reason: reason || "Reported from the board",
      });
      setSent(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  if (sent)
    return (
      <p className="muted">
        Thanks — it's with the moderators.{" "}
        <button className="link-button" onClick={onDone}>
          Close
        </button>
      </p>
    );

  return (
    <form onSubmit={submit}>
      {error && <div className="alert">{error}</div>}
      <div className="field">
        <label className="field-label" htmlFor="report-reason">
          What's wrong with it?
        </label>
        <input
          id="report-reason"
          className="input"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={200}
          placeholder="Spam, abusive, not a real notice…"
        />
      </div>
      <div className="row-actions">
        <button className="btn btn-secondary" disabled={sending}>
          {sending ? "Sending…" : "Send report"}
        </button>
        <button type="button" className="link-button" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}
