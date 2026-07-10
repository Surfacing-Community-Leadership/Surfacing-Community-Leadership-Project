import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import MapView from "../components/MapView.jsx";

// Falls back to Sunset Park, Brooklyn if the browser denies geolocation —
// enough to render a useful map instead of an error.
const FALLBACK_CENTER = [40.6552, -74.0069];

export default function MapHome() {
  const [center, setCenter] = useState(null); // [lat, lng]; null until located
  const [events, setEvents] = useState([]);
  const [kind, setKind] = useState(""); // "", "gathering", "help_request"
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const mapRef = useRef(null);

  // Resolve an initial center before first render so the map opens in the
  // right place (MapContainer's center is only read once).
  useEffect(() => {
    if (!navigator.geolocation) {
      setCenter(FALLBACK_CENTER);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setCenter([pos.coords.latitude, pos.coords.longitude]),
      () => setCenter(FALLBACK_CENTER),
      { timeout: 5000 },
    );
  }, []);

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
        setEvents(await api.get(`/api/events?${params}`));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [kind],
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

  // Initial load once located, and again whenever the kind filter changes.
  useEffect(() => {
    if (!center) return;
    if (mapRef.current) searchVisibleArea();
    else fetchEvents(center[0], center[1], 5000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center, kind]);

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
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All</option>
            <option value="gathering">Gatherings</option>
            <option value="help_request">Help requests</option>
          </select>
        </div>

        {error && <div className="alert">{error}</div>}
        {!loading && events.length === 0 && (
          <p className="muted">
            Nothing here yet. Pan the map and search again, or{" "}
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
                    {ev.kind === "help_request" ? "Help request" : "Gathering"}
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
