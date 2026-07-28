import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import CommunityPicker from "../components/CommunityPicker.jsx";
import {
  NOTICE_CATEGORIES,
  categoryHint,
  categoryLabel,
  categoryShort,
  timeLeft,
} from "../lib/noticeCategories.js";

// The neighborhood notice board: things worth knowing that aren't invitations.
// Anything you can show up to is an event and lives on the map instead.
//
// There is no feed, no ranking, no comment threads and no vote counts here, by
// design — every one of those is how a neighborhood board turns into an
// argument. What keeps it readable instead: everything expires, everyone gets
// a small allowance of posts, and replies go privately to whoever posted.
export default function Board() {
  const [filter, setFilter] = useState("all");
  const [composing, setComposing] = useState(false);

  const meta = useApi(() => api.get("/api/notices/meta"));
  const board = useApi(() => {
    const params = new URLSearchParams();
    if (filter === "mine") params.set("mine", "true");
    else if (filter !== "all") params.set("category", filter);
    return api.get(`/api/notices?${params}`);
  }, [filter]);

  async function refresh() {
    await Promise.all([meta.reload(), board.reload()]);
  }

  if (meta.loading) return <div className="org centered muted">Loading…</div>;
  if (meta.error)
    return (
      <div className="org narrow">
        <div className="alert">{meta.error}</div>
      </div>
    );

  // No neighborhood set means there is no board to show — the board is a place,
  // not a radius. Offer the same picker onboarding uses rather than an error.
  if (!meta.data.community_id) return <ChooseNeighborhood onDone={refresh} />;

  return (
    <div className="org wide">
      <div className="page-head">
        <div>
          <span className="kicker">{meta.data.community_name}</span>
          <h1>Notice board</h1>
        </div>
        {meta.data.can_post ? (
          <button className="btn" onClick={() => setComposing((v) => !v)}>
            {composing ? "Never mind" : "Put up a notice"}
          </button>
        ) : null}
      </div>

      <p className="muted board-intro">
        Things worth knowing around here. Everything comes down after a couple of
        weeks, and replies go straight to whoever posted — nothing here is a
        public conversation.
      </p>

      {!meta.data.can_post && (
        <div className="board-blocked">
          {meta.data.blocked_reason}
          {meta.data.live_count >= meta.data.max_live && (
            <>
              {" "}
              <button className="link-button" onClick={() => setFilter("mine")}>
                Manage yours
              </button>
            </>
          )}
        </div>
      )}

      {composing && (
        <ComposeNotice
          categories={meta.data.categories}
          onPosted={async () => {
            setComposing(false);
            await refresh();
          }}
          onCancel={() => setComposing(false)}
        />
      )}

      <Filters value={filter} onChange={setFilter} categories={meta.data.categories} />

      {board.loading ? (
        <p className="muted">Loading…</p>
      ) : board.error ? (
        <div className="alert">{board.error}</div>
      ) : board.data.length === 0 ? (
        <p className="muted board-empty">
          {filter === "mine"
            ? "You haven't put anything up yet."
            : filter === "all"
              ? "Nothing on the board right now. A quiet board is a fine thing."
              : "Nothing in this category right now."}
        </p>
      ) : (
        <div className="card-grid">
          {board.data.map((notice) => (
            <NoticeCard key={notice.id} notice={notice} />
          ))}
        </div>
      )}

      {filter !== "mine" && (
        <p className="muted allowance">
          You have {meta.data.live_count} of {meta.data.max_live} notices up.
        </p>
      )}
    </div>
  );
}

function Filters({ value, onChange, categories }) {
  return (
    <div className="pill-tabs board-filters">
      <button
        className={value === "all" ? "pill-tab on" : "pill-tab"}
        onClick={() => onChange("all")}
      >
        Everything
      </button>
      {Object.keys(NOTICE_CATEGORIES)
        // Only offer filters for categories this account could encounter:
        // the org-only ones are hidden from a personal account's tab strip.
        .filter((key) => categories.includes(key) || !NOTICE_CATEGORIES[key].orgOnly)
        .map((key) => (
          <button
            key={key}
            className={value === key ? "pill-tab on" : "pill-tab"}
            onClick={() => onChange(key)}
          >
            {categoryShort(key)}
          </button>
        ))}
      <button
        className={value === "mine" ? "pill-tab on" : "pill-tab"}
        onClick={() => onChange("mine")}
      >
        Yours
      </button>
    </div>
  );
}

function NoticeCard({ notice }) {
  return (
    <Link to={`/board/${notice.id}`} className={`card notice-card nc-${notice.category}`}>
      <div className="notice-tags">
        <span className={`tag tag-${notice.category}`}>
          {categoryShort(notice.category)}
        </span>
        {notice.resolved && <span className="tag tag-neutral">Sorted</span>}
      </div>
      <h3>{notice.title}</h3>
      <p className="notice-body">{notice.body}</p>
      <div className="notice-meta">
        <span>
          {notice.author_name || "A neighbor"}
          {notice.author_verified && (
            <span className="notice-verified" title="Verified organization">
              {" "}
              ✓
            </span>
          )}
        </span>
        {notice.place_hint && <span>{notice.place_hint}</span>}
        <span>{timeLeft(notice.expires_at)}</span>
        {notice.reply_count ? (
          <span className="notice-replies">
            {notice.reply_count} {notice.reply_count === 1 ? "reply" : "replies"}
          </span>
        ) : null}
        {notice.i_replied && <span className="notice-replies">You replied</span>}
      </div>
    </Link>
  );
}

function ComposeNotice({ categories, onPosted, onCancel }) {
  const [category, setCategory] = useState(categories[0] || "giveaway");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [placeHint, setPlaceHint] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/notices", {
        category,
        title,
        body,
        place_hint: placeHint || null,
      });
      await onPosted();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <form className={`notice-form form-${category}`} onSubmit={submit}>
      <h2>Put up a notice</h2>
      {error && <div className="alert">{error}</div>}

      <div className="field">
        <label className="field-label" htmlFor="notice-category">
          What kind
        </label>
        <select
          id="notice-category"
          className="input"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {categories.map((key) => (
            <option key={key} value={key}>
              {categoryLabel(key)}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-title">
          Headline
        </label>
        <input
          id="notice-title"
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={140}
          placeholder="Free bookshelf"
          required
        />
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-body">
          Details
        </label>
        <textarea
          id="notice-body"
          className="input"
          rows={4}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          maxLength={2000}
          required
        />
        <p className="field-hint">{categoryHint(category)}</p>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-place">
          Whereabouts <span className="muted">(optional)</span>
        </label>
        <input
          id="notice-place"
          className="input"
          value={placeHint}
          onChange={(e) => setPlaceHint(e.target.value)}
          maxLength={200}
          placeholder="44th St between 5th and 6th"
        />
        <p className="field-hint">
          A landmark reads better than an address — this never goes on the map.
        </p>
      </div>

      <div className="row-actions">
        <button className="btn btn-primary" disabled={saving}>
          {saving ? "Putting it up…" : "Put it up"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <p className="field-hint">
        It comes down on its own in two weeks. You can take it down or mark it
        sorted any time.
      </p>
    </form>
  );
}

// Shown when the account has no neighborhood yet: the board is scoped to one,
// so there is genuinely nothing to render until they pick.
function ChooseNeighborhood({ onDone }) {
  const [communityId, setCommunityId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.patch("/api/profiles/me", { community_id: communityId });
      await onDone();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <div className="org narrow">
      <span className="kicker">Notice board</span>
      <h1>Which neighborhood is yours?</h1>
      <p className="muted">
        The board belongs to a neighborhood rather than a radius, so everyone
        nearby reads the same one. Pick yours to see it.
      </p>
      {error && <div className="alert">{error}</div>}
      <CommunityPicker value={communityId} onChange={setCommunityId} />
      <div className="row-actions">
        <button className="btn btn-primary" onClick={save} disabled={!communityId || saving}>
          {saving ? "Saving…" : "Show me the board"}
        </button>
        <Link className="btn btn-secondary" to="/map">
          Back to the map
        </Link>
      </div>
    </div>
  );
}
