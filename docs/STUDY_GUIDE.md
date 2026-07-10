# The Ours Codebase — A Full-Stack Engineering Course

This is a course, not a reference. It assumes you're comfortable with basic
Python and JavaScript but new to most of the technologies here, and its goal
is not just that you *understand* this codebase — it's that you can **explain
every part of it in your own words**, to a teammate, an interviewer, or a
rubber duck.

**How to use it:**

- Read with the code open. Every concept points at a real file in this repo.
- Each module starts with **🎯 By the end you should be able to…** — treat
  those as a checklist, and ends with **✍️ Explain it yourself** prompts.
  Don't skip them. Answer out loud or in writing. If you can't, reread —
  that's the signal.
- Analogies are marked 💡. Steal them; they're for re-telling.
- **Accuracy note:** every file path, function name, migration ID, and test
  name in this guide was mechanically verified against the code when it was
  written. Code moves; if a reference doesn't resolve, `grep` for the symbol
  and trust the code over the guide — then fix the guide.

**The modules:**

- **0.** The big picture — what this app is and what "full stack" means
- **0.5** Run it first — see it working before you study it
- **1.** How the web works — HTTP, JSON, cookies (the ground everything stands on)
- **2.** The database — PostgreSQL, tables, PostGIS, migrations
- **3.** The backend — FastAPI, async, Pydantic, SQLAlchemy, dependency injection
- **4.** Identity & security — sessions, XSS, CSRF, authorization
- **Interlude.** One request, all the way down — a single RSVP traced through every layer
- **5.** The frontend — React's render loop, state, hooks, the map
- **6.** Testing — how we know it works, and what we honestly don't know
- **7.** The design decisions — what we chose, what we rejected, and what it cost
- **8.** Vocabulary & patterns — the words engineers use, with plain definitions
- **9.** Exercises — prove it to yourself

---

## Module 0 — The Big Picture

**🎯 By the end you should be able to:** describe what Ours does and how its
product philosophy shows up in code · explain the three-program architecture
and why rules live on the server · define monolith vs microservices and
argue for the choice made here.

### What this application is

**Ours** is a neighborhood community platform. Residents open a map of their
area, see nearby **gatherings** ("board games in the park") and **help
requests** ("help me move a bookshelf"), RSVP, form mutual **connections**
with people they've met, and invite them to future events.

The unusual part is the goal: most social apps profit from keeping you on a
screen; Ours measures success by *time people spend together in real life*.
That philosophy is physically built into the code:

- Messaging exists **only inside an event**. Look at
  [backend/app/models/message.py](../backend/app/models/message.py): every
  message row *requires* an `event_id`. There is no table where a
  free-floating chat could even live. The schema is the policy.
- Safety is first-class: you can block someone and they stop existing in
  your world — search, connections, invites, and even the map itself.

### What "full stack" means here

The app is three programs that talk to each other:

1. **The frontend** (`frontend/`) — JavaScript that runs *in the user's
   browser*. It draws the screens, holds what the user is currently looking
   at, and asks the backend for data.
2. **The backend** (`backend/`) — Python that runs *on a server* (during
   development: your laptop). It owns all the rules: who may see what, what
   a valid event is, who is logged in.
3. **The database** (PostgreSQL) — a separate program whose only job is to
   store data durably and answer questions about it fast.

💡 **Analogy — the restaurant.** The frontend is the dining room and the
menu: what the customer sees and touches. The backend is the kitchen: where
the actual work happens, with rules and quality control. The database is the
pantry: organized storage. Customers never walk into the pantry; every
request goes through the kitchen. This matters because the dining room is
*enemy territory* — anyone can open browser dev-tools and modify the
frontend. Every rule that matters is enforced in the kitchen.

### The architecture in one picture

```
   Browser (user's machine)                Your server
┌──────────────────────────┐          ┌────────────────────────────┐
│  React app (frontend/)   │  HTTP    │  FastAPI app (backend/)    │
│  - draws screens         │ ───────▶ │  - checks who you are      │
│  - remembers UI state    │  JSON    │  - enforces every rule     │
│  - src/api/client.js is  │ ◀─────── │  - talks to the database   │
│    the ONLY network code │          └─────────────┬──────────────┘
└──────────────────────────┘                        │ SQL
                                      ┌─────────────▼──────────────┐
                                      │  PostgreSQL + PostGIS      │
                                      │  - 13 tables               │
                                      │  - enforces data integrity │
                                      └────────────────────────────┘
```

The shape is called a **monolith with a separate SPA client**:

- **Monolith** = the whole backend is one program. The alternative
  (microservices — many small programs talking over a network) adds
  operational complexity that only pays off with large teams. One
  deliberate rule of this codebase: *don't add layers before they earn
  their existence.* (Module 7 makes the full argument.)
- **SPA (Single-Page Application)** = the browser downloads the JavaScript
  app once; after that, navigation swaps components in place and only *data*
  crosses the network. The alternative (server-rendered pages) re-sends
  whole HTML pages per click.

**✍️ Explain it yourself**

1. Why can't the frontend be trusted to enforce rules like "only the host
   may delete an event"? Where is that rule actually enforced in this repo?
2. In your own words: what is the difference between a monolith and
   microservices, and why is a monolith right *here*?
3. Using the restaurant analogy, explain what happens when a user taps
   "Going" on an event.

---

## Module 0.5 — Run It First

**🎯 By the end you should be able to:** start all three programs, click
through the core loop as two different users, and run both test suites.

You learn a codebase dramatically faster after you've *seen it move*.
Fifteen minutes, then start Module 1.

**Prerequisites:** [Postgres.app](https://postgresapp.com/) installed and
running (elephant icon in the menu bar), Python 3.12+, Node 20+.

```bash
# 1. Database — once
psql -d postgres -c "CREATE DATABASE ours_dev;"
psql -d ours_dev  -c "CREATE EXTENSION postgis;"

# 2. Backend — terminal one
cd backend
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env            # then edit: your macOS username in DATABASE_URL,
                                # and a real SECRET_KEY (command is in the file)
.venv/bin/alembic upgrade head  # builds every table from the migration chain
.venv/bin/uvicorn app.main:app --reload --port 8000

# 3. Frontend — terminal two
cd frontend
npm install
npm run dev
```

**Now click through the core loop:**

1. Open http://localhost:5173 — register an account, pick interests.
2. Create an event: click the mini-map to drop a pin, set a time.
3. Open a second browser (or a private window), register a *second*
   account, find the event on the map, RSVP "Going".
4. As user two, open user one's profile from the participants list and send
   a connection request; as user one, accept it under Connections.
5. Post a message inside the event from each account.
6. Visit http://localhost:8000/docs — the API's auto-generated interactive
   documentation. Expand `PUT /api/events/{event_id}/rsvp`. You'll meet the
   machinery behind this page in Module 3.

**Prove the safety net works:**

```bash
cd backend
.venv/bin/pytest                       # 24 tests, disposable ours_test DB
psql -d ours_dev -c "TRUNCATE users, events, communities CASCADE;"
bash scripts/smoke_test.sh             # 55 end-to-end curl checks
```

(The smoke test registers fixed emails — hence the reset first. It will
wipe your click-around accounts; that's fine, they were practice.)

**✍️ Explain it yourself**

1. What are the three processes now running on your machine, and what port
   does each listen on? (Trick: the database was already running.)
2. What did `alembic upgrade head` actually do, mechanically?

---

## Module 1 — How the Web Works (the ground floor)

**🎯 By the end you should be able to:** define request/response, name the
five HTTP methods and the nine status codes this API uses · explain
statelessness and how cookies fake memory on top of it · explain what the
dev proxy is for.

You cannot explain a web app without these four ideas. Most people use them
daily without being able to define them — being able to define them is
exactly the edge you're after.

### 1.1 HTTP: the request/response protocol

Every interaction between frontend and backend is an **HTTP request** — a
small structured text message — and an **HTTP response** coming back.
A request has:

- a **method** (verb): what kind of action —
  `GET` (read), `POST` (create), `PUT` (replace/set), `PATCH` (partial
  update), `DELETE` (remove).
- a **path** (noun): which thing — `/api/events/123/rsvp`.
- **headers**: metadata, like "I'm sending JSON" or "here's my CSRF token".
- optionally a **body**: the data, as JSON.

A response has a **status code**, headers, and usually a JSON body. Status
codes are a compressed language and this codebase uses them precisely:

| Code | Meaning | Where you'll see it here |
|---|---|---|
| 200 | OK | successful reads and updates |
| 201 | Created | new event, new connection, new report |
| 204 | No content (success, nothing to say) | login, logout, deletes |
| 400 | Bad request | wrong password, duplicate email |
| 401 | **Who are you?** (not logged in) | any protected route without a session |
| 403 | **I know who you are — no.** (not allowed) | non-host editing an event; missing CSRF token |
| 404 | Not found | missing event — *and* private events you can't see (see Module 4) |
| 409 | Conflict (valid request, state says no) | event full; already connected; illegal status change |
| 422 | Unprocessable (invalid input shape) | password too short, missing field |

💡 **Analogy — postal mail.** A request is an envelope: the method+path is
what's written on the front, headers are the stamps and routing marks, the
body is the letter inside. HTTP is **stateless** — each envelope is a
complete, self-contained message; the postal service remembers nothing
between letters. "How does the server know I'm logged in, then?" — that's
what cookies solve (Module 4), and it's a top-tier interview question.

The API this backend exposes is **REST-style**: URLs name *resources*
(`/api/events`, `/api/connections`), methods say what to do to them. Skim
any router file, e.g.
[backend/app/routers/blocks.py](../backend/app/routers/blocks.py) — you can
read the whole feature from just the method + path + status codes.

### 1.2 JSON: the shared language

The frontend speaks JavaScript, the backend speaks Python. **JSON**
(JavaScript Object Notation) is the neutral text format both understand:

```json
{ "title": "Board games in the park", "capacity": 2, "location": {"lat": 40.65, "lng": -74.0} }
```

Python turns this into dicts; JavaScript turns it into objects. Every API
body in this app is JSON. (One exception: avatar image upload uses
`multipart/form-data`, the format designed for files.)

### 1.3 Cookies: the server's memory of you

A **cookie** is a small piece of data the server asks the browser to store
(`Set-Cookie` response header). From then on the browser **automatically
attaches it to every request to that site**. That automatic attachment is
what turns stateless HTTP into "the server remembers me" — and also what
creates a whole attack category (CSRF, Module 4).

This app sets two cookies at login — find it in
[backend/app/routers/auth.py](../backend/app/routers/auth.py) `login()`:
`ours_auth` (the session; httpOnly, so JavaScript can't read it) and
`ours_csrf` (deliberately readable; explained in Module 4).

### 1.4 Same-origin and the dev proxy

Browsers treat `localhost:5173` (frontend dev server) and `localhost:8000`
(backend) as **different origins** and restrict cross-origin requests —
a protection called CORS. Rather than fight it, development uses a **proxy**:
[frontend/vite.config.js](../frontend/vite.config.js) tells the Vite dev
server "anything starting with `/api` or `/media`, quietly forward to
port 8000." The browser believes everything is one origin; cookies flow
naturally.

**✍️ Explain it yourself**

1. What does it mean that HTTP is stateless, and what mechanism does this
   app use to make logins survive between requests?
2. A teammate asks the difference between 401 and 403. Answer using two
   endpoints from this repo as examples.
3. Why does the frontend dev server proxy `/api` instead of calling
   `http://localhost:8000` directly?

---

## Module 2 — The Database (PostgreSQL + PostGIS)

**🎯 By the end you should be able to:** read the 13-table schema as a
product spec · explain constraints, foreign-key delete rules, and why IDs
are UUIDs · explain what PostGIS adds and how "events near me" stays fast ·
describe the migration workflow and why generated migrations get reviewed.

### 2.1 What a relational database is

**PostgreSQL** ("Postgres") stores data in **tables** — rigid grids where
every row has the same typed columns. You talk to it in **SQL**. Its
superpower over "just save a JSON file" is threefold:

1. **Integrity** — the database *refuses* bad data. Not "the app tries to
   avoid it" — refusal, at the storage layer.
2. **Relationships** — rows point at rows via **foreign keys**, and the DB
   guarantees the pointers are never dangling.
3. **Speed at scale** — indexes let it answer "events within 3 km" without
   reading every row ever written.

### 2.2 Reading this app's schema like a story

The 13 tables (find each in [backend/app/models/](../backend/app/models/))
*are* the product spec, if you know how to read them:

- **users** — credentials and account flags only (email, hashed password,
  `is_active`, `is_superuser`). Identity, not personality.
- **profiles** — the human part (display name, bio, avatar), linked to users
  one-to-one. Why split? Different sensitivity and different audiences: the
  API never sends a `users` row to another user, only profiles.
- **communities** — named neighborhoods with an optional map center.
- **events** — the heart. One table serves *both* gatherings and help
  requests, distinguished by a `kind` column (a decision unpacked in
  Module 7).
- **event_participants** — who's involved with which event, with a `status`
  (`invited`, `going`, `maybe`, `declined`, `attended`, `cancelled`). One
  clever unification: an *invitation* is just a participation row with
  status `invited` and an `inviter_id` — accepting flips it to `going`.
  One table instead of two, one uniqueness rule ("one row per person per
  event") instead of cross-table checks.
- **connections** — the mutual-friend graph: `requester_id`, `addressee_id`,
  status `pending`/`accepted`. Direction matters — only the addressee may
  accept — so rows keep their true direction and the *code* checks both
  directions for duplicates.
- **blocks / reports** — safety: who silenced whom; the moderation queue.
- **interests + user_interests + event_interests** — a tag vocabulary and
  two **join tables** implementing many-to-many links (a person has many
  interests; an interest has many people — neither side can hold a single
  foreign key, so a third table holds pairs).
- **event_messages** — chat scoped to an event, by construction.
- **access_tokens** — live login sessions (Module 4).

### 2.3 Constraints: rules the database enforces

Open [backend/app/models/event.py](../backend/app/models/event.py) and
[connection.py](../backend/app/models/connection.py) and find these:

- `UNIQUE` — no two users share an email; no duplicate RSVP rows.
- `CHECK (status IN (...))` — a status column literally cannot hold a value
  outside its list, no matter how buggy the app code is.
- `CHECK (requester_id <> addressee_id)` — you cannot befriend yourself,
  says the storage engine itself.
- `NOT NULL` — an event without a location cannot exist.
- **Server defaults** — `gen_random_uuid()`, `now()`: the database fills in
  IDs and timestamps itself, so even a hand-typed SQL insert gets them.

💡 **Analogy — the bouncer at the pantry door.** App code *tries* to send
good data; constraints *guarantee* nothing bad gets shelved. Defense in
depth: even if every Python check failed, the data stays sane.

The **foreign-key delete rules** encode product decisions:

- `ON DELETE CASCADE` on profiles, connections, messages, RSVPs: when a
  user deletes their account, their personal data genuinely goes away.
- `ON DELETE SET NULL` on `events.host_id`: hosted events *survive* with
  the host cleared — because other people already RSVP'd, and deleting your
  account shouldn't delete their plans. **A product decision, spelled as a
  foreign-key clause.** This is the single best example in the repo of
  "the schema is the spec."

### 2.4 Why IDs are UUIDs

Primary keys here are UUIDs (`7b7c65af-59bd-...`), not counting integers
(1, 2, 3…). Event IDs appear in shareable URLs; sequential IDs would let a
stranger enumerate `/events/1`, `/events/2`, … and also leak how many events
exist. UUIDs are unguessable. Trade-off: bigger, unsortable — Module 7 has
the full cost accounting.

### 2.5 PostGIS: teaching a database geography

PostGIS is a Postgres **extension** — a plugin adding a `geography` column
type plus functions and index support. The three ideas you need:

- **A point is `(longitude, latitude)` — longitude first.** Math convention
  (x, then y), opposite of how humans say it. Half of all map bugs are these
  two swapped; get it wrong and your event is in Antarctica. This repo
  isolates the conversion in one tiny file —
  [backend/app/core/geo.py](../backend/app/core/geo.py) — so no other code
  ever handles raw coordinates.
- **SRID 4326** identifies *which* coordinate system: WGS 84, the one GPS
  uses. (Map data has many; you must say which.)
- **`geography` vs `geometry`**: `geometry` computes on a flat plane (fast,
  but distances come out in meaningless degrees); `geography` computes on
  the curved Earth and returns honest **meters**. This app uses `geography`.

The signature query, in
[backend/app/routers/events.py](../backend/app/routers/events.py)
`discover_events()`:

- `ST_DWithin(location, my_point, radius_m)` — "within X meters", and
  crucially it can use the **GiST spatial index** (declared in the Event
  model) to skip nearly all far-away rows instead of computing every
  distance. 💡 A GiST index is like a map's grid squares: to find cafés near
  you, check your square and its neighbors — don't scan the whole atlas.
- `ST_Distance(...)` — exact meters, used to sort nearest-first and to show
  "1.2 km" in the sidebar.

### 2.6 Migrations: version control for the schema

Code evolves in git; the database's *shape* evolves in **Alembic
migrations** — small Python scripts in
[backend/alembic/versions/](../backend/alembic/versions/), each with a
revision ID and a pointer to its parent, forming a chain like commits.
The database stores which revision it's on (a one-row table,
`alembic_version`); `alembic upgrade head` runs only what's missing.

The workflow used throughout this project:

1. Change a model in `app/models/`.
2. `alembic revision --autogenerate -m "..."` — Alembic **diffs the models
   against the live database** and writes the script that closes the gap.
3. **Read the generated script before applying.** Autogenerate is a good
   clerk and a mediocre architect. This is not paranoia: in this very repo
   it once produced a migration referencing a module it never imported —
   the review caught what would have been a crash (see
   `5a4fdb5228c8_create_access_tokens_table.py`, whose `created_at` column
   type was hand-corrected for exactly this reason).
4. `alembic upgrade head`.

Migrations can also carry **data**, not just structure: see
`7c52bd870d32_seed_starter_interests.py`, which inserts the 16 starter
interest tags so every environment gets the same vocabulary.

**✍️ Explain it yourself**

1. Explain to a non-engineer why deleting your account removes your messages
   but not the events you hosted — and *where* that behavior is defined.
2. What's the difference between the app validating a status value and the
   database CHECK-constraining it? Why have both?
3. Why longitude-first? And why does this repo route all coordinate handling
   through one file?
4. What does `--autogenerate` actually compare, and why must you still read
   its output?
5. What is a join table, and why does many-to-many require one?

---

## Module 3 — The Backend (FastAPI + async + SQLAlchemy)

**🎯 By the end you should be able to:** explain the Uvicorn/FastAPI/ASGI
division of labor · explain `async`/`await` and what one blocking call would
do · distinguish engine from session · describe how Pydantic turns type
annotations into validation · draw the dependency-injection chain from
memory.

### 3.1 The cast of characters

When you "run the backend," three layers of software cooperate:

- **Uvicorn** — the *server*: opens port 8000, accepts raw HTTP
  connections, parses bytes into request objects. Knows nothing about your
  app's logic.
- **FastAPI** — the *framework*: routes each request to the right Python
  function, validates inputs, serializes outputs, generates docs.
- **Your code** — the handlers, models, and schemas in `backend/app/`.

They meet at **ASGI** — a standard Python interface (the async successor to
WSGI) that lets any ASGI server run any ASGI framework. 💡 Uvicorn is the
telephone switchboard; FastAPI is the receptionist routing each call to the
right department; your handlers are the departments.

The command that starts everything —
`uvicorn app.main:app --reload --port 8000` — means: "in package `app`,
module `main`, find the variable named `app` and serve it." That variable is
created in [backend/app/main.py](../backend/app/main.py), the assembly
point: middleware, error handlers, all eleven routers, static file mount,
admin panel, health check.

### 3.2 `async`/`await`: the concurrency model (explain-this-in-interviews tier)

Every handler in this codebase is `async def`. Here's the concept from zero:

A web server's life is mostly **waiting** — for the database, for disk, for
the network. A traditional synchronous server parks one thread per request;
the thread sits idle during every wait. An **async** server uses one thread
running an **event loop**: when a task hits a wait point — marked `await` —
it *steps aside*, the loop runs someone else, and it resumes when the wait
completes. One process, thousands of in-flight requests.

💡 **Analogy — the chess master.** A master playing 30 boards
simultaneously doesn't watch you think — she makes her move (does actual
work), then walks to the next board (next request) while you ponder (the
database query runs). `await` marks each "walk away" point.

Rules that follow (and that this codebase obeys):

- Anything that waits must be awaited: `await db.execute(...)`,
  `await db.commit()` — every I/O in every router.
- The whole chain must be async: async framework (FastAPI) → async ORM
  (SQLAlchemy async mode) → async driver (asyncpg). A single synchronous,
  slow call in a handler would freeze *every* request in the process —
  that's why the stack insists on asyncpg rather than the sync driver.

### 3.3 Pydantic: types that do work

FastAPI's core trick: Python type annotations aren't just documentation —
they're executed. A **Pydantic model** declares a data shape:

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str = Field(min_length=1, max_length=80)
```

Declare a handler parameter of this type and FastAPI will parse the JSON
body, validate every field, and hand you a typed object — or reject the
request with a 422 *before your code runs*. Same for query parameters:
in `discover_events`, `lat: float = Query(ge=-90, le=90)` means an
out-of-range latitude never reaches your logic.

All shapes live in [backend/app/schemas/](../backend/app/schemas/). Two
things to study there:

- **Different shapes for different directions.** `EventCreate` (what
  clients may send — no `id`, no `status`; the server owns those) vs
  `EventDetail` (what they get back). Never one class for both.
- **Cross-field rules** via `@model_validator` — e.g. `ends_at` must be
  after `starts_at` ([schemas/event.py](../backend/app/schemas/event.py)),
  and a report must target *something*
  ([schemas/report.py](../backend/app/schemas/report.py)).

Bonus: from these same annotations FastAPI auto-generates the interactive
API docs you visited in Module 0.5. Free, always current.

### 3.4 SQLAlchemy: objects ↔ rows

**SQLAlchemy** is an ORM (Object-Relational Mapper): it maps Python classes
to tables so you mostly write Python instead of SQL strings. The 2.0 syntax
used here packs a lot into one line:

```python
email: Mapped[str] = mapped_column(Text, unique=True)
```

`Mapped[str]` = column of strings, NOT NULL (because not `Optional`).
`Mapped[str | None]` would mean nullable. The annotation *is* the nullability
rule. `mapped_column(...)` carries DB details (type, uniqueness, defaults).

Two objects to keep straight — a classic interview distinction:

- The **engine** ([core/database.py](../backend/app/core/database.py)) is
  created **once per app**. It owns a **connection pool**: opening a DB
  connection is slow, so the engine keeps a few warm and lends them out.
- A **session** is created **per request**: a short-lived workspace that
  borrows a connection, tracks your changes, and ends in `commit()` (save
  it all) or rollback (as if nothing happened). Sessions make work
  **transactional** — in `create_event`, the event row and its interest
  tags commit together or not at all.

💡 Engine = the office's phone system; session = one phone call.

You'll also see `await db.flush()` (send pending inserts so `event.id`
exists, but don't end the transaction) and `await db.refresh(event)`
(re-read the row so server-generated defaults like `status='open'` appear on
the Python object). And ORM ≠ no SQL: `discover_events` composes raw
PostGIS functions via `func.ST_DWithin(...)` — the ORM is a tool, not a cage.

### 3.5 Dependency injection: the pattern that runs FastAPI

**The problem:** every handler needs a DB session; most need the current
user. Without help, each handler starts with the same boilerplate.

**The solution:** declare needs as parameters; the framework fulfills them.

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

That `yield` splits the function: before = setup (open a session), after =
cleanup (close it, even if the handler raised). A handler that declares
`db: DB` (the alias in [routers/deps.py](../backend/app/routers/deps.py))
gets a fresh session, automatically cleaned up.

Here is the full wiring for a typical protected handler — this diagram is
worth redrawing from memory, because DI is the pattern newcomers find most
magical-and-confusing, and it stops being magic the moment you can draw it:

```
async def set_rsvp(event_id, payload, db: DB, user: CurrentUser)
                                      │            │
        ┌─────────────────────────────┘            │
        │                                          ▼
        │                    current_active_user   (fastapi-users, core/auth.py)
        │                          │
        │                          │ 1. CookieTransport reads the
        │                          │    "ours_auth" cookie from the request
        │                          ▼
        │                    DatabaseStrategy.read_token
        │                          │ 2. SELECT ... FROM access_tokens
        │                          │    WHERE token = <cookie value>
        │                          │    (+ created_at within 24h lifetime)
        │                          ▼
        │                    get_access_token_db ─── needs a session ───┐
        │                          │ 3. row found → load User row       │
        │                          │    (is_active checked)             │
        │                          ▼                                    │
        │                    User object, or 401 — handler never runs   │
        │                                                               │
        └── get_db  ◀────────────────────────────────────────────────────┘
                │   FastAPI CACHES dependencies per request:
                │   the auth lookup and your handler share ONE session
                ▼
        AsyncSessionLocal() → borrows a pooled connection → Postgres
```

Read it bottom-up once, too: one pooled connection, wrapped in one session,
shared by everything this request needs, closed by `get_db`'s post-`yield`
cleanup no matter what happened.

💡 DI is a restaurant kitchen's mise en place: the chef (handler) finds
ingredients (session, user) already prepared at their station rather than
fetching them mid-recipe. Bonus: in tests you can swap what gets injected —
which is exactly how the test suite points everything at a scratch database.

### 3.6 Where the business rules live

This codebase keeps logic in the **routers**, promoting shared rules to
[routers/deps.py](../backend/app/routers/deps.py): `user_can_view_event`
(the visibility policy), `blocked_either_way` and `blocked_counterparts`
(block checks), `ALLOWED_STATUS_TRANSITIONS` (the event lifecycle),
`get_event_or_404`. Read that one file and you know most of the app's law.

A worthwhile study exercise: notice the *pressure* toward a service layer.
`set_rsvp` in [routers/participants.py](../backend/app/routers/participants.py)
is ~35 lines of policy. At what size would you extract it? Module 7 states
the position this codebase takes; developing your own judgment is the point.

**✍️ Explain it yourself**

1. Uvicorn vs FastAPI: what does each do? What is ASGI?
2. Explain `async`/`await` with your own analogy (not the chess one). What
   goes wrong if one handler makes a slow *synchronous* call?
3. Engine vs session — lifetimes, jobs, and why the pool exists.
4. What happens, step by step, when a client POSTs invalid JSON to
   `/api/events`? Where does the 422 come from?
5. Close the book and redraw the DI diagram for `set_rsvp`. Which arrow is
   the 401? Which arrow is the shared session?

---

## Module 4 — Identity & Security (the deepest module)

**🎯 By the end you should be able to:** explain hashing, and what a session
physically is in this app · argue the JWT-vs-database-sessions trade-off ·
explain XSS and CSRF and the exact mechanism that defeats each · locate the
authorization policy at both of its enforcement altitudes.

Security is where this codebase teaches the most. Take it slowly.

### 4.1 Passwords: never stored, only hashed

The `users` table has `hashed_password`, never the password. A **hash** is a
one-way fingerprint: easy to compute, infeasible to reverse. At login the
server hashes the submitted password and compares fingerprints
(fastapi-users does this inside `user_manager.authenticate`). If the
database ever leaks, attackers get fingerprints, not keys. Password *policy*
(≥8 chars, ≠ email) lives in `UserManager.validate_password` in
[core/auth.py](../backend/app/core/auth.py).

### 4.2 Sessions: what "being logged in" physically is

HTTP is stateless, so "logged in" must be manufactured. This app's design —
the result of two deliberate upgrades during development — is worth
explaining end-to-end:

1. At login ([routers/auth.py](../backend/app/routers/auth.py)), the server
   generates a long **random opaque string** — the token — and stores it as
   a row in `access_tokens`
   ([models/access_token.py](../backend/app/models/access_token.py)) linked
   to the user.
2. The token is sent back in an **httpOnly cookie** (`ours_auth`). httpOnly
   = JavaScript cannot read it; only the browser's network machinery can.
3. On every request, the browser attaches the cookie; the backend looks the
   token up in the table (and checks it isn't past the 24-hour lifetime).
   Row found → that's your user. This is the `CurrentUser` dependency you
   saw in the Module 3 diagram.
4. **Logout deletes the row.** The session is dead *server-side* — even if
   someone had copied the cookie, it now unlocks nothing. There's a test
   that proves exactly this by "stealing" the cookie before logout:
   `test_logout_revokes_session_server_side` in
   [tests/test_auth.py](../backend/tests/test_auth.py).

💡 The token is a **coat-check ticket**: a meaningless number that only
means something because the clerk (database) has a matching stub. Tear up
the stub (logout) and the ticket is garbage.

**The design history teaches the trade-offs.** Version 1 used **JWTs** —
self-contained signed tokens the server can verify *without* a database
lookup. Faster, but unrevocable: a stolen JWT works until it expires,
because there's no stub to tear up. Version 2 (current) accepts one DB
lookup per request to make logout real. Version 1 also kept the token in
`localStorage`, readable by JavaScript — which brings us to:

### 4.3 XSS — why the cookie is httpOnly

**Cross-Site Scripting**: if an attacker ever gets JavaScript to run in your
page (via an unescaped comment, a compromised dependency…), that script can
read anything JavaScript can read. A token in `localStorage` is stolen in
one line. An httpOnly cookie is *invisible* to script — the entire class of
"XSS steals your session" dies. That's why the login response body is empty
(204): the token never passes through JavaScript's hands at all.

### 4.4 CSRF — the attack cookies invite, and the double-submit defense

Cookies attach **automatically** — even when the request is triggered by a
different website. Evil.com can render an invisible form that POSTs to
`ours.app/api/events/123/rsvp`; if you're logged in, your browser helpfully
attaches your session cookie. That's **Cross-Site Request Forgery**: riding
someone's cookie without ever seeing it.

The defense here (see `login()` in
[routers/auth.py](../backend/app/routers/auth.py) and the `csrf_protect`
middleware in [main.py](../backend/app/main.py)) is the **double-submit
cookie** pattern, built on one asymmetry:

> Other sites can make your browser **send** cookies, but they can never
> **read** them — only same-origin JavaScript can.

So: login sets a second, *deliberately readable* cookie (`ours_csrf`,
random). The frontend ([api/client.js](../frontend/src/api/client.js))
reads it and echoes it in an `X-CSRF-Token` header on every mutating
request. The middleware compares header to cookie: match → genuine frontend;
missing/mismatch → 403. Evil.com can trigger the request, but can't read
the cookie, so can't forge the header.

Memorize the pairing — it's a beautiful symmetry:

| Attack | Vector | Defense here |
|---|---|---|
| **XSS** | script *reads* your secrets | token in **unreadable** (httpOnly) cookie |
| **CSRF** | site *rides* your auto-sent cookie | prove readability of a **readable** cookie |

### 4.5 Authorization: who may do what (≠ authentication)

**Authentication** = who are you (§4.2). **Authorization** = what may
*you* do. This app enforces authorization at two altitudes:

- **Inside the SQL** — `discover_events` composes visibility directly into
  the query: public events, OR your own, OR your community's, OR private
  ones you're invited to — AND NOT hosted by anyone you have a block with.
  The database *never returns* rows you may not see; there is no moment
  where forbidden data exists in memory to leak.
- **Per-object** — `user_can_view_event` in
  [routers/deps.py](../backend/app/routers/deps.py) makes the same decision
  for a single event, and RSVPs, participants, messages, and invites all
  route through it.

Same policy, two enforcement points — deliberate redundancy (defense in
depth).

Two subtle policies worth retelling:

- **404 instead of 403 for private events.** A 403 would whisper "something
  exists here that you can't see." A 404 says nothing. Knowing an event
  *exists* is already information — e.g., an abuser probing whether their
  blocker is hosting something.
- **Field-level privacy**: the event's `address` is returned only to the
  host and confirmed attendees — everyone else gets the map pin. Enforced
  where the response is built ([routers/events.py](../backend/app/routers/events.py)
  `read_event`), which is only possible because the API shape (schema) is
  separate from the DB shape (model).

Other hardening worth finding: LIKE-wildcard escaping in people search
([routers/profiles.py](../backend/app/routers/profiles.py)) so searching
"100%" means the literal text; upload whitelisting (type + 2 MB cap) on
avatars; the admin login gate hashing a password even for unknown emails so
response *timing* doesn't reveal whether an account exists
([core/admin.py](../backend/app/core/admin.py)); SQL injection neutralized
throughout by parameterized queries (the ORM never glues user input into SQL
text).

**✍️ Explain it yourself**

1. Walk through login → authenticated request → logout in terms of the
   `access_tokens` table. Where exactly does "logging out" happen?
2. JWT vs database-backed sessions: the trade, and why this app chose the
   latter. (This is a real interview question.)
3. Explain XSS and CSRF to a junior dev, including why one is beaten by an
   *unreadable* cookie and the other by proving you can *read* a cookie.
4. Why 404 and not 403 for a private event? What could 403 leak, concretely?
5. Where are blocks enforced? (Trap: the answer is at least five places —
   search, connections, invites, the map query, single-event view.)

---

## Interlude — One Request, All the Way Down

**🎯 By the end you should be able to:** narrate this entire trace from
memory, naming the file at every step. This is the keystone — every concept
from Modules 1–4 fires here in sequence, and Module 5's concepts get
previewed. Read it twice: once now, once after Module 5.

**The scene:** Eleanor is looking at Dylan's "Board games in the park"
(capacity 2, one seat taken) in her browser. She clicks **Going**.

### In the browser (steps 1–4)

1. **The click.** Eleanor's screen is the `EventDetail` component
   ([pages/EventDetail.jsx](../frontend/src/pages/EventDetail.jsx)). The
   Going button's `onClick` runs `rsvp("going")`, which is
   `act(() => api.put(`/api/events/${id}/rsvp`, { status: "going" }))`.
   `act()` first clears any previous error (`setActionError(null)` — a
   state update), then awaits the API call.
2. **The single funnel.** `api.put` lands in `request()` in
   [api/client.js](../frontend/src/api/client.js) — the only file in the
   frontend that talks to the network. It sets
   `Content-Type: application/json`, serializes the body, and — because PUT
   is a mutating method — calls `readCsrfCookie()` to copy the `ours_csrf`
   cookie's value into an `X-CSRF-Token` header.
3. **What the browser adds on its own.** As the request leaves, the browser
   attaches every cookie for this site — including `ours_auth`, the
   httpOnly session cookie that no line of our JavaScript can see. Two
   proofs of identity are now aboard: one we attached (CSRF header), one
   the browser attached (session cookie).
4. **The proxy.** The URL is relative (`/api/...`), so it hits the Vite dev
   server on port 5173, whose proxy rule
   ([vite.config.js](../frontend/vite.config.js)) forwards it to the
   backend on port 8000. Same-origin as far as the browser knows.

### Into the backend (steps 5–8)

5. **Uvicorn** accepts the connection, parses the raw bytes into an HTTP
   request object, and hands it to the FastAPI app via ASGI.
6. **Middleware.** The request passes through the middleware stack in
   [main.py](../backend/app/main.py). (Fine print: `csrf_protect` was
   registered *after* CORS, which in Starlette makes it the *outer* layer —
   it runs first.) The CSRF check fires: mutating method ✓, path starts
   with `/api` ✓, `ours_auth` cookie present ✓ → compare the
   `X-CSRF-Token` header to the `ours_csrf` cookie. Match → continue.
   (Mismatch would have ended everything here: 403, handler never runs.)
7. **Routing.** FastAPI matches `PUT /api/events/{event_id}/rsvp` to
   `set_rsvp()` in
   [routers/participants.py](../backend/app/routers/participants.py) and
   parses the path segment into a UUID (garbage in the URL → 422, before
   any code of ours runs).
8. **Dependency resolution** — the Module 3 diagram, live:
   - `db: DB` → `get_db()` opens an `AsyncSession`, borrowing a pooled
     connection from the engine.
   - `user: CurrentUser` → the cookie's token is looked up in
     `access_tokens` (one indexed SELECT, plus the 24h lifetime check), and
     Eleanor's `User` row is loaded — *through the same cached session*.
     No row → 401, handler never runs.
   - `payload: RsvpPayload` → Pydantic validates the body;
     `{"status": "going"}` is one of the three allowed literals. Anything
     else → 422, handler never runs.

### The handler (steps 9–12) — [routers/participants.py](../backend/app/routers/participants.py), `set_rsvp`

9. **Existence + visibility.** `get_event_or_404` loads the event (`db.get`
   by primary key). Then `require_event_view` applies the Module 4 policy:
   Eleanor isn't the host; no block exists between her and Dylan; the event
   is public → she may see it. (Private-and-uninvited would 404 here —
   the "it doesn't exist for you" rule.)
10. **State check.** The event's status is `open` — a `cancelled` or
    `completed` event would 409 ("no longer open").
11. **Capacity.** She's asking for `going`, the event has `capacity=2`, and
    she isn't already confirmed — so the handler counts confirmed
    participants with one `SELECT count(*)`. One of two seats taken → she
    fits. (Count ≥ capacity would 409 "This event is full.")
12. **The write.** No existing participation row for (event, Eleanor) → a
    new `EventParticipant` is added with `status="going"`; `await
    db.commit()` makes it real. At this instant the database's own defenses
    have the final say: the CHECK constraint would reject an illegal status,
    and the UNIQUE(event_id, user_id) constraint would reject a duplicate
    row — even if every Python check above had been deleted.

### Back up (steps 13–16)

13. **Response.** The handler returns `RsvpRead(event_id=..., user_id=...,
    status="going")` — a Pydantic schema, serialized to JSON, sent as a 200.
    `get_db`'s post-`yield` cleanup closes the session; the connection goes
    back to the pool.
14. **The funnel again.** In `client.js`, `res.ok` is true; the JSON is
    parsed and returned. (A 409 would instead have become
    `throw new ApiError(409, "This event is full")`, and `act()`'s catch
    would have put that exact message on screen.)
15. **Re-fetch.** `act()` now calls `reload()` — the function returned by
    the [useApi](../frontend/src/hooks/useApi.js) hook — which re-runs the
    page's loader: `GET` the event and its participants again, fresh from
    the server. No client-side cache to update; the server is the single
    source of truth.
16. **Re-render.** The loader's `setData(...)` is a state update, so React
    re-runs the `EventDetail` function with the new data: Eleanor's row now
    appears in "Who's coming," the Going button computes as active,
    `participant_count` reads 2. React diffs the new tree against the old
    and patches only those DOM nodes (Module 5 explains this loop). Total
    elapsed: tens of milliseconds.

**Worth noticing:** the request could have died at steps 6 (403), 7 (422),
8 (401/422), 9 (404), 10 (409), 11 (409), or 12 (constraint violation) —
each rejection at the *earliest layer that can know*. And one honest gap:
between steps 1 and 14 the Going button is **not disabled** — a double-click
fires two requests. Harmless here (the second is an update of the same row),
but it's a real UX/robustness gap, and fixing it is Exercise 6.

**✍️ Explain it yourself**

1. Close the guide. Narrate the sixteen steps out loud, naming the file at
   each one. (This is the module's entire point.)
2. List every status code this one request could have produced, and the
   step where each dies.
3. Two proofs of identity travel with the request. Which one did our code
   attach, which did the browser attach, and what attack does each defeat?

---

## Module 5 — The Frontend (React + Vite + Leaflet)

**🎯 By the end you should be able to:** explain "UI is a function of
state" and the render → diff → commit loop · use `useEffect` and explain its
dependency array without guessing · name the three state layers and defend
the no-cache decision · trace a 401 from any page to the login screen.

### 5.1 What React actually is

React's one big idea: **UI is a function of state.** You don't imperatively
"find the button and change its label" — you declare *given this state, the
screen looks like this*, and when state changes, React recomputes and
patches the real page.

- A **component** is a function returning JSX (HTML-looking syntax inside
  JavaScript). Pages live in [frontend/src/pages/](../frontend/src/pages/),
  reusable pieces in [components/](../frontend/src/components/).
- **State** is per-component memory: `const [email, setEmail] = useState("")`.
- **Props** are arguments passed into components
  (`<ConfirmDialog open={...} onConfirm={...}>`).

💡 A component is a **spreadsheet cell with a formula**: you never paint the
cell by hand; you change an input and the formula recomputes it.

### 5.2 What actually happens when state changes (the render loop)

This is the part most React users can't explain. When you call a setter
(`setEmail("x")`, or `setData(...)` inside `useApi`):

1. **Schedule.** React marks the component as needing re-render. (The
   setter does *not* change your variable immediately — `email` keeps its
   old value until the next render. Classic beginner trap.)
2. **Render.** React calls your component function again, top to bottom,
   with the new state. The JSX it returns is a description of the desired
   screen — a lightweight tree of plain objects (the "virtual DOM"), not
   real page elements. Rendering is cheap *because* it's just building this
   description.
3. **Diff (reconciliation).** React compares the new tree to the previous
   one and computes the minimal set of differences.
4. **Commit.** Only those differences are applied to the real page — the
   expensive part, kept as small as possible.

💡 **Analogy — the renovation architect.** Each render, you hand the
contractor a complete new blueprint of the whole house. The contractor
(React) compares it with the current house and repaints *one wall* — they
don't demolish and rebuild. You get to *think* in whole-blueprints
(simple!) while the work stays minimal (fast!).

Watch it concretely in the Interlude's step 16: `setData` → `EventDetail`
re-runs → the diff finds a changed button class and a changed count → two
DOM patches, nothing else.

Two practical consequences you'll see in this codebase:

- **Re-running the function must be safe and side-effect-free** — which is
  why anything that *does* something (fetching, subscribing, geolocation)
  lives in `useEffect`, never in the function body. That's next.
- **`key` props on lists** (every `.map(...)` in the pages has one) tell
  the differ which items are *the same item* across renders, so it moves
  rows instead of rebuilding them.

### 5.3 `useEffect`: side effects, and the dependency array (where beginners get hurt)

A component function should just *compute JSX*. But real pages must do
things: fetch data, ask for geolocation, register a callback. `useEffect`
is the escape hatch: "after you've rendered, run this code."

```js
useEffect(() => {
  /* the effect */
  return () => { /* optional cleanup */ };
}, [deps]);
```

The **dependency array** is the part to actually understand, not memorize:
it lists every value the effect *reads* that could change. React re-runs
the effect **only when one of those values changed since the last render**.

- `[]` — depends on nothing → runs once, after the first render ("on
  mount"). Real example:
  [auth/AuthContext.jsx](../frontend/src/auth/AuthContext.jsx) registers
  the global 401 handler once; [pages/MapHome.jsx](../frontend/src/pages/MapHome.jsx)
  asks for geolocation once.
- `[data]` — re-runs when `data` changes. Real example:
  [pages/Profile.jsx](../frontend/src/pages/Profile.jsx) and
  [pages/Onboarding.jsx](../frontend/src/pages/Onboarding.jsx) *seed form
  state from fetched data*: the fetch completes → `data` changes → the
  effect copies it into the editable form fields. This "server data →
  local editable copy" handoff is a pattern you'll reuse constantly.
- **Omitted entirely** — runs after *every* render. Almost never what you
  want.

The two classic injuries, and where this repo stands on them:

- **The infinite loop**: an effect that *sets state it also depends on*
  re-triggers itself forever. (Set `data` → `data` changed → effect runs →
  sets `data` → …) The cure is making the dependency the thing that should
  *cause* the work, not the thing the work produces — note how the
  Profile effect *reads* `data` but *sets* `form`.
- **The stale closure**: an effect (or callback) "remembers" the state
  values from the render it was created in. If you lie in the dependency
  array, it keeps using stale values. The lint rule
  (`react-hooks/exhaustive-deps`) exists to catch this — and where this
  codebase deliberately deviates, it says so out loud: `useApi`
  ([hooks/useApi.js](../frontend/src/hooks/useApi.js)) passes the *caller's*
  deps to `useCallback` and disables the rule with a comment, because the
  hook can't statically know what the caller's loader reads. That's an
  informed exception, not a habit — copy the honesty (the comment), not
  the disable.

While you're in `useApi`, understand `useCallback`: functions are re-created
on every render, so anything comparing them by identity (like a dependency
array) would see "changed!" each time. `useCallback` returns the *same*
function object until its own deps change — that's what lets `useApi`'s
effect re-run only when the page's deps (like the event `id` from the URL)
actually change, instead of on every render.

### 5.4 The three state layers (interviewable)

This app manages state at three distinct levels — being able to name them
is a differentiator:

1. **Local UI state** — one component's memory: form fields, "is this modal
   open," "is the request in flight." `useState` in the page. Look at how
   every *form* submit button disables itself via a `submitting` flag —
   local state preventing double-submits. (The RSVP buttons don't — see
   the Interlude's honest gap, and Exercise 6.)
2. **Global app state** — exactly one thing is global here: *who is logged
   in*. [auth/AuthContext.jsx](../frontend/src/auth/AuthContext.jsx) uses
   React **Context** to make `user`, `login`, `logout` available to any
   component without passing props down ten levels. On page load it calls
   `GET /api/users/me` — "cookie, who am I?" — and holds a `loading` flag
   so a hard refresh doesn't flash the login screen at someone who is
   actually logged in.
3. **Server state** — data whose true owner is the backend: events,
   messages, connections. The pattern is deliberately simple: fetch fresh
   per page via `useApi`, and after any mutation, `reload()`. No cache, no
   Redux. Why — and what it costs — is a Module 7 entry.

The `useApi` hook is the repo's best example of extracting a repeated
pattern: every page needs the same four-state dance —
**loading → error → empty → data** — so the hook packages it once, and
every page renders those states the same way. Consistency itself is a
feature; users learn one loading pattern, and so do future devs.

### 5.5 The single network funnel

[src/api/client.js](../frontend/src/api/client.js) is the **only** file
that calls `fetch`. Three policies live there once instead of in every page:

- JSON encoding/decoding, plus multipart for uploads (`api.upload`).
- **CSRF header injection** — reads the `ours_csrf` cookie and attaches
  `X-CSRF-Token` to every mutating request. Pages don't know CSRF exists.
- **Error normalization** — non-2xx becomes a typed `ApiError` with the
  backend's `message`; **any 401 anywhere** triggers a registered callback
  that clears the auth context, and `ProtectedRoute`
  ([components/ProtectedRoute.jsx](../frontend/src/components/ProtectedRoute.jsx))
  redirects to login. Expired session → clean bounce, from one place.

💡 One doorway into the building means one security checkpoint. If auth or
error policy changes, one file changes.

Trace the 401 path end-to-end once: `request()` sees 401 → calls
`onUnauthorized()` → which is the callback `AuthContext` registered via
`setUnauthorizedHandler` → `setUser(null)` → every component reading the
context re-renders → `ProtectedRoute` sees `user == null` → `<Navigate
to="/login">`. Four files, one policy, zero duplication.

### 5.6 Routing: pages without page loads

[App.jsx](../frontend/src/App.jsx) maps URLs to components with
react-router: `/login` public; everything else nested inside
`<ProtectedRoute><Layout/></ProtectedRoute>` — the auth gate and shared
navigation wrap all private pages at once, and each page renders into
`Layout`'s `<Outlet/>`. Dynamic segments like `/events/:id` are read with
`useParams()` in [pages/EventDetail.jsx](../frontend/src/pages/EventDetail.jsx)
— and note how that `id` then appears in `useApi`'s dependency array, so
navigating from one event to another re-fetches automatically. That's the
hooks system composing: router state → dependency array → effect → fetch.

### 5.7 The map

[components/MapView.jsx](../frontend/src/components/MapView.jsx) wraps
**Leaflet** (the map engine) via react-leaflet, drawing OpenStreetMap tiles
(free, no API key). Study three practical techniques:

- **CSS-drawn markers** (`divIcon`) instead of image icons — dodging
  Leaflet's infamous broken-icon-under-bundlers problem and making the
  green/amber event pins trivially styleable.
- **The escape hatch**: `MapBridge` uses react-leaflet hooks to lift the
  raw Leaflet map object up to the page — needed because "search this area"
  must ask the map for its current bounds. (Declarative wrappers around
  imperative libraries always need one of these; recognize the shape.)
- **Viewport-driven radius** ([pages/MapHome.jsx](../frontend/src/pages/MapHome.jsx)):
  the search radius is computed as center-to-corner distance of the visible
  map, so the query matches what the user actually sees. Geolocation falls
  back to a default neighborhood if denied — the map must never be broken.

### 5.8 Forms, modals, uploads

- Forms are **controlled components** (input value ↔ state), submitted via
  the shared client with a `submitting` flag and inline error display —
  the same skeleton everywhere; learn it once in
  [pages/CreateEvent.jsx](../frontend/src/pages/CreateEvent.jsx) (which also
  shows a click-to-place map picker and datetime → UTC ISO conversion).
- Destructive confirmations use in-app modals
  ([components/dialogs.jsx](../frontend/src/components/dialogs.jsx)) rather
  than the browser's `confirm()` — stylable, testable, and able to carry a
  real explanation ("this deletes RSVPs and messages; use Cancel to keep
  the record").
- Avatar upload ([pages/Profile.jsx](../frontend/src/pages/Profile.jsx))
  sends `FormData` via `api.upload`; the backend stores the file under
  `/media/avatars/` and the profile's `avatar_key` points at it.

**✍️ Explain it yourself**

1. Walk through the four phases of a re-render using the Interlude's step
   16 as your example. Why is "re-run the whole function" not wasteful?
2. What does a `useEffect` dependency array actually control? Explain the
   infinite-loop injury and the stale-closure injury, and how the
   Profile-page effect avoids the first.
3. Name the three state layers and give one example of each from this repo.
   Why is there no Redux/cache library?
4. Trace what happens in the UI when a session expires mid-use: which file
   notices, what state changes, which component redirects?
5. Why does `client.js` exist instead of pages calling `fetch` directly?
   Name two policies that would otherwise be duplicated.

---

## Module 6 — Testing: How We Know It Works (and what we don't)

**🎯 By the end you should be able to:** explain both test layers and what
each can catch · describe how the pytest suite isolates itself · state what
is *not* tested here and the risk that carries.

Two layers, deliberately different:

### 6.1 The smoke test — honest end-to-end

[backend/scripts/smoke_test.sh](../backend/scripts/smoke_test.sh) is ~55
`curl` checks against a **really running server**: registers Dylan and
Eleanor, creates events in Sunset Park, verifies the private dinner is
invisible until an invite exists, fills an event to capacity and expects
409, blocks Bob and confirms Eleanor's events vanish from his map, checks
that a request missing its CSRF header gets 403, and that a stolen cookie
dies at logout. It's coarse — but it exercises the *real* stack, cookies
and middleware included, exactly like a browser would.

### 6.2 The pytest suite — precise and isolated

[backend/tests/](../backend/tests/) holds 24 tests. The engineering is in
[conftest.py](../backend/tests/conftest.py):

- **A disposable database.** Environment variables are set *before the app
  is imported*, pointing it at `ours_test`; a session fixture drops and
  recreates that database each run and builds the schema straight from the
  models. Tests can never touch dev data.
- **In-process requests.** httpx's `ASGITransport` calls the FastAPI app
  directly — no server process, no port — yet middleware, DI, cookies all
  run for real.
- **Isolation between tests**: an autouse fixture truncates tables after
  each test. Every test starts from zero and can't contaminate the next.
- **The `make_user` factory** — registers + logs in a user and returns a
  client already carrying its auth cookie and CSRF header. Tests then read
  like user stories:

```python
eleanor = await make_user("eleanor@example.com", "Eleanor")
bob     = await make_user("bob@example.com", "Bob")
await eleanor.post("/api/blocks", json={"blocked_id": bob_id})
assert (await bob.get(NEARBY)).json() == []       # blocked → map is empty
```

Note *what* is tested: **behavior through the public API**, not internal
functions. That's why the suite survived refactors during development — the
handlers changed, the contracts didn't, the tests stayed green. Tests
pinned to internals break on every refactor and teach you to fear change;
tests pinned to behavior *enable* change.

### 6.3 What is NOT tested — read this as a risk register

Honesty about coverage is itself an engineering lesson. Known holes, and
what each one risks:

- **The frontend has zero automated tests.** `npm run build` proves the
  code *parses*, not that it *works*. The CSRF header injection, the 401
  redirect chain, the form validation — all verified only by humans
  clicking. Risk: a refactor of `client.js` or `AuthContext` could silently
  break every mutation, and no robot would object.
- **Concurrency is untested — and there is a real race.** The capacity
  check in `set_rsvp` is *check-then-insert* with no row locking: two
  requests arriving in the same instant can both count 1-of-2 seats taken
  and both insert. Tests run sequentially, so they can never catch it. At
  neighborhood scale this is theoretical; at ticket-sale scale it's the
  bug. (Fix would be a DB-level lock or constraint; knowing *that it's
  there and unpriced* is the discipline.)
- **Migrations aren't exercised by pytest.** The suite builds the test
  schema from the models (`create_all`), not by replaying the migration
  chain. If a migration drifted from the models, tests would stay green
  and only the smoke test / a fresh deploy would notice.
- **The admin panel and media uploads** have no automated coverage.
- **Load and latency** — nothing measures how the map query behaves with
  100k events.

The meta-lesson: every test suite has a boundary, and teams get hurt by the
boundary they *haven't written down*, not the one they have.

**✍️ Explain it yourself**

1. What can the smoke test catch that the pytest suite can't, and vice
   versa?
2. How does the pytest suite guarantee it can't damage development data?
   (Two mechanisms.)
3. Explain the RSVP capacity race to a teammate: why do tests miss it, when
   would it matter, and what would a fix look like?
4. Why is "test through the public API" a refactoring superpower?

---

## Module 7 — The Design Decisions (what we chose, what it cost)

**🎯 By the end you should be able to:** state each decision as *chose /
rejected / because / at the cost of* — and argue the other side.

This module is the guide's spine. Every codebase is a pile of decisions;
most teams lose the reasoning within months. Here are the eight
highest-leverage calls in this repo, each with its price tag — because a
decision explained without its cost is advertising, not engineering.
(The full running log, including calls that were later *reversed*, is in
[DECISIONS.md](DECISIONS.md) — read it beside this.)

### D1. One `events` table for gatherings AND help requests

- **Chose:** a single table with a `kind` column.
- **Rejected:** separate `gatherings` and `help_requests` tables.
- **Because:** they behave identically — location, time, visibility,
  RSVPs, messages, capacity. Two tables would duplicate every column,
  every migration, every query, and every permission rule; the map endpoint
  would need a UNION.
- **Cost:** columns that only make sense for one kind (e.g. `capacity` on
  a help request) exist on both, unenforced. If the two kinds ever *diverge*
  behaviorally (help requests get "fulfilled by", gatherings get ticketing),
  the shared table becomes a squeeze. The bet: they won't diverge soon.

### D2. UUID primary keys, not auto-incrementing integers

- **Chose:** `UUID DEFAULT gen_random_uuid()` everywhere.
- **Rejected:** `SERIAL` integers.
- **Because:** IDs travel in shareable URLs. Sequential IDs are guessable —
  `/events/1`, `/events/2`, … — enabling enumeration of the whole table and
  leaking volume ("this app has 300 users"). UUIDs are unguessable.
- **Cost:** 16 bytes vs 4, no natural sort order (we order by real columns
  like `created_at` instead), and uglier debugging ("event 7b7c65af…" vs
  "event 12").

### D3. Database-backed sessions, not JWTs (a reversal!)

- **Chose:** opaque random tokens stored in `access_tokens`; the cookie is
  a coat-check ticket.
- **Rejected:** JWTs — *after initially shipping them.* This is the repo's
  most instructive decision because it was changed with reasons.
- **Because:** JWTs cannot be revoked before expiry; "logout" was a polite
  fiction. A stolen token stayed valid for 24 hours. With DB sessions,
  logout deletes the row — provably (there's a test).
- **Cost:** one indexed SELECT per authenticated request, and a table of
  expired rows that needs periodic sweeping (still an open ops task). At
  massive scale you'd revisit (or add a cache); at this scale, correctness
  wins.

### D4. Monolith, not microservices

- **Chose:** one FastAPI process owning API + media + admin.
- **Rejected:** services split by domain (auth service, events service…).
- **Because:** microservices trade *code* complexity for *operational*
  complexity (deployment, network failures, distributed transactions,
  tracing). That trade pays off for many teams working independently — not
  for one small team building an MVP. A modular monolith (routers by
  domain) preserves the seams to split *later, if ever*.
- **Cost:** everything scales together (can't give just the map query more
  machines), one bad deploy takes down everything, and the discipline of
  module boundaries rests on convention, not network walls.

### D5. Business logic in routers + shared `deps.py`, no service layer

- **Chose:** handlers own their logic; shared rules promoted to
  [routers/deps.py](../backend/app/routers/deps.py).
- **Rejected:** a `services/` layer between routers and models, from day one.
- **Because:** a layer must earn its existence. With one caller per rule, a
  service layer is indirection without abstraction — every read of the code
  requires one more hop. `deps.py` captures the genuinely shared rules
  (visibility, blocks, the status machine) without ceremony.
- **Cost:** handlers like `set_rsvp` mix HTTP concerns (status codes) with
  domain rules (capacity). Logic is harder to reuse outside HTTP (a future
  CLI or background job would have to call the API or duplicate rules).
  The *pressure* to extract grows with the app — this is a decision to
  revisit, on purpose, later.

### D6. Re-fetch after every mutation, no client cache or state library

- **Chose:** `useApi` per page + `reload()` after mutations; global state
  is the logged-in user, nothing else.
- **Rejected:** Redux / React Query / SWR-style caching.
- **Because:** cache invalidation is famously the hard problem. Re-fetching
  is *always correct*, trivially understandable, and at neighborhood scale
  the extra requests are noise. Correct-and-boring beat clever.
- **Cost:** more round-trips, brief loading flashes after actions (watch
  the whole detail page re-load after an RSVP), no optimistic UI, and no
  cross-page sharing (two components needing the same data fetch it twice).
  The moment UX polish demands optimistic updates, this decision gets
  revisited — knowingly.

### D7. Messaging exists only inside events

- **Chose:** `event_messages` with a mandatory `event_id`; no DM table.
- **Rejected:** direct user-to-user messages.
- **Because:** this is the *product* encoded as schema. The app's mission
  is getting people into rooms, not hosting conversations; open DMs are
  also a harassment surface the team would then have to moderate.
- **Cost:** real user friction — "I just want to ask Eleanor something"
  requires an event as pretext. If users demand DMs, this becomes a
  deliberate product fight, not a quick schema change. That's intentional:
  some decisions *should* be hard to reverse casually.

### D8. Hard-delete accounts; hosted events survive with `host_id = NULL`

- **Chose:** `DELETE /api/users/me` cascades personal data away for real;
  `events.host_id` is `ON DELETE SET NULL`.
- **Rejected:** soft delete (`deleted_at` flags) — and also cascading
  event deletion.
- **Because:** privacy honesty ("delete my account" should mean it) plus
  not vandalizing other people's plans: attendees already RSVP'd to that
  block party. The pair of FK rules encodes both values at once.
- **Cost:** no "undo" for account deletion, no tombstone for moderation
  history (a banned user's data vanishes too — reports referencing them
  cascade away), and "orphaned" events with no host need UI care.

**✍️ Explain it yourself**

1. Pick any two decisions and argue the *rejected* side as persuasively as
   you can. (If you can't make the rejected option sound reasonable, you
   don't understand the decision yet.)
2. Which of the eight is most likely to be reversed as the app grows, and
   what event would trigger the reversal?
3. D3 was a real reversal. What does the fact that it *shipped both ways*
   teach about how decisions should be recorded?

---

## Module 8 — Vocabulary & Patterns (own these words)

**🎯 By the end you should be able to:** define each term below in one
sentence *and* point to where it lives in this repo.

Plain-language definitions, each anchored to this repo. These are the terms
that make you sound — and be — fluent.

| Term | In plain words | In this repo |
|---|---|---|
| **Dependency Injection** | Don't fetch your tools; declare them as parameters and let the framework hand them in. | `Depends(get_db)`, `CurrentUser` — everywhere; diagram in §3.5 |
| **Generator dependency** | A DI provider using `yield`: before = setup, after = guaranteed cleanup. | `get_db` in [core/database.py](../backend/app/core/database.py) |
| **Strategy pattern** | Behavior slots you can swap without touching the callers. | fastapi-users auth = transport (how credentials travel) × strategy (how tokens verify); we swapped Bearer→Cookie and JWT→DB with zero endpoint changes |
| **Repository / adapter** | Wrap data access behind an interface so libraries don't touch your tables directly. | `SQLAlchemyUserDatabase` in [core/auth.py](../backend/app/core/auth.py) |
| **Factory** | A function that manufactures configured objects. | `async_sessionmaker`; `make_user` in tests |
| **Singleton (module-level)** | Created once at import, shared everywhere — the Pythonic way. | `engine`, `settings`, `app` |
| **Middleware** | Code every request passes through before/after routing. | CORS + CSRF in [main.py](../backend/app/main.py) |
| **State machine** | Legal state transitions as data; everything else rejected. | `ALLOWED_STATUS_TRANSITIONS` in [routers/deps.py](../backend/app/routers/deps.py) — cancelled/completed are terminal, violations 409 |
| **Facade** | A simple face over a messy machine. | `client.js` over fetch; `useApi` over the loading/error dance |
| **Schema/model separation** ("three shapes") | DB shape ≠ API shape ≠ HTTP layer; the gaps are where security lives. | `models/` vs `schemas/` vs `routers/` |
| **Defense in depth** | Enforce the same rule at multiple layers. | visibility in SQL *and* per-object; validation in Pydantic *and* DB constraints |
| **Idempotent** | Safe to repeat with the same result. | `PUT /rsvp` (sets your status) vs `POST /invites` (repeating → 409) |
| **Connection pool** | Keep expensive connections warm and lend them out. | the engine |
| **Transaction** | All-or-nothing group of writes. | event + interest tags in `create_event` |
| **Race condition** | Two concurrent operations interleave into a state neither intended. | the *known, accepted* RSVP capacity race (§6.3) |
| **Reconciliation / diffing** | Compare desired UI tree to current, apply minimal patches. | React's render loop (§5.2) |
| **CORS** | Browser rules about which origins may call which servers. | middleware + Vite proxy sidestep in dev |
| **Environment config** | Secrets/config live outside code, per machine. | `.env` + [core/config.py](../backend/app/core/config.py); `.env.example` as the committed template |

Also worth naming as *practices* rather than patterns: **migrations
reviewed like code** (§2.6), **decision logs with costs and reversals**
(Module 7 + [DECISIONS.md](DECISIONS.md)), **one error shape** across the
whole API, and **small, verifiable increments** — the git history of this
repo is itself a study document; read it oldest-first with
`git log --oneline --reverse`.

---

## Module 9 — Exercises (proof of understanding)

**Tier 1 — Read and narrate** (no code changes)

1. The Interlude traced the RSVP. Now do your own trace, unaided, for
   `POST /api/events/{id}/invites` — which has *more* rejection paths
   (connection required, blocks, duplicates, inviter must be tied to the
   event). List every status code and the exact line that decides it.
2. Read `alembic/versions/` oldest-first and narrate the schema's history
   like a story: what arrived when, and why.
3. With the backend running, use only `/docs` (no frontend) to: register,
   log in, create an event, RSVP to it. (Hint: you'll collide with CSRF —
   understanding *why*, and what the browser normally does for you, is the
   exercise.)

**Tier 2 — Small extensions**

4. Add `GET /api/users/me/events` — events I host or am going to. Touches:
   one router function, one schema, one test. No model changes.
5. Make the sidebar's "Nearby" list show the host's display name. You'll
   need a join — study how `list_participants` joins Profile.

**Tier 3 — Full-stack features**

6. Fix the Interlude's honest gap: disable the RSVP buttons while a request
   is in flight (mirror the `submitting` pattern from the forms). Frontend
   only — and notice how the fix's *shape* was already in the codebase.
7. Add `last_seen_at` to users: model change → autogenerate → **review the
   migration** → apply → update it on each authenticated request.
8. Wire rate limiting on `/api/auth/login` (the one stack item still
   unwired — this repo's known gap) and write a test proving the 6th rapid
   attempt gets 429.

**Tier 4 — Judgment**

9. Extract the RSVP/capacity logic into a `services/participation.py` and
   watch the tests stay green — experience "behavioral tests enable
   refactoring" firsthand. Then write three sentences arguing whether the
   extraction was worth it *at this size* (Module 7, D5, has the standing
   position — disagree with it if you can).
10. Fix the capacity race from §6.3 (hint: `SELECT ... FOR UPDATE` on the
    event row, or a trigger-enforced constraint). Then explain why writing
    a *test* for it is genuinely hard.
11. Read every "deviation" and "revision" in [DECISIONS.md](DECISIONS.md)
    and argue *against* one of them. If you can steelman both sides, you
    understand the trade-off.

**The final exam** is a conversation: explain this system to someone —
restaurant analogy to a non-engineer, the Interlude's sixteen steps to a
junior dev, D3's JWT-vs-database-sessions reversal to an interviewer. When
you can shift altitude on demand, this codebase is yours.
