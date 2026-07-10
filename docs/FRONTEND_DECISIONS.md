# Decision log — frontend MVP build

Judgment calls made while building the React frontend in one pass
(2026-07-10). Items marked **⚠ gap** are places the backend API doesn't yet
expose something the UI ideally wants; I worked around them and noted each.

## Architecture

1. **Manual Vite scaffold** rather than `npm create vite`. Fewer surprise
   files, and every file in the tree is one we wrote and understand.
2. **Plain global CSS**, one `styles.css`, no CSS Modules. Per the "wireframe,
   styling is not the priority" brief — a single sheet is the least machinery
   that works. Easy to split into Modules later if it grows.
3. **Native Fetch, wrapped once** in `src/api/client.js`. Everything goes
   through `api.get/post/put/patch/del`, so token handling, JSON encoding, and
   error shaping live in exactly one place. No axios, no React Query — the app
   is small enough that a `useApi` hook covers the data-fetching needs.
4. **`useApi` hook** (`src/hooks/useApi.js`) standardizes the loading / error /
   data triad every screen needs, plus a `reload()` for post-mutation refresh.
   This is the frontend echo of the backend's repeating router pattern.

## Auth & session

5. **JWT stored in `localStorage`** under `ours.token`. Simple and survives
   refresh. Trade-off: localStorage is readable by any script on the page, so
   it's vulnerable to XSS. The more secure option (an httpOnly cookie) needs
   backend cooperation and doesn't fit the current bearer-token contract —
   noted for the pre-production security pass.
6. **A single 401 handler** in the client fires a callback that the auth
   context uses to drop the token and force a re-login. Any expired token
   anywhere in the app funnels through it.
7. **`AuthProvider` verifies the token on first mount** by calling
   `/api/users/me`, and holds a `loading` flag so protected routes don't flash
   the login screen on a hard refresh.
8. **Register auto-logs-in then routes to `/onboarding`.** One smooth first
   run instead of making a new user log in a second time.

## Routing

9. **`react-router-dom` v6**, all authenticated pages nested under one
   `<ProtectedRoute><Layout/></ProtectedRoute>` so the gate and the nav shell
   are declared once. `/login` and `/register` sit outside it.
10. **Protected routes remember where you were headed** (`state.from`) and
    return you there after login.

## The map (the one genuinely new piece)

11. **Leaflet + react-leaflet v4**, OpenStreetMap tiles — matches the stack and
    needs no API key.
12. **`divIcon` markers** (CSS-styled colored dots) instead of image pins. This
    sidesteps the well-known broken-marker-image problem with Leaflet under
    bundlers, and suits the wireframe look. Green = gathering, amber = help.
13. **"Search this area" button** rather than auto-refetching on every map
    move. Explicit, avoids hammering the API while panning, and makes the
    radius logic obvious: radius = center→corner distance of the current view.
14. **Geolocation with a Brooklyn fallback.** We wait for the browser's
    location (5s timeout) before first render so the map opens in the right
    place; denial silently falls back so the app never dead-ends on a
    permission prompt.
15. **A list mirrors the map** in the sidebar — better for scanning, keyboard
    use, and the empty state, and it gives distance readouts.

## Screens & UX

16. **Location is set by clicking a mini-map** in the create form
    (`LocationPicker`), not by typing coordinates — the natural gesture for a
    map-first app, and it guarantees a valid point.
17. **`datetime-local` inputs are converted to UTC ISO** (`toISOString()`)
    before sending, matching the timezone-aware backend.
18. **Native `confirm()` / `prompt()`** for delete confirmation, report
    reasons, and block confirmation. Not pretty, but honest MVP scaffolding; a
    real modal component is a later polish pass.
19. **The host doesn't see RSVP buttons** (they own the event); they see
    Cancel / Delete instead. RSVP state is reflected by highlighting the
    active choice.
20. **Messages and the invite panel only render for participants/host**,
    mirroring the backend's 403 rules so the user never sees a control that
    would just fail.

## Gaps worked around (worth discussing)

21. **⚠ No "get my interests" endpoint.** The API has `PUT
    /api/profiles/me/interests` but no GET, so the profile page can't pre-check
    the user's current interests. Interest editing is therefore routed through
    "redo the quick setup" (onboarding), which sets a fresh list. A
    `GET /api/profiles/me/interests` would let us build true inline editing.
22. **⚠ No user search / directory.** You can only send a connection request
    from someone's profile page, which you reach from an event's participant
    list. There's no "find people by name" because the API has no search
    endpoint. Fine for the in-person-first ethos, but worth a decision.
23. **⚠ Connection requests return only IDs**, so the Connections page fetches
    each requester's profile by id to show a name (N small extra requests). A
    request list that included display names would remove this.
24. **`show_attending` isn't consumed yet** — there's no endpoint to view a
    connection's attended events, so the preference is captured but not acted
    on. Backend feature to add later.

## Revisions — 2026-07-10 (post-review, user-directed)

- **#5 resolved:** JWT no longer touches JavaScript. Auth rides in an
  httpOnly cookie; `client.js` has zero token code and the browser attaches
  the cookie itself. Any lingering `ours.token` in localStorage is ignored.
- **#21 resolved:** onboarding now pre-fills the user's current interests,
  community, and preference flags via `GET /api/profiles/me/interests` +
  `GET /api/profiles/me` — it doubles as a real "edit preferences" screen.
- **#22 resolved:** the Connections page has a "Find people" search backed by
  `GET /api/profiles?q=`, with inline Connect buttons.
- **#24 stands:** `show_attending` stays captured-but-unused, per review.

## Not done (deferred)

- No automated frontend tests (build passes; flows verified manually through
  the Vite proxy).
- No image uploads — `avatar_key` is a free-text field (emoji/label) for now.
- No optimistic UI; every mutation waits for the server then reloads.
- No pagination controls (backend caps the map query at 200).
