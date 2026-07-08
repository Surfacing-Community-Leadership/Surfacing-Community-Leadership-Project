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

## Deferred (known gaps to discuss)

- Tests are a curl smoke script, not a pytest suite.
- SQLAdmin (admin UI) and rate limiting are in the stack but not yet wired.
- Blocked users' events still appear on each other's maps (only connect,
  invite and message paths enforce blocks so far).
- `PATCH /api/events/{id}` accepts any status transition; no state machine.
- No pagination on list endpoints (map query is capped at 200).
