import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import L from "leaflet";

// Wireframe markers: a colored dot per event kind. Using divIcon sidesteps
// the classic Leaflet-with-bundlers broken-image-path problem entirely.
const ICONS = {
  gathering: L.divIcon({ className: "pin pin-gathering", iconSize: [16, 16] }),
  help_request: L.divIcon({ className: "pin pin-help", iconSize: [16, 16] }),
};

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
        >
          <Popup>
            <strong>{ev.title}</strong>
            <br />
            <span className="muted">
              {ev.kind === "help_request" ? "Help request" : "Gathering"}
            </span>
            <br />
            <button className="link-button" onClick={() => navigate(`/events/${ev.id}`)}>
              View details →
            </button>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
