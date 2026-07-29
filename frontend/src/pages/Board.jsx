import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import CommunityPicker from "../components/CommunityPicker.jsx";
import LocationPicker from "../components/LocationPicker.jsx";
import StarButton from "../components/StarButton.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import {
  CATEGORY_ORDER,
  NOTICE_CATEGORIES,
  categoryHint,
  categoryLabel,
  categoryShort,
  isLongForm,
  suggestsPin,
  timeLeft,
} from "../lib/noticeCategories.js";

// The neighborhood notice board: things worth knowing that aren't invitations.
// Anything you can show up to is an event and lives on the map instead.
//
// No endless feed, no ranking by engagement, no comment threads — every one of
// those is how a neighborhood board turns into an argument. What keeps it
// readable: everything expires, everyone gets a small allowance, replies go
// privately to whoever posted, and the one piece of prominence on the page
// (Post of the Day) rotates on a 24-hour window rather than accumulating.
export default function Board() {
  const [filter, setFilter] = useState("all");
  const [composing, setComposing] = useState(false);

  const meta = useApi(() => api.get("/api/notices/meta"));
  const top = useApi(() => api.get("/api/notices/top"));
  const board = useApi(() => {
    const params = new URLSearchParams();
    if (filter === "mine") params.set("mine", "true");
    else if (filter === "official") params.set("official", "true");
    else if (filter !== "all") params.set("category", filter);
    return api.get(`/api/notices?${params}`);
  }, [filter]);

  async function refresh() {
    await Promise.all([meta.reload(), board.reload(), top.reload()]);
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

  const showTop = filter === "all" && top.data;
  // Don't print the same notice twice: when it's highlighted above, it comes out
  // of the grid rather than appearing in both places.
  const listed = showTop
    ? (board.data || []).filter((n) => n.id !== top.data.id)
    : board.data || [];

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
        Things worth knowing around here. Everything comes down on its own, and
        replies go straight to whoever posted — nothing here is a public
        conversation.
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
          meta={meta.data}
          onPosted={async () => {
            setComposing(false);
            await refresh();
          }}
          onCancel={() => setComposing(false)}
        />
      )}

      {showTop && <PostOfTheDay notice={top.data} onStar={() => top.reload()} />}

      <Filters value={filter} onChange={setFilter} categories={meta.data.categories} />

      {board.loading ? (
        <p className="muted">Loading…</p>
      ) : board.error ? (
        <div className="alert">{board.error}</div>
      ) : listed.length === 0 ? (
        <p className="muted board-empty">
          {showTop ? "Nothing else on the board right now." : emptyMessage(filter)}
        </p>
      ) : (
        <div className="card-grid">
          {listed.map((notice) => (
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

function emptyMessage(filter) {
  if (filter === "mine") return "You haven't put anything up yet.";
  if (filter === "official")
    return "No official notices right now. Verified organizations post here.";
  if (filter === "all")
    return "Nothing on the board right now. A quiet board is a fine thing.";
  return "Nothing of this kind right now.";
}

// One highlighted notice, chosen by stars earned in the last 24 hours. One post,
// no numbers-vs-numbers leaderboard, and the author is never told they won —
// a spotlight rather than a scoreboard.
function PostOfTheDay({ notice, onStar }) {
  return (
    <section className="potd" aria-label="Community post of the day">
      <span className="potd-kicker">★ Post of the day</span>
      <Link to={`/board/${notice.id}`} className={`potd-card nc-${notice.category}`}>
        <div className="notice-tags">
          <span className={`tag tag-${notice.category}`}>
            {categoryShort(notice.category)}
          </span>
          {notice.author_verified && <span className="tag tag-official">Official</span>}
        </div>
        <h2>{notice.title}</h2>
        <p className="notice-body">{notice.body}</p>
        <div className="notice-meta">
          <span>{notice.author_name || "A neighbor"}</span>
          {notice.place_hint && <span>{notice.place_hint}</span>}
          <span>{timeLeft(notice.expires_at)}</span>
        </div>
      </Link>
      <div className="potd-foot">
        <StarButton notice={notice} onChange={onStar} />
        <span className="muted">Most starred in the last day. Resets daily.</span>
      </div>
    </section>
  );
}

function Filters({ value, onChange, categories }) {
  return (
    // Horizontally scrollable rather than wrapping: nine types plus three
    // pseudo-filters would otherwise stack three rows deep on a phone.
    <div className="pill-tabs board-filters">
      <button
        className={value === "all" ? "pill-tab on" : "pill-tab"}
        onClick={() => onChange("all")}
      >
        Everything
      </button>
      <button
        className={value === "official" ? "pill-tab on" : "pill-tab"}
        onClick={() => onChange("official")}
      >
        Official
      </button>
      {CATEGORY_ORDER
        // Only offer filters for types this account could encounter: the
        // org-only ones stay off a personal account's strip.
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
        {notice.author_verified && <span className="tag tag-official">Official</span>}
        {notice.location && (
          <span className="tag tag-neutral" title="Pinned on the map">
            ◎ On the map
          </span>
        )}
        {notice.resolved && <span className="tag tag-neutral">Sorted</span>}
      </div>
      <h3>{notice.title}</h3>
      <p className={isLongForm(notice.category) ? "notice-body clamp-2" : "notice-body"}>
        {notice.body}
      </p>
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
      <div className="notice-card-foot">
        <StarButton notice={notice} />
      </div>
    </Link>
  );
}

function ComposeNotice({ meta, onPosted, onCancel }) {
  const categories = meta.categories;
  const here = useGeolocation();
  const [category, setCategory] = useState(categories[0] || "giveaway");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [placeHint, setPlaceHint] = useState("");
  const [expiryDays, setExpiryDays] = useState(meta.default_expiry_days);
  const [allowInquiries, setAllowInquiries] = useState(true);
  const [pinned, setPinned] = useState(false);
  const [location, setLocation] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  // Follow the pin once it's placed, so fine-tuning doesn't fight the map.
  const mapCenter = location ? [location.lat, location.lng] : here;

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const expires = new Date();
      expires.setDate(expires.getDate() + Number(expiryDays));
      await api.post("/api/notices", {
        category,
        title,
        body,
        place_hint: placeHint || null,
        location: pinned ? location : null,
        allow_direct_inquiries: allowInquiries,
        expires_at: expires.toISOString(),
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
          What kind of post
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
          rows={isLongForm(category) ? 10 : 4}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          maxLength={meta.max_body_chars}
          required
        />
        <p className="field-hint">
          {categoryHint(category)}
          {isLongForm(category) && (
            <>
              {" "}
              <span className="muted">
                {body.length}/{meta.max_body_chars}
              </span>
            </>
          )}
        </p>
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
        <p className="field-hint">A landmark usually reads better than an address.</p>
      </div>

      <div className="field">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={pinned}
            onChange={(e) => setPinned(e.target.checked)}
          />
          Also drop a pin on the map
          {suggestsPin(category) && <span className="muted"> — useful for this kind</span>}
        </label>
        {pinned && (
          <>
            {/* LocationPicker needs an explicit centre — Leaflet can't
                initialise a view without one, and the map renders blank. */}
            {mapCenter ? (
              <div className="picker-map">
                <LocationPicker
                  center={mapCenter}
                  value={location}
                  onPick={setLocation}
                />
              </div>
            ) : (
              <div className="picker-map centered muted">Locating…</div>
            )}
            <p className="field-hint">
              Click the map to place it. Informational only — it appears as a
              muted pin so nobody mistakes it for something to attend.
            </p>
          </>
        )}
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-expiry">
          Take it down after
        </label>
        <select
          id="notice-expiry"
          className="input"
          value={expiryDays}
          onChange={(e) => setExpiryDays(e.target.value)}
        >
          {meta.expiry_choices_days.map((days) => (
            <option key={days} value={days}>
              {days === 7 ? "A week" : days === 14 ? "Two weeks" : days === 30 ? "A month" : "Three months"}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={allowInquiries}
            onChange={(e) => setAllowInquiries(e.target.checked)}
          />
          Let neighbors send me a private reply
        </label>
        <p className="field-hint">
          Replies come to you alone and never appear on the board. Turn this off
          for something nobody needs to answer.
        </p>
      </div>

      <div className="row-actions">
        <button className="btn btn-primary" disabled={saving || (pinned && !location)}>
          {saving ? "Putting it up…" : "Put it up"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {pinned && !location && (
        <p className="field-hint">Tap the map to place your pin.</p>
      )}
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
