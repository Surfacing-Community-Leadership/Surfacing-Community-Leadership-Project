import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import MapView from "../components/MapView.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import { tagIcon } from "../lib/tagIcons.js";
import { kindLabel } from "../lib/eventKinds.js";

export default function MapHome() {
  const center = useGeolocation(); // [lat, lng]; null until located
  const [events, setEvents] = useState([]);
  // Board notices that carry a location. Kept in their own state and their own
  // request: a notice isn't an event, has no start time to sort by, and must not
  // land in the "spots nearby" list as something you could attend.
  const [notices, setNotices] = useState([]);
  const [showNotices, setShowNotices] = useState(true);
  const [kind, setKind] = useState(""); // "", "gathering", "help_request"
  // "" = all categories, "mine" = matching my interests, or an interest id.
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Which event the map is pointed at. `seq` increments on every click so
  // tapping the same row twice flies there twice — an id alone wouldn't change.
  const [focus, setFocus] = useState(null);
  const mapRef = useRef(null);

  const focusOnMap = useCallback((id) => {
    setFocus((current) => ({ id, seq: (current?.seq ?? 0) + 1 }));
  }, []);
  const { data: interests } = useApi(() => api.get("/api/interests"));

  const fetchEvents = useCallback(
    async (lat, lng, radiusM) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({
          lat: lat.toFixed(6),
          lng: lng.toFixed(6),
          radius_m: Math.round(radiusM),
        });
        if (kind) params.set("kind", kind);
        if (category === "mine") params.set("matching_interests", "true");
        else if (category) params.set("tag_id", category);
        setEvents(await api.get(`/api/events?${params}`));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }

      // Notice pins ride along but never block the map: a failure here leaves
      // the events showing rather than erroring the whole screen.
      try {
        const pins = new URLSearchParams({
          lat: lat.toFixed(6),
          lng: lng.toFixed(6),
          radius_m: Math.round(radiusM),
        });
        setNotices(await api.get(`/api/notices/map?${pins}`));
      } catch {
        setNotices([]);
      }
    },
    [kind, category],
  );

  // Radius = distance from the map center to a corner of the current view,
  // so we fetch roughly what the user can see.
  const searchVisibleArea = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const c = map.getCenter();
    const radiusM = c.distanceTo(map.getBounds().getNorthEast());
    fetchEvents(c.lat, c.lng, Math.min(radiusM, 100000));
  }, [fetchEvents]);

  // Initial load once located, and again whenever a filter changes.
  useEffect(() => {
    if (!center) return;
    if (mapRef.current) searchVisibleArea();
    else fetchEvents(center[0], center[1], 5000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center, kind, category]);

  if (!center) {
    return <div className="centered muted">Finding your neighborhood…</div>;
  }

  return (
    <div className="map-immersive">
      <MapView
        center={center}
        events={events}
        notices={showNotices ? notices : []}
        focus={focus}
        onReady={(map) => {
          mapRef.current = map;
        }}
      />
      <button className="search-area" onClick={searchVisibleArea} disabled={loading}>
        {loading ? "Searching…" : "Search this area"}
      </button>

      <aside className="map-panel">
        <div className="sidebar-header">
          <span className="eyebrow">Nearby</span>
          <span className="sidebar-count">
            {events.length} {events.length === 1 ? "spot" : "spots"}
          </span>
        </div>
        <div className="map-filters">
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All types</option>
            <option value="gathering">Gatherings</option>
            <option value="help_request">Help requests</option>
            <option value="volunteer_work">Volunteer work</option>
          </select>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="mine">✨ For you</option>
            <option value="">All categories</option>
            {interests?.map((i) => (
              <option key={i.id} value={i.id}>
                {tagIcon(i.slug)} {i.name}
              </option>
            ))}
          </select>
        </div>
        {notices.length > 0 && (
          <label className="map-notice-toggle">
            <input
              type="checkbox"
              checked={showNotices}
              onChange={(e) => setShowNotices(e.target.checked)}
            />
            Show {notices.length} board {notices.length === 1 ? "post" : "posts"}
            <Link to="/board" className="link-button">
              Board
            </Link>
          </label>
        )}

        <div className="map-panel-scroll">
          {error && <div className="alert">{error}</div>}
          {!loading && events.length === 0 && (
            <p className="map-empty">
              {category === "mine"
                ? "Nothing here matches your interests yet. Try widening to All categories, or "
                : "Nothing here yet. Pan the map and search again, or "}
              <Link to="/events/new">create something</Link>.
            </p>
          )}

          <ul className="event-list">
            {events.map((ev) => (
              <li
                key={ev.id}
                className={focus?.id === ev.id ? "event-row selected" : "event-row"}
              >
                {/* The row itself moves the map rather than navigating — the
                    list is how you look around. "Details" is the way out to the
                    event's own page, kept explicit so it stays discoverable. */}
                <button
                  type="button"
                  className="event-list-item"
                  aria-pressed={focus?.id === ev.id}
                  onClick={() => focusOnMap(ev.id)}
                >
                  <span className={`dot dot-${ev.kind}`} />
                  <span className="event-list-body">
                    <strong>{ev.title}</strong>
                    <span className="muted">
                      {ev.source === "imported" ? "Around town ↗" : kindLabel(ev.kind)}
                      {ev.tag_name && ` · ${ev.tag_name}`}
                      {ev.distance_m != null && ` · ${formatDistance(ev.distance_m)}`}
                    </span>
                  </span>
                </button>
                <Link
                  to={`/events/${ev.id}`}
                  className="event-row-details"
                  aria-label={`Open ${ev.title}`}
                >
                  Details
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function formatDistance(m) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}
