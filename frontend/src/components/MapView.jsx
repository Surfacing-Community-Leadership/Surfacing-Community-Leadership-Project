import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { useNavigate } from "react-router-dom";
import L from "leaflet";

// Wireframe markers: a colored dot per event kind. Using divIcon sidesteps
// the classic Leaflet-with-bundlers broken-image-path problem entirely.
//
// The visible dot is an *inner* <span>, not the icon element itself: Leaflet
// positions the icon element with its own `transform: translate3d(...)`, so
// scaling it on hover (below, in CSS) would clobber that and fling the pin to
// the map's origin. Scaling the inner span leaves Leaflet's transform alone.
const makeIcon = (suffix) =>
  L.divIcon({
    className: "pin-wrap",
    html: `<span class="pin pin-${suffix}"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
const ICONS = {
  gathering: makeIcon("gathering"),
  help_request: makeIcon("help"),
};

function kindLabel(kind) {
  return kind === "help_request" ? "Help request" : "Gathering";
}

function formatWhen(iso) {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDistance(m) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}

// Lives inside MapContainer so it can use the map hooks. Lifts the map
// instance up on mount and reports when the user finishes panning/zooming.
function MapBridge({ onReady, onMoveEnd }) {
  const map = useMap();
  useEffect(() => {
    onReady(map);
  }, [map, onReady]);
  useMapEvents({ moveend: () => onMoveEnd?.() });
  return null;
}

export default function MapView({ center, events, onReady, onMoveEnd }) {
  const navigate = useNavigate();

  return (
    <MapContainer center={center} zoom={14} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <MapBridge onReady={onReady} onMoveEnd={onMoveEnd} />
      {events.map((ev) => (
        <Marker
          key={ev.id}
          position={[ev.location.lat, ev.location.lng]}
          icon={ICONS[ev.kind] || ICONS.gathering}
          eventHandlers={{ click: () => navigate(`/events/${ev.id}`) }}
        >
          {/* Hover: a quick peek. Shows on mouseover, hides on mouseout.
              Clicking the pin goes straight to the event's page. */}
          <Tooltip direction="top" offset={[0, -10]} opacity={1} className="pin-tip">
            <strong>{ev.title}</strong>
            <div className="muted">
              {kindLabel(ev.kind)} · {formatWhen(ev.starts_at)}
              {ev.distance_m != null && ` · ${formatDistance(ev.distance_m)}`}
            </div>
            {ev.status !== "open" && <div className="muted">{ev.status}</div>}
          </Tooltip>
        </Marker>
      ))}
    </MapContainer>
  );
}
