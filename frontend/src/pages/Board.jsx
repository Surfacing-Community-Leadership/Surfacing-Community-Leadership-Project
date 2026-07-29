import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import CommunityPicker from "../components/CommunityPicker.jsx";
import NoticeForm from "../components/NoticeForm.jsx";
import StarButton from "../components/StarButton.jsx";
import { categoryShort, isLongForm, timeLeft } from "../lib/noticeCategories.js";

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

// A thin wrapper: the form itself is shared with the edit screen so the two can
// never drift apart.
function ComposeNotice({ meta, onPosted, onCancel }) {
  return (
    <NoticeForm
      meta={meta}
      submitLabel="Post it"
      savingLabel="Posting…"
      onCancel={onCancel}
      onSubmit={async (payload) => {
        await api.post("/api/notices", payload);
        await onPosted();
      }}
    />
  );
}


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
