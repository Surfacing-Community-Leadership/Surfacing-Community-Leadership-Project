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

## Revisions — 2026-07-10, round two

- **CSRF handled invisibly in `client.js`**: every mutating request reads the
  `ours_csrf` cookie and echoes it as `X-CSRF-Token`. Pages never think about
  it.
- **Native `confirm()`/`prompt()` replaced** with in-app `ConfirmDialog` /
  `ReportDialog` components (`components/dialogs.jsx`) — used for event
  delete, block, and both report flows.
- **Avatar upload UI** on the profile page (file input → multipart POST via
  `api.upload`); `avatarUrl()` in `client.js` resolves uploaded keys to
  `/media/...` URLs, falling back to emoji/text for legacy values.

## Revisions — 2026-07-28 (the notice board)

- **`Create` moved from the nav rail to a floating button** (`.fab` in
  `styles.css`, `CreateButton` in `Layout.jsx`), freeing the fifth tab for
  `Board`. Six tabs don't fit a phone-width bar, and creating is an action
  rather than a destination. The button hides itself on `/events/new`,
  `/onboarding` and any `…/edit` route, shrinks to a circle on mobile, and
  lifts above the map's list sheet via `.fab-map` — verified by measuring the
  two rects rather than eyeballing it.
- **The board is styled deliberately quieter than the event cards.** A 4px
  category-coloured left rule instead of a coloured background, bodies clamped
  to three lines so a wordy notice can't shout down a short one, and no counts
  or ranking. Giveaways and offers lean sage (something is available), asks and
  losses lean terracotta (someone needs a hand), org-only categories take the
  ochre volunteer work already uses.
- **The compose form tints by category**, reusing the pattern the event form
  established (`.notice-form.form-giveaway` etc. override the accent ramp).
- **`Board.jsx` renders the neighborhood picker inline** when the account has no
  `community_id`, rather than erroring or bouncing to onboarding: the board is
  scoped to a neighborhood, so there is genuinely nothing to show until one is
  chosen. `GET /api/notices/meta` reports *why* posting is unavailable and the
  UI turns that into a prompt instead of a dead button.
- **`NoticeDetail.jsx` is two screens on one route** — the author sees their
  private replies plus "mark it sorted" / "take it down"; everyone else sees a
  single reply box, a character counter, and no hint of who else replied.

## Revisions — 2026-07-29 (notice board v2)

- **The filter strip scrolls sideways rather than wrapping.** Nine post types
  plus Everything / Official / Yours stacked three rows deep on a phone.
- **`StarButton` is optimistic and calls `preventDefault`/`stopPropagation`** —
  the card is a `<Link>`, so starring from inside one would otherwise navigate.
  A failed request rolls the local count back.
- **Post of the day is excluded from the grid below it.** Caught in a screenshot:
  the highlighted notice was also being printed as a normal card, which reads as
  a bug rather than emphasis.
- **`LocationPicker` needs `center` and `onPick`.** My first pass passed
  `onChange` and no centre, so the picker rendered blank and a pin could never be
  placed — which also left the submit button permanently disabled behind
  `disabled={pinned && !location}`. Found by looking at the screenshot rather
  than trusting "the component is on the page"; now verified by clicking the map
  in the harness and asserting a marker appears and submit enables.
- **Notice pins are their own `MapView` prop and their own request**, not merged
  into `events`. They fail soft: a notices error leaves the events showing rather
  than erroring the map. They also get their own checkbox in the map panel
  instead of joining the event-kind `<select>`, since a notice is not a kind of
  event and never enters the "spots nearby" count.
- **Long-form types get `rows={10}` and a live character counter** in the compose
  form, and `clamp-2` on the board card.

## Revisions — 2026-07-29, round two (Community board)

- **`.notice-card` no longer composes with `.card`.** Dropping the grid meant the
  card had to stand on its own — it now sets its own surface, padding and radius
  rather than inheriting a tile's.
- **`.board-list` is a flex column**, and the heading scales with `clamp()` now
  that a card has the full column width to play with.
- **The nav label stays "Board"** even though the page is "Community board" —
  five characters is what fits a phone tab bar, and the icon carries the rest.
- **`.potd-foot` wraps.** Its caption ran to the right edge at 390px; caught in a
  screenshot, not by the overflow measurement, which stayed at 0 because the text
  was clipping inside its container rather than widening the document.

## Revisions — 2026-07-29, round three (paging + address pins)

- **`PAGE_SIZE = 6`, and the page resets to 0 on a tab change** — page 4 of Posts
  is not page 4 of Organizations. `hasNext` comes from fetching one extra row, so
  there's no count query and the pager never shows a dead "Older" button.
- **`addressPoint` is tracked separately from `location`.** A picked address's
  coordinates have to survive the author *not* having ticked the pin box yet, so
  ticking it later can still use them. Typing over the address clears them,
  because they no longer describe what's in the field.
- **Driving `AddressAutocomplete` in the test harness needs the native value
  setter.** A plain `input.value = "..."` doesn't fire React's `onChange`, so the
  debounce never runs and no suggestion ever appears. Worth recording because it
  looked exactly like a broken component the first time.
- Nominatim needs **~5 seconds**, not 2, before suggestions land in a headless
  run. My first attempt reported "no suggestions" purely because I didn't wait
  long enough — the component was fine.

## Revisions — 2026-07-29, round four (editing)

- **The compose form was extracted to `components/NoticeForm.jsx`** and is now
  shared by writing and editing. Nine fields, a geocoder and a map picker copied
  into a second component would have drifted within a week, and the edit form
  would quietly miss whatever the create form gained next.
- **`existing` is the only mode switch.** Passing a post fills the fields and
  changes exactly two behaviours: the heading/button wording, and expiry
  defaulting to "leave as it is" instead of the standard window.
- **`clear_location` is sent only when a post that HAD a pin loses it.** A null
  `location` in a PATCH is indistinguishable from "field not sent" after
  serialisation, so removing a pin needs the explicit flag.
- **Editing replaces the author's panel rather than opening a modal**, so the post
  itself stays visible above the form while you change it.
- Driving a React `<select>` from the harness needs the native setter on
  `HTMLSelectElement.prototype` and a `change` event — same trap as the text
  inputs, different prototype.

## Revisions — 2026-07-29, round five ("Mark it sorted" removed)

- **"Mark it sorted" and "Put it back up" are gone from the author's panel.**
  Nobody could tell what "sorted" meant, and the concept was doing two jobs at
  once (freeing an allowance slot, and closing a post to replies) behind one
  opaque verb. The panel is now just **Edit** and **Take it down**, with Edit
  promoted to the primary button since it's the one an author reaches for.
- **The word "sorted" is gone from the interface entirely** — the tag reads
  "Closed" and the closed-post message says "the author closed it". Half-removing
  vocabulary is worse than not removing it.
- **`resolved_at` stays in the schema and on the API.** Nothing in the app sets
  it any more, so those renderings are defensive (an admin or a direct API call
  could still close a post). Ripping out the column would mean a destructive
  migration for a label problem.
- **Consequence, deliberately accepted:** an author who is finished with a post
  now either takes it down or waits for it to expire. Taking it down is
  permanent and removes the replies — the hint text says so plainly rather than
  leaving someone to find out.

## Revisions — 2026-08-05 (clicking the map list flies to the pin)

- **A sidebar row now moves the map instead of navigating.** The row became a
  `<button>`; a compact "Details" link beside it is the way to the event's own
  page. Keeping that link explicit rather than making it a second-click gesture
  means the route to an event page stays discoverable.
- **`Details` sits beside the row, not under it.** On its own line it made all
  40+ rows noticeably taller — 83px per row versus ~140px. Measured, not guessed.
- **The fly-to offsets the centre so the panel isn't covering the pin.** The
  panel is a 358px left column on desktop and a bottom sheet on mobile, so the
  offset is computed by measuring the live element against the map container
  rather than hardcoding either number — one code path, and it can't drift out of
  sync with the CSS. Done in projected pixels at the destination zoom and
  converted back, since that's the only way to say "200px west of here" as a
  coordinate. Verified: the pin lands **0px** from the centre of the visible area
  at both 1440px and 390px.
- **`focus` carries a sequence number, not just an id.** Clicking the same row
  twice should fly there twice, and a bare id doesn't change between renders.
- **The tooltip opens on `moveend`, not immediately.** Opened mid-flight it
  drifts, because Leaflet is still repositioning.

## Revisions — 2026-08-05 (the AI flyer)

- **Caprasimo and Figtree are now self-hosted** (`public/fonts`, 44KB, latin
  subsets, Figtree as one variable file) and the cross-origin `@import` from
  fonts.googleapis.com is gone. The reason is the flyer: html2canvas is
  unreliable with webfonts loaded cross-origin, and an exported poster that falls
  back to Georgia is a real quality failure, not a cosmetic one. Verified with
  `document.fonts.check('16px Caprasimo')` returning true and by looking at the
  exported PNG.
- **The flyer template contains no `<img>` at all.** Text, our own CSS, and the
  QR as inline SVG. html2canvas taints the canvas on the first cross-origin
  resource it meets, and a tainted canvas exports as a blank rectangle. A check
  asserts `.flyer img` is empty.
- **`QRCodeSVG`, not the canvas renderer.** html2canvas rasterises inline SVG
  reliably; a nested `<canvas>` comes out blank often enough to matter.
- **The preview transform leaked into the export — caught, then fixed.** The
  preview shrinks the flyer with `transform: scale(0.48)`, and html2canvas honours
  that: the first export came out **840×1192 instead of 1748×2480**, i.e. text
  rasterised at half size and enlarged. The export now neutralises the wrapper's
  transform for the duration of the capture and passes explicit width/height.
  Found by checking the PNG's IHDR dimensions, not by looking at it.
- **`await document.fonts.ready` before rasterising**, or a cold load exports on
  the fallback face.
- **html2canvas and jsPDF are dynamically imported.** Together they are ~590KB;
  nobody who isn't making a flyer should pay for them at first load. They now sit
  in their own chunks.
- **Two layout bugs found by looking at the exported file:** the fallback's first
  option uses the title as the headline, which printed the same words twice (the
  "What" row is now dropped when they match); and the facts block left a large
  dead gap, so the headline block grows instead and the facts anchor above the QR.

## Not done (deferred)

- No automated frontend tests (the backend now has a 200-test pytest suite;
  UI flows verified through the Vite proxy — the board was checked at 1440px
  and 390px, as author and as visitor, with horizontal overflow measured at 0).
- No optimistic UI; every mutation waits for the server then reloads.
- No pagination controls in the UI (backend supports limit/offset; defaults
  cover MVP volumes).
