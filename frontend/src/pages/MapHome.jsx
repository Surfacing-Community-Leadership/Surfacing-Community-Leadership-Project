import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import MapView from "../components/MapView.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import { tagIcon } from "../lib/tagIcons.js";

export default function MapHome() {
  const center = useGeolocation(); // [lat, lng]; null until located
  const [events, setEvents] = useState([]);
  const [kind, setKind] = useState(""); // "", "gathering", "help_request"
  // "" = all categories, "mine" = matching my interests, or an interest id.
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const mapRef = useRef(null);
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
    <div className="map-layout">
      <div className="map-main">
        <MapView
          center={center}
          events={events}
          onReady={(map) => {
            mapRef.current = map;
          }}
        />
        <button className="search-area" onClick={searchVisibleArea} disabled={loading}>
          {loading ? "Searching…" : "Search this area"}
        </button>
      </div>

      <aside className="map-sidebar">
        <div className="sidebar-header">
          <h2>Nearby</h2>
        </div>
        <div className="map-filters">
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All types</option>
            <option value="gathering">Gatherings</option>
            <option value="help_request">Help requests</option>
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

        {error && <div className="alert">{error}</div>}
        {!loading && events.length === 0 && (
          <p className="muted">
            {category === "mine"
              ? "Nothing here matches your interests yet. Try widening to All categories, or "
              : "Nothing here yet. Pan the map and search again, or "}
            <Link to="/events/new">create something</Link>.
          </p>
        )}

        <ul className="event-list">
          {events.map((ev) => (
            <li key={ev.id}>
              <Link to={`/events/${ev.id}`} className="event-list-item">
                <span className={`dot dot-${ev.kind}`} />
                <span className="event-list-body">
                  <strong>{ev.title}</strong>
                  <span className="muted">
                    {ev.source === "imported" ? "Around town ↗" : ev.kind === "help_request" ? "Help request" : "Gathering"}
                    {ev.tag_name && ` · ${ev.tag_name}`}
                    {ev.distance_m != null && ` · ${formatDistance(ev.distance_m)}`}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function formatDistance(m) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}
