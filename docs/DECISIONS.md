# Decision log — backend MVP build

Every judgment call made while building out the backend in one pass
(2026-07-08), for review and discussion. Items marked **⚠ deviation** differ
from the written spec; everything else fills a gap the spec left open.

## Authentication

1. **Custom auth routes on top of fastapi-users.** The stock fastapi-users
   login router expects OAuth2 *form* data with a `username` field; our API
   contract promises JSON `{ email, password }`. Rather than deviate from the
   contract, `/api/auth/register|login|logout` are small custom routes that
   use fastapi-users' machinery underneath (password hashing, user manager,
   JWT strategy, the `current_user` dependency).
2. **Logout is client-side.** Stateless JWTs can't be revoked server-side
   without a token blocklist. `POST /api/auth/logout` requires auth (so the
   contract's 401 works) and returns 204; the client discards its token.
   Revisit before production (short-lived tokens + refresh, or a blocklist).
3. **Register creates the profile too** — `display_name` from the register
   body, `avatar_key` set to `"default"`. Every user always has a profile.
4. **Password policy:** at least 8 characters and not equal to the email.
5. **`/api/auth/register` returns** `{ id, email, is_verified }`;
   `/api/users/me` adds `is_superuser`. Matches contract.

## Events & the map

6. **Private events 404 for outsiders** (instead of 403) so their existence
   is not revealed. The messages endpoints return 403 per the contract.
7. **Address privacy:** `address` is returned only to the host and
   participants with status `going`/`attended`. Everyone else gets the map
   point (which the host should place at a corner/landmark for private
   gatherings) — matches contract note.
8. **`participant_count`** counts `going` + `attended` only.
9. **Map query defaults:** radius 5 km (max 100 km), max 200 results sorted
   nearest-first, only `open`/`full` events, and **upcoming only** unless a
   `from` filter is passed. Cancelled/completed events never appear.
10. **The host has no participant row.** Permission checks treat the host
    specially instead. Keeps counts clean; revisit if hosts need RSVP states.
11. **Capacity:** enforced when someone sets status `going` — confirmed
    (`going`+`attended`) ≥ capacity → 409. The event's `status` column is
    *not* auto-flipped to `full` (host can set it manually via PATCH).
12. **RSVP against a cancelled/completed event → 409.**
13. **DELETE /api/events/{id} is a hard delete** (cascades participants and
    messages). The contract said "deletes or cancels"; cancelling is
    available separately via `PATCH { status: "cancelled" }`.

## Invitations

14. **Who may invite:** the host, or a participant whose status is
    invited/going/maybe/attended — and the invitee must be an *accepted
    connection* of the inviter (per contract) and not blocked either way.

## Connections & blocks

15. **⚠ deviation — connection rows stay directional.** The schema notes
    suggested storing the pair in canonical order; but requester/addressee
    direction is load-bearing (only the addressee may accept), so rows keep
    their true direction and duplicate checks look up both directions.
16. **Blocking severs any existing connection or pending request** between
    the two users, and blocks (either direction) prevent new connection
    requests and invites with 403.
17. **Self-targeting** (connect with/block yourself) → 422.

## API shape

18. **Error bodies are `{ "message": ... }`** via global exception handlers
    (FastAPI's default is `{ "detail": ... }`). 422 responses also include an
    `errors` array with field-level details — an extension of the contract.
19. **`location` is `{ lat, lng }`** in both requests and responses (the
    contract never fixed a format). PostGIS order (lng, lat) is handled
    internally in `app/core/geo.py`.
20. **`GET /api/interests` and `GET /api/communities` are public** — the
    contract lists no 401 for them.
21. **CORS** allows `http://localhost:5173` (the future Vite dev server).

## Data & environment

22. **16 starter interests seeded via a data migration**, so every
    environment gets the same taxonomy.
23. **No API creates communities** — that's an admin concern; for now insert
    via SQL, later via SQLAdmin (still to be wired, along with rate limiting).
24. **`cryptography` was installed from a prebuilt wheel** (`--only-binary`);
    the newest source-only release fails to build on this Intel-Python setup.

## Revisions — 2026-07-10 (post-review, user-directed)

- **Auth moved from bearer tokens to an httpOnly cookie** (`ours_auth`,
  SameSite=Lax, Secure off in dev via `COOKIE_SECURE`, must be on in prod).
  This supersedes items 1–2 above in part: login now returns **204 and sets
  the cookie** (no more `{ access_token }` body — a deliberate contract
  change), and logout now genuinely clears the cookie. The JWT inside is
  still valid until expiry if somehow captured; a token blocklist remains the
  production upgrade. SameSite=Lax is the MVP CSRF answer; a real CSRF token
  is the production-grade one.
- **Added `GET /api/profiles/me/interests`** so the UI can show current
  selections (contract gap found while building the frontend).
- **Added `GET /api/profiles?q=` people search** — matches display names
  case-insensitively (LIKE wildcards escaped), excludes yourself and anyone
  with a block in either direction, capped at 20 results, min 2 characters.
- `show_attending` deliberately left unused for now (user decision).

## Revisions — 2026-07-10, round two (user-directed gap closure)

- **Blocks now hide events entirely**: the map query excludes events hosted
  by anyone with a block in either direction (NULL hosts stay visible), and
  the single-event permission check does the same — so detail, RSVP,
  participants, and messages all follow.
- **Sessions are database-backed** (fastapi-users `DatabaseStrategy` +
  `access_tokens` table) instead of JWTs. Tokens are opaque random strings;
  **logout deletes the row and genuinely revokes the session**. Expired rows
  accumulate until cleaned — a periodic sweep is a future ops task.
- **CSRF double-submit**: login also sets a JS-readable `ours_csrf` cookie;
  middleware rejects any mutating `/api` request whose `X-CSRF-Token` header
  doesn't match it (403). Scoped to `/api` so SQLAdmin's forms are unaffected.
  Login/register are naturally exempt (no auth cookie yet).
- **SQLAdmin mounted at `/admin`**, login restricted to active superusers
  (promote via `scripts/make_admin.py`). Users/events can't be created from
  the admin (moderate, don't author); reports can't be deleted (audit trail);
  PostGIS columns are excluded from forms (no widget — set via SQL).
- **Event status is a state machine**: open ⇄ full, either → cancelled or
  completed, and those two are terminal (409 otherwise).
- **Pagination** (`limit`/`offset`) on event discovery, participants, and
  messages.
- **Avatar uploads**: `POST /api/profiles/me/avatar` (JPEG/PNG/WebP ≤ 2 MB)
  stored on local disk under `media/avatars/` and served at `/media/…` —
  production would use object storage (S3-style) instead.
- **A real pytest suite** (24 tests) against a disposable `ours_test`
  database created per run — see `backend/tests/`.

## Revisions — 2026-07-16 (dynamic communities from OpenStreetMap)

- **Communities are sourced live from OpenStreetMap**, not a fixed seed list.
  `GET /api/communities/nearby?lat&lng&radius` proxies the **Overpass API**
  for `place` nodes (neighbourhood/suburb/quarter/borough) around the user and
  returns them **nearest-first**. Proxied server-side for the same reasons as
  geocoding: an identifying User-Agent and a swappable provider.
- **Lazy materialization (find-or-create on select)** reconciles an external
  source with our relational FK model. `/nearby` returns *candidates* (name +
  center + `osm_ref`), which are **not** rows. Only when a user picks one does
  `POST /api/communities` create a row keyed by a new unique `osm_ref` column
  (migration `9a3f7c2b1e04`), minting the UUID that `profiles.community_id`
  references. The table becomes a lazily-grown cache of neighborhoods someone
  actually joined — we never mirror all of OSM. Idempotent per `osm_ref`
  (two users picking the same neighborhood share one row; a concurrent
  double-insert is caught via `IntegrityError` and reused).
- **The seeded Sunset Park carries its real `osm_ref`** (`node/3343148003`)
  so picking it from the live list reuses the seed row instead of duplicating.
- **`POST` trusts only the `osm_ref`, not the client's name/center.** The name
  and center come from OSM, so a caller can't invent a community. `osm_ref` is
  pattern-validated `(node|way|relation)/<digits>` — it is interpolated into an
  Overpass query, and the pattern blocks injection.
- **A 30-minute in-memory candidate cache** keyed by `osm_ref` removes the
  second Overpass call at save time. Overpass rate-limits aggressively (~1 req
  / 10–15s per IP), and a live call *at the moment a user commits* is the worst
  place for flakiness. `/nearby` caches what it hands out; `POST` reads the
  cache when warm and only falls back to a live lookup-by-id on a miss. The
  cache is per-process and lost on restart — fine for the MVP; the OSM fallback
  covers every miss. Total Overpass outage degrades to a clean 503, never a 500.
- **Onboarding's community `<select>` was replaced by `CommunityPicker`**,
  which uses the shared `useGeolocation` hook, lists neighborhoods nearest
  first, offers "Search a wider area" (3 → 8 → 20 km) and "Choose later", and
  materializes the pick (POST) before handing the UUID to the profile PATCH.

## Revisions — 2026-07-28 (the notice board)

- **Notices are their own table, not a fourth `Event.kind`.** The events table
  advertises "one table serves both", but the seams don't fit: `events.starts_at`
  and `events.location` are both NOT NULL and plenty of real notices have
  neither ("water main work on 5th all week"). Sharing the table would also
  inherit RSVPs, capacity, `status`, event-scoped messaging and the trust
  tallies — `isHelpKind` and the hosted-count ladder would each need an "unless
  it's a notice" carve-out. `notices` reuses the *patterns* instead (the
  `public`/`community` scoping idea, `blocked_counterparts`, the notifications
  table, the report path) without the baggage.
- **The board is scoped by `community_id`, not by radius, and never appears on
  the map.** A board is a *place*: everyone in a neighborhood reads the same
  one, rather than each person seeing a personalized slice. This fell out of the
  product decision to keep notices off the map, and it removed PostGIS from the
  feature entirely — no geography column, no GIST index, no interaction with the
  tile-import ledger. A free-text `place_hint` ("the bench by the playground")
  covers location, and reads better to a neighbor than a pin would. Adding a
  nullable location later is a one-column migration if that changes.
- **Three structural noise controls, chosen over moderation** because there is
  nobody on staff to moderate (`app/core/notices.py`): every notice carries an
  `expires_at` so the board sweeps itself; `MAX_LIVE_NOTICES = 3` per author,
  because a corkboard has finite space and the scarcity is the feature; and the
  categories are a closed CHECK-constrained list rather than free text.
- **No comment threads anywhere on the board.** Open comments are the specific
  mechanism that turns neighborhood feeds into argument venues (the Nextdoor
  research is unambiguous), so a reply is a single private line to the poster,
  delivered as a notification. `UNIQUE (notice_id, author_id)` means one reply
  per neighbor — sending again edits it and deliberately does *not* re-notify,
  so editing can't become an unlimited pinger. `GET /replies` is author-only,
  and `reply_count` is nulled out for everyone else so the board doesn't leak
  who is interested in what.
- **No engagement metrics.** No likes, votes, ranking or recency emphasis. The
  trust record earned the right to show counts because they're verifiable; a
  board hasn't.
- **No crime-and-safety category, on purpose.** Studies of Nextdoor find its
  users perceive more crime regardless of whether crime actually rose, which is
  the opposite of getting neighbors comfortable with each other. Reports and
  blocks handle real problems between people. `test_there_is_no_crime_or_safety_category`
  asserts the absence so nobody re-adds one by reflex.
- **Posting requires a confirmed email**, reusing `email_confirmed_at` as the
  board's only spam gate: it costs an attacker a working inbox per account.
- **Organizations get two extra categories** (`announcement`, `service_change`)
  because those carry an institution's authority; they keep the neighborly ones
  too, since a library giving away chairs is still a giveaway.
- **`notifications` gained a nullable `notice_id`** (it only referenced events
  before). CASCADE rather than the `event_id` column's SET NULL: an orphaned
  event notification still reads as "an event", but "someone replied to a
  notice" with no notice to open is a dead end.
- **`Create` left the nav for a floating button.** Creating is an action, not a
  destination, and moving it freed the fifth tab slot for the board instead of
  cramming six tabs into a phone-width bar. The button lifts above the map's
  list sheet on mobile (`.fab-map`) and sits below the rail's z-index so the
  nav always wins a fight over the same pixels.

## Revisions — 2026-07-29 (notice board v2, user-directed)

A spec round that **reversed four of the previous day's decisions**. Recording
what changed and why, since the reasoning in the section above is now partly
superseded.

- **Nine post types, not six.** `news`, `shoutout` and `blog` join the four
  neighbourly types; `announcement` and `service_change` stay organization-only.
  The spec's "strictly announcements, news, shoutouts, blogs" reading was *not*
  taken, on the user's instruction — the giveaway and lost-and-found types are
  the ones that end at a doorstep, and the spec's own map-pin examples ("road
  closures, lost pets") depend on them.
- **Body limit raised to 8000 chars** so a `blog` is actually writable. Long-form
  types get a two-line card preview instead of three, so one wordy post can't
  dominate the grid.
- **Expiry ceiling raised to 3 months, default still 14 days.** The author picks
  a window (a week / two weeks / a month / three months); the server clamps on
  create *and* on every edit. The purge the spec asked for is
  `scripts/purge_notices.py` with a 30-day grace after expiry — a script, not a
  background task, because the deployment has no scheduler and a sweep inside a
  web request runs at an unpredictable moment on a user's latency budget.
- **Allowance is now per account type**: 5 live notices for a person, 15 for an
  organization. Announcing things *is* the point of a verified account.
- **Notices can carry an optional location** (`Geography(POINT)`, partial GiST
  index `WHERE location IS NOT NULL`, since most notices have none). This
  reverses "never on the map". Served by a **separate** `/api/notices/map`
  endpoint rather than folded into the events query: a notice has no start time
  to order by, and keeping them apart means the map's "spots nearby" list can't
  fill with things nobody can attend. Pins are a muted rounded *square* with an
  ⓘ — shape, not just colour, so it still reads as "not an event" to someone who
  can't distinguish the two hues.
- **Stars, reversing "no engagement metrics".** `notice_stars` with
  `UNIQUE (notice_id, user_id)` — the uniqueness *is* the one-per-account rule.
  Three deliberate limits kept the concession narrow: the count is an anonymous
  aggregate with **no endpoint that lists who starred** (not even for the
  author — `test_there_is_no_endpoint_that_reveals_who_starred` asserts it),
  starring **sends no notification** (a ping on a star is what turns a board into
  a slot machine), and there is no leaderboard — exactly one post is highlighted.
- **"Post of the day" ranks on a trailing 24-hour window**, not the all-time
  count, so it rotates rather than accumulating. Ties break toward the newer
  post. Returns null when nothing was starred recently and the board simply shows
  no highlight. The all-time count is what's displayed on a card; only the
  *ranking* uses the window.
- **`allow_direct_inquiries`** (default true) gates the private reply built the
  day before. Toggling it off after the fact stops new replies but leaves the
  ones already received readable — the author asked for quiet, not amnesia.
- **An "Official" filter, not a pinned band.** Verified organizations get a
  filter and a black `Official` tag rather than a permanent section at the top of
  the board, because post-of-the-day already owns that slot and two competing
  bands would leave no room for the board itself.
- **Deliberately NOT built:** the Knowledge & Skills Resource Pool. Its spec
  listed "3 Pillar Categories" and named only one, and the user chose to defer it.

## Revisions — 2026-07-29, round two (Community board)

- **Renamed "Notice board" → "Community board"** in the interface, and each entry
  is a "post" rather than a "notice" in all visible copy. **The schema, routes and
  models were deliberately NOT renamed** — the table is still `notices`, the API
  is still `/api/notices`, the model is still `Notice`. Renaming a shipped schema
  and its migration chain to chase a label buys nothing and risks a lot; the
  router docstring says so explicitly so the mismatch reads as a decision rather
  than an oversight.
- **Nine per-type filter tabs collapsed to three reading tabs**: Posts,
  Organizations, My posts. Post *types* still exist and still show as a tag on
  every card — they just aren't a navigation axis any more. The board is
  something you read down, not something you query.
- **`official=true` became `source=all|posts|organizations`**, and the two tabs
  are a **complete partition** of the board rather than two independent filters.
  `posts` is "everything not official", *not* "people only": an unverified
  organization (a mutual-aid group on a `.org`) would otherwise appear under
  neither tab and become unreachable. `test_the_two_tabs_partition_the_board`
  asserts `posts | orgs == everything` and `posts & orgs == set()`.
  `_IS_OFFICIAL` uses `coalesce()` because the author joins are outer — a NULL
  would otherwise drop a row from *both* sides of the split.
- **"Yours" ignores the split**, so a verified organization still finds its own
  work under My posts.
- **Post of the day appears above the Posts tab only**, but still ranks across
  the whole board — so an organization's post can win it. It's labelled "post of
  the day", not "a neighbour's post", so nothing misrepresents itself; scoping the
  ranking per-tab would have meant a great official post could never be
  highlighted anywhere.
- **The grid became a single-column list.** Each card is now full-width with the
  same shape as the highlight above it, minus that one's tint — a post is
  something you read, and a tile clips the words.

## Revisions — 2026-07-29, round three (paging, six types, address pins)

- **Six person post types, fixed by name**: Giveaway, Lost & Found, Question,
  Local news, Shoutout, Writing. `recommendation` was renamed to `question`, and
  `offer_help` was retired. Organizations keep Announcement and Service change on
  top of those six — a closure notice from a library is genuinely a different
  thing from local news, and the Organizations tab filters by author rather than
  by type, so it works either way.
- **Rows are reclassified, never deleted.** Migration `d1a7c46e9b25` moves
  `recommendation` → `question` and `offer_help` → `blog`. Order matters and I got
  it wrong first: the CHECK has to come off *before* the UPDATE, because the old
  constraint doesn't know `question` yet and rejects the first row. `offer_help`
  has no exact survivor, so `blog` is used as the general-purpose type rather than
  as a claim about the content, and the downgrade doesn't try to restore it
  (nothing recorded which rows they were).
- **The board pages at six**, with Newer/Older rather than infinite scroll.
  Reaching the end of a page is a natural place to stop reading, which is the
  whole point of a board you visit instead of a feed.
- **`exclude_id` was added to the list endpoint** so paging stays exact. The
  post of the day is rendered above the list; filtering it out client-side left
  whichever page contained it one post short. The client also fetches
  `PAGE_SIZE + 1` rows purely to answer "is there a next page?" without a second
  count query — the extra row is never rendered.
- **The post of the day only appears on page 1** of the Posts tab. It isn't a
  header for page 3.
- **Whereabouts is now an address autocomplete that drives the map pin.**
  Picking a suggestion fills the text, ticks "also drop a pin", and places the
  pin at that coordinate — still draggable by clicking the map, since a street
  address is usually only approximately the spot. Free text still works
  unchanged: "the bench by the playground" is often more use to a neighbour than
  an address, so the geocoder suggests rather than insists. Typing over a chosen
  address discards its coordinates, and ticking the pin box later reuses them if
  they're still valid.

## Revisions — 2026-07-29, round four (editing your own post)

- **Authors can now edit everything they wrote**, including the post type. This
  *reverses* the earlier "the type is fixed after posting" rule from round two.
  That was my own conservative call, not a requirement — the stated reason (people
  may have already read it) doesn't justify making someone delete and repost to
  fix a mis-picked type, which is an ordinary mistake.
- **The type is re-validated on edit.** Without it, relabelling would be a way
  around the organization gate entirely: a person could post a `giveaway` and
  then PATCH it to `announcement`. `test_editing_cannot_promote_a_post_to_an_organization_type`
  covers it.
- **`NoticeUpdate` needed its own category validator.** `NoticeCreate` had one;
  the update schema didn't, so a retired type like `offer_help` slipped past
  validation and hit the router's account-type check, which answered "that post
  type is for verified organization accounts" — true of neither and actively
  misleading. Found by a test that asserted 422 and got 403.
- **Editing never touches the expiry unless asked.** The form's expiry selector
  defaults to "Leave as it is — N days left" and the payload omits `expires_at`
  entirely in that case, so fixing a typo can't silently restart a post's clock.
- **Stars and replies survive an edit** untouched, asserted by a test — an edit
  changes the words, not the post's history.

## Revisions — 2026-08-05 (the AI flyer)

- **The feature needed a public event page, which did not exist.** `/events/:id`
  is behind `ProtectedRoute` and `GET /api/events/{id}` requires a user, so a QR
  code on a lamppost would have bounced a stranger to the login screen — which
  defeats the point of a flyer. Added `GET /api/public/events/{id}` and an
  unauthenticated `/e/:id` route.
- **That endpoint is the only unauthenticated read of app data in the codebase**,
  so it is written to be boring: public-visibility events only, a hand-listed
  response model, and no branch that could widen either. A test asserts the field
  set *exactly*, so adding a field later fails loudly rather than quietly leaking.
  It lives in its own router, not under `/api/events`, because a public route
  sitting beside auth-dependent ones is how you accidentally inherit — or fail to
  inherit — a dependency.
- **A help request's address is never public**, regardless of its visibility
  setting: for a help request the address is somebody's home. A gathering's or a
  volunteering shift's address *is* served publicly, since a host who chose public
  visibility and typed a venue wants people to find it. `VENUE_KINDS` draws that
  line in one place.
- **Gemini never receives the address at all.** `flyer_copy()` has no parameter
  for it, so the caller cannot leak one even by mistake. It gets title,
  description, host display name, when, and neighbourhood.
- **Private events cannot have a flyer** (409). A flyer's QR points at a publicly
  readable page, so allowing one would quietly undo the visibility the host chose.
  The button is hidden in the UI too, but the server is what enforces it.
- **The feature cannot fail.** No key, a timeout, a quota error, a malformed
  reply, or an SDK change all land on the same behaviour: templated "mad-libs"
  copy from the event's own fields, logged for us, HTTP 200 for the user. The
  `except` is deliberately broad because every one of those cases has the same
  correct response.
- **Templated copy does not spend the daily allowance.** Only a real model call
  is recorded, otherwise an outage on Google's side would burn the quota of every
  user who tried during it.
- **The cap is a table, not a counter.** `flyer_generations` survives restarts,
  is correct across worker processes (an in-process dict would give each worker
  its own count, making the real limit the cap times the worker count), and
  doubles as an audit trail. `event_id` is SET NULL rather than CASCADE so
  deleting an event cannot refund the quota it spent.
- **`google-genai`, not `google-generativeai`.** The latter is Google's legacy
  SDK, superseded by the unified one; same capability here, and it avoids adding
  a deprecated dependency to new code.

## Security fix — 2026-08-05 (path traversal in the SPA fallback)

**Severity: high. Found during pre-deploy checks for the flyer feature, before
the affected code had ever been deployed with a real secret in place.**

- **What was wrong.** The production single-origin server serves the built
  frontend through a catch-all route, which joined the request path directly onto
  the dist directory: `candidate = FRONTEND_DIST / full_path`. Starlette decodes
  percent-escapes but does **not** normalise `..` segments before handing the path
  to the route, so `GET /..%2f..%2fbackend%2f.env` arrived as the literal string
  `../../backend/.env` and the file was returned with HTTP 200.
- **What it exposed.** `SECRET_KEY`, `DATABASE_URL`, `TICKETMASTER_API_KEY`,
  `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` — readable by anyone, no
  authentication, in a single request. `SECRET_KEY` signs session cookies and the
  email-confirmation and OAuth-state tokens, so its disclosure is enough to forge
  a session for any account.
- **How it was found.** Not by reading the code. The flyer needs self-hosted fonts
  served from that same fallback, so the pre-merge check simulated the production
  single-origin server and probed it — including with `--path-as-is` so curl
  wouldn't normalise the path on the client. The raw `/../` form is normalised
  away by the client and looks safe; only the encoded form got through, which is
  why an eyeball review had missed it.
- **The fix.** `_safe_static()` resolves both the dist root and the candidate and
  requires the root to be a parent of the result. Containment after resolution,
  not string inspection — stripping `..` or rejecting on substring misses
  encodings, absolute paths and symlinks, all three of which are now tested.
- **Regression cover.** `tests/test_spa_static.py`, 16 tests. Verified to actually
  catch the bug: reinstating the old two-line resolution fails 6 of them,
  including one that goes through the real HTTP stack.
- **Note for whoever reads this later:** the vulnerable code predates the flyer
  feature. What the flyer changed is that it made this fallback load-bearing for
  fonts, which is why it got probed at all.

## Revisions — 2026-08-05, round two (the demo seed was silently stale in production)

- **The bug.** `scripts/seed_prod.py` decided whether to seed by asking only "does
  the Sunset Park community exist". Once a database had been seeded a single time
  it never seeded again — so every feature that shipped with demo data had none of
  it in production, and the deploy log said "already present — skipping" the whole
  time. Verified against the real code path, not inferred.
- **The fix: a version marker.** `seed_state` (one row) records which
  `SEED_VERSION` built the current demo data. `seed_prod` re-seeds when the demo
  is absent, unversioned, or older than the build; skips when it matches; and
  **refuses to overwrite a newer database with older data**, so rolling back to an
  earlier image doesn't destroy demo content.
- **The migration deliberately does not backfill a version.** An existing
  deployment therefore reads as "unversioned", which is exactly right — it is
  missing everything added to the seed since it was first built.
- **The version is stamped last**, after every insert, so a run that dies partway
  leaves no version recorded and the next deploy retries rather than believing a
  half-built demo is current.
- **Re-seeding is destructive and says so.** It TRUNCATEs users/events/communities,
  so it deletes any account created on the deployed app. That is correct for a
  demo and wrong for a real deployment, which is what `SEED_DEMO=false` is for —
  the log now prints how many accounts it is about to delete.
- **Also fixed: trust records were all zeros in the demo.** Every seeded event was
  in the future, and nothing seeded `attended` participations or `help_thanks` —
  so the trust feature, which counts hosted/attended/helped, showed three zeros
  and "Neighbor" on every profile. It looked broken rather than new. `PAST_EVENTS`
  adds ten events that already happened, 28 confirmed attendances and 7 written
  thanks (each clearing `MIN_REFLECTION_WORDS`), giving profiles like
  "hosted=2 attended=1 helped=1".

## Deferred (known gaps to discuss)

- Rate limiting is in the stack but still not wired.
- Expired access-token rows need a periodic cleanup task.
- Avatar storage is local disk — swap for object storage before deploying.
- `scripts/purge_notices.py` exists but nothing runs it — it needs a scheduler,
  same as the access-token cleanup above. Until then expired notices are hidden
  by the query filter and simply accumulate as rows.
- The Knowledge & Skills Resource Pool is specified but unbuilt: two of its three
  pillar categories were never named, and its scope (neighbourhood vs city-wide),
  edit model (author-owned vs wiki) and the meaning of its "verified" badge are
  all still open.
