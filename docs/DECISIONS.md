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

## Deferred (known gaps to discuss)

- Rate limiting is in the stack but still not wired.
- Expired access-token rows need a periodic cleanup task.
- Avatar storage is local disk — swap for object storage before deploying.
