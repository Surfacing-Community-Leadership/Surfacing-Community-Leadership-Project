import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import AddressAutocomplete from "../components/AddressAutocomplete.jsx";
import CommunityPicker from "../components/CommunityPicker.jsx";
import LocationPicker from "../components/LocationPicker.jsx";
import StarButton from "../components/StarButton.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import {
  categoryHint,
  categoryLabel,
  categoryShort,
  isLongForm,
  suggestsPin,
  timeLeft,
} from "../lib/noticeCategories.js";

// The community board: things worth knowing that aren't invitations. Anything
// you can show up to is an event and lives on the map instead.
//
// No endless feed, no ranking by engagement, no comment threads — every one of
// those is how a neighborhood board turns into an argument. What keeps it
// readable: everything expires, everyone gets a small allowance, replies go
// privately to whoever posted, and the one piece of prominence on the page
// (Post of the day) rotates on a 24-hour window rather than accumulating.
//
// Three tabs, not a filter per post type. Posts and Organizations partition the
// board between them — see SOURCES in the router for why "Posts" is
// "everything not official" rather than "people only".
const TABS = [
  { key: "posts", label: "Posts" },
  { key: "organizations", label: "Organizations" },
  { key: "mine", label: "My posts" },
];

// A page, not an endless scroll. Six is enough to scan without the board
// becoming something you fall down.
const PAGE_SIZE = 6;

export default function Board() {
  const [tab, setTab] = useState("posts");
  const [page, setPage] = useState(0);
  const [composing, setComposing] = useState(false);

  const meta = useApi(() => api.get("/api/notices/meta"));
  const top = useApi(() => api.get("/api/notices/top"));

  // The highlight is shown above the list on the Posts tab, so the server drops
  // it from the results — filtering it out here instead would leave whichever
  // page contains it one post short.
  const excludeId = tab === "posts" ? top.data?.id : null;

  const board = useApi(() => {
    const params = new URLSearchParams();
    if (tab === "mine") params.set("mine", "true");
    else params.set("source", tab);
    if (excludeId) params.set("exclude_id", excludeId);
    // One extra row is fetched purely to answer "is there a next page?" without
    // a second count query. It is never rendered.
    params.set("limit", String(PAGE_SIZE + 1));
    params.set("offset", String(page * PAGE_SIZE));
    return api.get(`/api/notices?${params}`);
  }, [tab, page, excludeId]);

  function changeTab(next) {
    setTab(next);
    // Page 4 of Posts is not page 4 of Organizations.
    setPage(0);
  }

  async function refresh() {
    setPage(0);
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

  // The highlight lives above the Posts tab — the board's front page. It ranks
  // across the whole board, so the winner can be an organization's post; it's
  // labelled "post of the day", not "a neighbour's post", so that's honest.
  // Only on the first page: it isn't a header for page 3.
  const showTop = tab === "posts" && page === 0 && top.data;
  const fetched = board.data || [];
  const hasNext = fetched.length > PAGE_SIZE;
  const listed = fetched.slice(0, PAGE_SIZE);

  return (
    <div className="org wide">
      <div className="page-head">
        <div>
          <span className="kicker">{meta.data.community_name}</span>
          <h1>Community board</h1>
        </div>
        {meta.data.can_post ? (
          <button className="btn" onClick={() => setComposing((v) => !v)}>
            {composing ? "Never mind" : "Write a post"}
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
              <button className="link-button" onClick={() => setTab("mine")}>
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

      <Tabs value={tab} onChange={changeTab} />

      {board.loading ? (
        <p className="muted">Loading…</p>
      ) : board.error ? (
        <div className="alert">{board.error}</div>
      ) : listed.length === 0 ? (
        <p className="muted board-empty">
          {page > 0
            ? "That's the end of the board."
            : showTop
              ? "Nothing else on the board right now."
              : emptyMessage(tab)}
        </p>
      ) : (
        // One per row rather than a grid: a post is something you read, and a
        // full-width card gives the words room instead of clipping them into a
        // tile. Same shape as the highlight above, minus its tint.
        <div className="board-list">
          {listed.map((notice) => (
            <NoticeCard key={notice.id} notice={notice} />
          ))}
        </div>
      )}

      {(hasNext || page > 0) && (
        <nav className="board-pager" aria-label="More posts">
          <button
            className="btn btn-secondary"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            ← Newer
          </button>
          <span className="muted">Page {page + 1}</span>
          <button
            className="btn btn-secondary"
            onClick={() => setPage((p) => p + 1)}
            disabled={!hasNext}
          >
            Older →
          </button>
        </nav>
      )}

      {tab !== "mine" && (
        <p className="muted allowance">
          You have {meta.data.live_count} of {meta.data.max_live} posts up.
        </p>
      )}
    </div>
  );
}

function emptyMessage(tab) {
  if (tab === "mine") return "You haven't written anything yet.";
  if (tab === "organizations")
    return "Nothing from local organizations right now. Verified libraries, schools and parks post here.";
  return "Nothing on the board right now. A quiet board is a fine thing.";
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

// Three tabs, and no per-type filter. Each post still wears its type as a tag,
// so you can tell a giveaway from a closure while scrolling — the board is
// something you read down, not something you query.
function Tabs({ value, onChange }) {
  return (
    <div className="pill-tabs board-tabs" role="tablist">
      {TABS.map(({ key, label }) => (
        <button
          key={key}
          role="tab"
          aria-selected={value === key}
          className={value === key ? "pill-tab on" : "pill-tab"}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function NoticeCard({ notice }) {
  return (
    <Link to={`/board/${notice.id}`} className={`notice-card nc-${notice.category}`}>
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
  // Coordinates of the address the author picked from the suggestions, kept
  // apart from `location` so ticking the pin box later can still use them.
  const [addressPoint, setAddressPoint] = useState(null);
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
      <h2>Write a post</h2>
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
        {/* Suggests addresses but doesn't insist on one: "the bench by the
            playground" is often more use to a neighbour, and free text still
            works. Picking a suggestion is what gives us coordinates. */}
        <AddressAutocomplete
          value={placeHint}
          onChange={(text) => {
            setPlaceHint(text);
            // Typing over a chosen address invalidates its coordinates.
            setAddressPoint(null);
          }}
          onSelect={({ address, lat, lng }) => {
            setPlaceHint(address);
            const point = { lat, lng };
            setAddressPoint(point);
            // Placing the pin at the address is the whole point of picking one,
            // so it lands immediately — and it's still draggable by clicking
            // the map, since an address is often only approximately the spot.
            setLocation(point);
            setPinned(true);
          }}
          center={here ? { lat: here[0], lng: here[1] } : undefined}
        />
        <p className="field-hint">
          Pick a suggestion to place the map pin automatically, or just describe
          it — a landmark often reads better than an address.
        </p>
      </div>

      <div className="field">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={pinned}
            onChange={(e) => {
              const on = e.target.checked;
              setPinned(on);
              // Ticking the box after choosing an address reuses that address
              // rather than making the author hunt for the spot again.
              if (on && !location && addressPoint) setLocation(addressPoint);
            }}
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
              {addressPoint && location
                ? "Placed at the address you picked — click the map to nudge it."
                : "Click the map to place it."}{" "}
              Informational only — it appears as a muted pin so nobody mistakes
              it for something to attend.
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
          {saving ? "Posting…" : "Post it"}
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
      <span className="kicker">Community board</span>
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
