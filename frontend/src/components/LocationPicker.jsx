import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import L from "leaflet";

const PIN = L.divIcon({ className: "pin pin-gathering", iconSize: [16, 16] });

function ClickCapture({ onPick }) {
  useMapEvents({
    click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }),
  });
  return null;
}

// A small map where clicking drops/moves the pin. `value` is { lat, lng }.
export default function LocationPicker({ center, value, onPick }) {
  return (
    <MapContainer center={center} zoom={14} className="picker-map">
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <ClickCapture onPick={onPick} />
      {value && <Marker position={[value.lat, value.lng]} icon={PIN} />}
    </MapContainer>
  );
}
