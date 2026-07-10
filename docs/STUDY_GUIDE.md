# Ours — Engineering Study Guide

A guided tour of this repository for leveling up your full-stack skills.
Every claim below points at real files — read this with the code open.

---

## 1. Executive Summary & System Design

### What this application is

**Ours** is a neighborhood community platform whose product goal is unusual:
*get people off the screen and into a room together*. Residents discover
nearby **gatherings** and **help requests** on a map, RSVP, form mutual
**connections**, and invite each other to events. Messaging deliberately
exists *only inside an event* — there is no open chat, because the app is a
coordination tool, not a place to live online.

That product philosophy shows up in the code as concrete constraints:

- `event_messages` rows require an `event_id` (see
  [backend/app/models/message.py](../backend/app/models/message.py)) — the
  schema itself makes free-floating chat impossible.
- Safety features are first-class, not bolted on: blocks erase people from
  each other's world (search, connections, invites, *and the map itself*),
  and a private event returns **404, not 403**, so outsiders can't even
  learn it exists.

### High-level architecture

This is a **layered monolith with a separate SPA client** — the most common
shape for a small-team product, and worth studying because you'll meet it
everywhere:

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│  React SPA (Vite)       │        │  FastAPI monolith (Uvicorn)  │
│  frontend/src           │ /api   │  backend/app                 │
│  - pages (views)        │──────▶ │  - middleware (CORS, CSRF)   │
│  - AuthContext (state)  │ proxy  │  - routers (HTTP endpoints)  │
│  - api/client.js (I/O)  │◀────── │  - deps (auth, permissions)  │
└─────────────────────────┘  JSON  │  - models (SQLAlchemy ORM)   │
                                   └───────────────┬──────────────┘
             ┌──────────────────┐                  │ asyncpg
             │  SQLAdmin /admin │──────────────────┤
             └──────────────────┘                  ▼
                                   ┌──────────────────────────────┐
                                   │  PostgreSQL 18 + PostGIS     │
                                   │  (spatial queries, 13 tables)│
                                   └──────────────────────────────┘
```

Key properties:

- **One backend process** serves the JSON API (`/api/*`), uploaded media
  (`/media/*`), and an admin panel (`/admin`). No microservices — at this
  scale they would add network boundaries without adding value.
- **The frontend is fully decoupled**: it only speaks HTTP+JSON through
  [frontend/src/api/client.js](../frontend/src/api/client.js). You could
  replace React with anything and the backend wouldn't notice.
- **The database is the source of truth for integrity**: uniqueness, CHECK
  constraints, foreign-key cascade rules, and even UUID generation live in
  Postgres, not in Python (more in §5).

### Data flow: anatomy of one request

Take `PUT /api/events/{id}/rsvp` (a user taps "Going"):

1. **Browser** — a page calls `api.put(...)` in
   [client.js](../frontend/src/api/client.js). The wrapper JSON-encodes the
   body, and because the method is mutating, reads the `ours_csrf` cookie
   and echoes it as an `X-CSRF-Token` header. The browser itself attaches
   the `ours_auth` httpOnly session cookie.
2. **Vite dev proxy** ([frontend/vite.config.js](../frontend/vite.config.js))
   forwards `/api/*` to `localhost:8000`, making everything same-origin in
   development (no CORS preflights).
3. **Middleware** in [backend/app/main.py](../backend/app/main.py): CORS,
   then the CSRF check — mutating `/api` request + auth cookie present →
   header must match the csrf cookie or the request dies with 403 right here.
4. **Routing + Dependency Injection** — FastAPI matches
   `set_rsvp()` in [routers/participants.py](../backend/app/routers/participants.py).
   Before the function body runs, FastAPI resolves its declared dependencies:
   - `DB` → `get_db()` in [core/database.py](../backend/app/core/database.py)
     opens an `AsyncSession` (borrowing a pooled connection),
   - `CurrentUser` → fastapi-users reads the cookie, looks the token up in
     the `access_tokens` table, loads the `User` row. Invalid/expired → 401
     before your code runs.
5. **Handler logic** — `set_rsvp` loads the event (404 if missing), checks
   visibility via `require_event_view()` in
   [routers/deps.py](../backend/app/routers/deps.py), enforces capacity
   (409 if full), then upserts the `EventParticipant` row and commits.
6. **Response** — the returned Pydantic model (`RsvpRead` from
   [schemas/participant.py](../backend/app/schemas/participant.py)) is
   serialized to JSON. If anything raised `HTTPException`, the global
   handler in `main.py` reshapes it to the API contract's `{ "message": ... }`.
7. **Back in the browser** — `client.js` parses the JSON (or throws a typed
   `ApiError`), and the page re-fetches via its `reload()` from the
   [useApi](../frontend/src/hooks/useApi.js) hook.

Internalize step 4 — **dependency resolution before the handler** — and half
of FastAPI makes sense.

---

## 2. Tech Stack Deep Dive

### Backend

| Technology | Role | Why it was chosen / how it interacts |
|---|---|---|
| **FastAPI** | Web framework | Async-native, and built on type hints: the same annotation gives you validation, serialization, DI, and the auto-generated docs at `/docs`. Interacts with Pydantic (schemas) and Starlette (middleware, responses). |
| **Uvicorn** | ASGI server | FastAPI describes endpoints; it cannot listen on a port. Uvicorn accepts sockets and speaks ASGI to the app. `--reload` gives dev hot-restart. |
| **Pydantic / pydantic-settings** | Validation + config | Every request/response shape in `app/schemas/` is a Pydantic model — invalid input is rejected before your code runs. `Settings` ([core/config.py](../backend/app/core/config.py)) reads `.env` so secrets never live in code. |
| **SQLAlchemy 2.0 (async)** | ORM | The 2.0 `Mapped[...]`/`mapped_column` style makes the type annotation control nullability. Async mode means DB waits yield the event loop instead of blocking a thread. |
| **asyncpg** | Postgres driver | The fastest async Python driver; SQLAlchemy speaks *to* asyncpg, asyncpg speaks *to* Postgres (`postgresql+asyncpg://` in the URL selects it). |
| **PostgreSQL + PostGIS** | Database | PostGIS adds a `geography` type and spatial functions/indexes. "Events near me" is `ST_DWithin` over a GiST index — a solved problem instead of a hard one. |
| **GeoAlchemy2 + shapely** | Geo glue | GeoAlchemy2 maps the `Geography` column type into SQLAlchemy; shapely converts Postgres's binary WKB values back to `(lat, lng)` (see [core/geo.py](../backend/app/core/geo.py)). |
| **Alembic** | Migrations | Version control for schema. Autogenerate diffs `Base.metadata` (what code wants) against the live DB (what exists) — every change is a reviewed script in `alembic/versions/`. |
| **fastapi-users** | Auth machinery | Provides password hashing, the user manager, token strategies, and the `current_user` dependency. We use its engine but wrote thin custom routes ([routers/auth.py](../backend/app/routers/auth.py)) to match our JSON contract. |
| **SQLAdmin** | Admin panel | CRUD UI over the same SQLAlchemy models at `/admin`, gated to superusers ([core/admin.py](../backend/app/core/admin.py)). Zero custom admin frontend needed. |
| **pytest + pytest-asyncio + httpx** | Tests | httpx's `ASGITransport` calls the app **in-process** — full-stack tests (real Postgres, real middleware) without a running server. |

### Frontend

| Technology | Role | Why |
|---|---|---|
| **React 18 (JavaScript)** | UI | Component model fits the app's page structure; no TypeScript to keep the learning surface small. |
| **Vite** | Build tool + dev server | Instant startup, hot module replacement, and the dev proxy that makes cookies/CSRF same-origin. |
| **react-router v6** | Client-side routing | URL ↔ page mapping in [App.jsx](../frontend/src/App.jsx); nested routes let all authenticated pages share one `Layout`. |
| **Leaflet + react-leaflet + OpenStreetMap** | Map | Free tiles, no API key, tiny footprint. `divIcon` markers sidestep Leaflet's notorious broken-icon-paths-under-bundlers problem ([components/MapView.jsx](../frontend/src/components/MapView.jsx)). |
| **Native Fetch + plain CSS** | I/O + styling | Deliberate minimalism: one fetch wrapper instead of axios; one stylesheet ([styles.css](../frontend/src/styles.css)) instead of Tailwind. Fewer layers = clearer learning. |

### The interaction that ties it together

The stack is **async end-to-end on the read/write path**: browser fetch →
ASGI → `async def` handler → `await session.execute()` → asyncpg → Postgres.
One Python process can hold many requests "in flight" because every wait
point yields the event loop. This is why the stack insists on `asyncpg` and
SQLAlchemy's async mode rather than their synchronous cousins.

---

## 3. File Architecture & Domain Mapping

```
├── backend/
│   ├── app/
│   │   ├── main.py             # App assembly: middleware, routers, error shape,
│   │   │                       #   /media static mount, admin mount, /health
│   │   ├── core/               # Cross-cutting plumbing (no domain logic)
│   │   │   ├── config.py       #   Settings from .env (pydantic-settings)
│   │   │   ├── database.py     #   Engine, AsyncSessionLocal, Base, get_db
│   │   │   ├── auth.py         #   fastapi-users wiring: UserManager, cookie
│   │   │   │                   #   transport, DatabaseStrategy, current_active_user
│   │   │   ├── admin.py        #   SQLAdmin views + superuser login gate
│   │   │   └── geo.py          #   lat/lng ↔ PostGIS conversions
│   │   ├── models/             # DATABASE SHAPE — one class per table
│   │   │   ├── user.py, profile.py, community.py, event.py,
│   │   │   ├── participant.py, connection.py, block.py, message.py,
│   │   │   ├── report.py, interest.py (+ 2 association tables),
│   │   │   └── access_token.py # login sessions (revocable)
│   │   ├── schemas/            # API SHAPE — Pydantic request/response models
│   │   │   └── (mirrors the domains: auth, profile, event, ...)
│   │   ├── routers/            # HTTP LAYER + business logic
│   │   │   ├── deps.py         #   shared DI aliases + permission helpers
│   │   │   └── auth, users, profiles, communities, interests, events,
│   │   │       participants, connections, blocks, messages, reports
│   │   └── ...
│   ├── alembic/                # Migration chain (5 revisions incl. seed data)
│   ├── tests/                  # pytest suite (conftest + 24 tests)
│   └── scripts/                # smoke_test.sh, make_admin.py
├── frontend/
│   └── src/
│       ├── api/client.js       # THE ONLY network code (fetch, CSRF, errors)
│       ├── auth/AuthContext.jsx# global "who am I" state
│       ├── hooks/useApi.js     # loading/error/data pattern for every page
│       ├── components/         # Layout, ProtectedRoute, MapView, dialogs, ...
│       └── pages/              # one file per screen
└── docs/                       # DECISIONS.md, FRONTEND_DECISIONS.md, this guide
```

### Separation of concerns — the "three shapes" rule

The most important structural idea: **the same domain object exists in three
deliberately different forms**, and each answers to a different master:

1. **Model** ([models/event.py](../backend/app/models/event.py)) — how an
   Event lives in Postgres. Has `location` as binary geography, CHECK
   constraints, cascade rules.
2. **Schemas** ([schemas/event.py](../backend/app/schemas/event.py)) — how an
   Event crosses the API boundary. `EventCreate` (what clients may send),
   `EventSummary` (map pins), `EventDetail` (full view, `address` maybe
   nulled). The DB row always has the address; *the schema decides who sees it*.
3. **Router** ([routers/events.py](../backend/app/routers/events.py)) —
   translates between the two and enforces the rules.

Never let these collapse into one class. The gap between them is where
security lives (e.g. `hashed_password` exists on the model and on **no**
response schema — leaking it becomes structurally impossible).

### Where's the business logic?

An honest answer: **in the routers, plus shared helpers in
[routers/deps.py](../backend/app/routers/deps.py)**. There is a deliberate
MVP decision here — no separate `services/` layer yet. The rules that
multiple routers need (visibility, blocks, participation lookups, the status
state machine) were promoted into `deps.py`; rules used once stay in their
handler. When handlers grow past ~50 lines or logic needs reuse across
domains, extracting a service layer is the natural next refactor. Watch for
that pressure as the app grows — feeling *when* a layer earns its existence
is a senior-engineer skill.

---

## 4. Core Workflow Walkthrough: Login (and what a session really is)

Authentication touches every layer and includes this repo's most interesting
security engineering. Trace it with the files open.

### Step 1 — the form: [pages/Login.jsx](../frontend/src/pages/Login.jsx)

Classic controlled-component React: `email`/`password` in `useState`,
`submitting` disables the button mid-flight, errors render in an alert div.
On submit it calls `login()` from the auth context.

### Step 2 — the context: [auth/AuthContext.jsx](../frontend/src/auth/AuthContext.jsx)

```js
async function login(email, password) {
  await api.post("/api/auth/login", { email, password }); // sets cookies
  await loadUser();                                       // GET /api/users/me
}
```

Note what's *absent*: no token handling. The response body is empty (204).
The session credential travels in an **httpOnly cookie** JavaScript can never
read — which is the point: if an attacker ever injects script into the page
(XSS), there is no token in `localStorage` to steal.

### Step 3 — the wire: [api/client.js](../frontend/src/api/client.js)

One `request()` function all calls funnel through. Three jobs:
JSON encoding; CSRF header injection on mutating methods (reads the
JS-visible `ours_csrf` cookie); and error normalization — non-2xx becomes a
typed `ApiError` carrying the backend's `message`. Any 401 anywhere triggers
the `onUnauthorized` callback the context registered, clearing user state →
`ProtectedRoute` redirects to `/login`. **One funnel, one policy.**

### Step 4 — the endpoint: `login()` in [routers/auth.py](../backend/app/routers/auth.py)

```python
user = await user_manager.authenticate(credentials)   # verify password hash
token = await strategy.write_token(user)              # INSERT access_tokens row
response = await cookie_transport.get_login_response(token)  # httpOnly cookie
response.set_cookie(CSRF_COOKIE_NAME, secrets.token_hex(16), httponly=False, ...)
```

Two cookies, opposite visibility, and that asymmetry **is** the CSRF defense
(double-submit pattern): a hostile site can make your browser *send* our
cookies, but only same-origin JavaScript can *read* `ours_csrf` to echo it
in the `X-CSRF-Token` header. The middleware in
[main.py](../backend/app/main.py) (`csrf_protect`) rejects mismatches with 403.

### Step 5 — what a session actually is: [core/auth.py](../backend/app/core/auth.py)

The token is **not a JWT**. It's an opaque random string that is the primary
key of a row in `access_tokens`
([models/access_token.py](../backend/app/models/access_token.py)):

- `DatabaseStrategy.write_token` inserts the row at login.
- Every authenticated request looks the cookie's value up in that table
  (and checks `created_at` against the 24h lifetime).
- **Logout deletes the row** (`strategy.destroy_token` in the logout route)
  — the session is dead server-side, not merely forgotten by the browser.

We migrated here *from* JWTs deliberately: stateless JWTs can't be revoked
before expiry. The trade is one DB lookup per request for real revocation —
the right trade for this app. There's a test that proves it:
`test_logout_revokes_session_server_side` in
[tests/test_auth.py](../backend/tests/test_auth.py) "steals" the cookie
before logout and asserts it's dead after.

### Step 6 — guarding every other endpoint

Handlers declare `user: CurrentUser` (alias in
[routers/deps.py](../backend/app/routers/deps.py)). The dependency chain —
`current_active_user` → cookie transport → `DatabaseStrategy.read_token` →
`get_access_token_db` → `get_db` — resolves before the handler body runs.
FastAPI **caches dependencies per request**, so the handler and the auth
lookup share one DB session.

### Bonus flow — the map query (read it after login)

`discover_events()` in [routers/events.py](../backend/app/routers/events.py)
is the app's signature query. Study how one SQL statement composes:
`ST_DWithin` (radius, GiST-index-accelerated) + `ST_Distance` (sorting) +
`_visibility_clause` (public / same-community / private-if-invited) +
a block-exclusion subquery (`blocked_counterparts` from `deps.py`, with a
careful `host_id IS NULL OR host_id NOT IN (...)` — because `NOT IN` against
NULL would silently hide orphaned events) + time and pagination filters.
Authorization expressed *inside the query* instead of filtering in Python:
the database only ever returns what this user may see.

---

## 5. Engineering Best Practices & Patterns

### Design patterns actually present (name → where → why)

- **Dependency Injection** — everywhere via `Depends`. `get_db()` in
  [core/database.py](../backend/app/core/database.py) is the canonical
  example: a *generator dependency* whose `yield` splits setup (open
  session) from teardown (close it, even on exceptions). Tests exploit DI
  by swapping the database URL before the app imports
  ([tests/conftest.py](../backend/tests/conftest.py)).
- **Strategy pattern** — fastapi-users' auth is literally
  transport-strategy composition: `CookieTransport` (how credentials travel)
  × `DatabaseStrategy` (how tokens are validated) plug into one
  `AuthenticationBackend`. We swapped Bearer→Cookie and JWT→Database without
  touching any endpoint code — that's the pattern paying rent.
- **Repository/adapter** — `SQLAlchemyUserDatabase` and
  `SQLAlchemyAccessTokenDatabase` wrap table access behind an interface
  fastapi-users defines; the library never imports our models directly.
- **Factory** — `async_sessionmaker` manufactures sessions;
  `make_user` in conftest manufactures authenticated test clients.
- **Module-level singletons** — `engine`, `settings`, the FastAPI `app`:
  created once at import, shared everywhere. Pythonic singleton-by-module.
- **State machine** — `ALLOWED_STATUS_TRANSITIONS` dict in
  [routers/deps.py](../backend/app/routers/deps.py): data, not code. Adding
  a state means editing a dict, and illegal transitions are 409s.
- **Middleware pipeline** — CORS → CSRF → routing; cross-cutting concerns
  stay out of handlers.
- **Facade** — [api/client.js](../frontend/src/api/client.js) is a facade
  over fetch; [hooks/useApi.js](../frontend/src/hooks/useApi.js) is a facade
  over the loading/error/data state dance every page needs.

### State management (frontend)

Deliberately boring, in a good way:

- **Global state = auth only** (`AuthContext`). Everything else is *server
  state fetched per page* via `useApi`, refreshed after mutations with
  `reload()`. No Redux, no cache library — at this scale, re-fetching is
  simpler than cache invalidation, and correct beats clever.
- The pattern to copy: every page renders exactly one of
  `loading → error → empty → data`. Grep `useApi(` and see the same
  skeleton in every page — consistency is itself a feature.

### Error handling

- **One error shape** — the API contract says `{ "message": ... }`; two
  exception handlers in [main.py](../backend/app/main.py) reshape FastAPI's
  defaults so *every* error, from any layer, matches.
- **Status codes carry meaning**: 401 not-logged-in vs 403 not-allowed vs
  404 not-found-*or-not-yours* (deliberate ambiguity for private events) vs
  409 conflict (capacity, duplicate connection, illegal status transition)
  vs 422 invalid input.
- **Frontend mirrors it**: `ApiError(status, message)` lets pages branch on
  status while showing the server's human-readable message.

### Security (the deepest vein in this codebase)

- **Session security**: httpOnly cookie (XSS can't steal), SameSite=Lax +
  double-submit CSRF token (other sites can't forge), server-side revocable
  opaque tokens (logout means logout), 24h lifetime.
- **Authorization is layered**: visibility logic lives in *both* the map
  query (SQL) and the single-event check (`user_can_view_event`) — the
  same policy enforced at two altitudes.
- **Information hiding as policy**: private events 404; `address` nulled
  in the schema unless host or confirmed participant; admin login burns a
  hash on unknown emails so response timing doesn't reveal account existence
  ([core/admin.py](../backend/app/core/admin.py)).
- **Input hardening**: Pydantic bounds every field; LIKE wildcards escaped
  in people search ([routers/profiles.py](../backend/app/routers/profiles.py));
  upload endpoint whitelists content types and caps size; UUID primary keys
  make IDs unguessable in shared links.
- **Integrity in the database**: `UNIQUE`, `CHECK (status IN ...)`,
  `CHECK (requester_id <> addressee_id)`, `ON DELETE CASCADE` for personal
  data vs `SET NULL` for hosted events (events outlive a deleted host —
  a *product* decision encoded as a *foreign key*).

### Testing philosophy

Two complementary layers, worth imitating:

- **[scripts/smoke_test.sh](../backend/scripts/smoke_test.sh)** — 55 curl
  checks against a *running* server: cheap, honest, end-to-end.
- **[backend/tests/](../backend/tests/)** — 24 pytest tests, in-process via
  httpx `ASGITransport`, against a disposable `ours_test` database created
  from `Base.metadata` each run. Note the fixtures: `make_user` returns a
  *client already carrying auth cookie + CSRF header*, so tests read like
  user stories (`dylan = await make_user(...)`; `await dylan.post(...)`).
- What's tested is *behavior through the public API*, not internals — the
  suite survives refactors (it didn't change when handlers did).

### Suggested exercises (in rising difficulty)

1. **Read**: follow `PUT /api/events/{id}/rsvp` yourself, file by file, and
   write down every place a request can be rejected and with which status.
2. **Extend**: add `GET /api/users/me/events` (events I host or attend).
   You'll touch router + schema + a test — no model changes.
3. **Migrate**: add a `last_seen_at` column to `users` via a model change +
   autogenerate + *reviewing the migration before applying*.
4. **Harden**: wire rate limiting on `/api/auth/login` (the one stack item
   still unwired) and add a test proving a 6th rapid attempt gets 429.
5. **Refactor**: extract the RSVP capacity logic into a service function and
   watch the tests stay green — experience "tests as a safety net" firsthand.

---

*Companion documents: [DECISIONS.md](DECISIONS.md) and
[FRONTEND_DECISIONS.md](FRONTEND_DECISIONS.md) record every judgment call
made during the build, including the ones later revised — reading a
decision log next to the code it produced is one of the fastest ways to
absorb engineering judgment.*
