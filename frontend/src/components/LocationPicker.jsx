import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";

const PIN = L.divIcon({ className: "pin pin-gathering", iconSize: [16, 16] });

function ClickCapture({ onPick }) {
  useMapEvents({
    click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }),
  });
  return null;
}

// Recenter the map only when the pin jumps somewhere off-screen — e.g. the
// user picked an address from search. A manual click inside the current view
// leaves the map still, so fine-tuning doesn't cause a jarring re-center.
function Recenter({ value }) {
  const map = useMap();
  useEffect(() => {
    if (value && !map.getBounds().contains([value.lat, value.lng])) {
      map.setView([value.lat, value.lng], map.getZoom());
    }
  }, [value, map]);
  return null;
}

// A small map where clicking drops/moves the pin. `value` is { lat, lng }.
export default function LocationPicker({ center, value, onPick }) {
  return (
    <MapContainer center={center} zoom={14} className="picker-map">
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <ClickCapture onPick={onPick} />
      <Recenter value={value} />
      {value && <Marker position={[value.lat, value.lng]} icon={PIN} />}
    </MapContainer>
  );
}
