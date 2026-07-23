# Ours

**Ours** is a web application that helps people in a local community turn everyday acts of
helping and hosting into real relationships — and helps the natural leaders
already living there begin to see themselves that way.

Everything is centered on an interactive map of the user's own neighborhood,
where residents can create local events, ask neighbors for help with tasks,
and follow community organizations.

## Why this is different

Most apps that claim to "build community" make money by keeping you on a
screen, so they can never truly want you to use them less. **Our job is to get
people into a room together.** We measure success by the time people spend
with one another in real life, not by the time they spend in the app.

To keep the app about getting together rather than chatting online,
interaction is intentionally limited:

- People connect and invite each other to real-world events.
- All messaging stays attached to a specific event or invite — there is
  deliberately no open, free-floating chat.
- The platform is non-partisan and apolitical: neighbors helping neighbors.

If we succeed, people need the app less and less over time. That's the point.

## Core features (MVP)

- **Account & profile** — register/log in, optional onboarding preferences,
  and a simple profile (name, photo, bio, interests).
- **The map** — the landing page is a map of your area showing nearby events
  and help requests, filtered by your preferences.
- **Events & help requests** — create a community gathering or ask neighbors
  for a hand; both appear on the map and neighbors can RSVP or offer to help.
- **Visibility controls** — events can be public, community-only, or private
  invite-only.
- **Connections** — mutually-approved connections with people you've met, so
  inviting them again is easy; see what your connections are hosting or
  attending (if they've chosen to share it).
- **Event-scoped messaging** — coordinate within an event or invite, nothing
  more.
- **Safety** — decline requests, block users, and report bad behavior.

Planned stretch features include verified organization accounts, a low-noise
notice board, and an AI layer that guides event creation and surfaces
relevant local happenings.

## Tech stack

| Layer     | Choices |
|-----------|---------|
| Backend   | Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy 2.0 (async) + asyncpg, GeoAlchemy2, Alembic, fastapi-users, SQLAdmin |
| Database  | PostgreSQL + PostGIS (geospatial queries for "what's near me") |
| Frontend  | React (JavaScript) SPA built with Vite, plain CSS / CSS Modules, native Fetch API |
| Map       | Leaflet + OpenStreetMap |
| Auth      | JWT bearer tokens |

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── main.py      # FastAPI application entry point
│   │   ├── core/        # Config, database session, security
│   │   ├── models/      # SQLAlchemy models (database tables)
│   │   ├── schemas/     # Pydantic schemas (API request/response shapes)
│   │   ├── routers/     # API endpoints grouped by resource
│   │   └── services/    # Business logic
│   ├── alembic/         # Database migrations
│   └── tests/
└── frontend/            # React + Vite single-page app
```

## Getting started (development)

**Prerequisites**

- Python 3.12+
- [Postgres.app](https://postgresapp.com/) (macOS) or PostgreSQL 16+ with the
  PostGIS extension
- Node.js 20+ (for the frontend)

**Status:** the project is being rebuilt incrementally from the ground up;
setup instructions for each part are added here as that part lands.

## Roadmap

- [x] Database setup (PostgreSQL + PostGIS)
- [x] Backend skeleton (FastAPI app, config, health check)
- [x] Async SQLAlchemy + Alembic migrations
- [x] Users & JWT authentication (fastapi-users)
- [x] Profiles, communities, interests
- [x] Events & help requests with geospatial "near me" queries
- [x] Participation: RSVPs and invites
- [x] Connections, blocks, reports
- [x] Event-scoped messaging
- [x] Frontend: auth, map, event creation & discovery
- [x] Backend hardening: pytest suite, SQLAdmin, revocable sessions, CSRF,
      block-aware visibility, avatar uploads, pagination
- [ ] Rate limiting; frontend automated tests; object storage for uploads

Design decisions made along the way are logged in
[docs/DECISIONS.md](docs/DECISIONS.md) (backend) and
[docs/FRONTEND_DECISIONS.md](docs/FRONTEND_DECISIONS.md) (frontend).

## Running it locally

Two terminals, from the repo root:

```bash
# 1. Backend (needs Postgres.app running with the ours_dev database)
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000

# 2. Frontend
cd frontend
npm install     # first time only
npm run dev     # serves http://localhost:5173, proxies /api to :8000
```

Open http://localhost:5173 and register an account.

**Admin panel:** register an account in the app, promote it with
`cd backend && .venv/bin/python scripts/make_admin.py you@example.com`,
then log in at http://localhost:8000/admin.

**Tests:** `cd backend && .venv/bin/pytest` (creates and uses a disposable
`ours_test` database). The curl smoke test is
`backend/scripts/smoke_test.sh` — reset dev data first as noted in its header.

## Deploy to Render

The repo ships a [`Dockerfile`](Dockerfile) (builds the React SPA, then runs the
API which serves that build from the **same origin** — so the auth cookie +
CSRF flow needs no cross-site setup) and a [`render.yaml`](render.yaml)
blueprint (one web service + one managed Postgres).

1. Push this repo to GitHub.
2. In Render: **New + → Blueprint**, pick the repo. It reads `render.yaml` and
   creates the `ours` web service and the `ours-db` Postgres.
3. Render sets `DATABASE_URL` (rewritten to the async driver in
   [config.py](backend/app/core/config.py)) and generates `SECRET_KEY`;
   `COOKIE_SECURE` is `true`. Set `TICKETMASTER_API_KEY` only if you want
   real-world event import.
4. First deploy runs `alembic upgrade head`, which **enables PostGIS** (baseline
   migration) and builds the schema. When it's live, open the service URL and
   register an account.

Notes:
- Render's managed Postgres supports PostGIS; the migration turns it on
  automatically, so no manual `CREATE EXTENSION` step.
- Uploaded avatars are written to the container's local disk, which is
  **ephemeral** on Render — they're lost on redeploy. Wire up object storage
  (S3) before relying on them (see the roadmap).
- Any Docker host works the same way: build the image and run it with
  `DATABASE_URL`, `SECRET_KEY` and `COOKIE_SECURE=true` set.
