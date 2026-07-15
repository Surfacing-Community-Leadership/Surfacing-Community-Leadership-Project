import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";

// An address text field that suggests matching addresses as you type.
// Props:
//   value     - the current address string (controlled by the parent)
//   onChange  - called with the new text as the user types freely
//   onSelect  - called with { address, lat, lng } when a suggestion is picked
//   center    - { lat, lng } to restrict results to that region (optional)
//
// Debounced so we query the geocoder only after typing pauses — both kinder
// to the user and required by Nominatim's usage policy (no per-keystroke hits).
export default function AddressAutocomplete({ value, onChange, onSelect, center }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);
  // When a pick updates `value`, we must NOT treat that as "user typed" and
  // fire another search — this flag swallows exactly that one change.
  const justPicked = useRef(false);

  useEffect(() => {
    if (justPicked.current) {
      justPicked.current = false;
      return;
    }
    if (!value || value.trim().length < 3) {
      setSuggestions([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ q: value });
        if (center) {
          params.set("lat", center.lat);
          params.set("lng", center.lng);
        }
        const results = await api.get(`/api/geocode?${params}`);
        setSuggestions(results);
        setOpen(true);
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 450);
    return () => clearTimeout(debounceRef.current);
  }, [value]);

  function pick(s) {
    justPicked.current = true;
    onSelect({ address: s.display_name, lat: s.lat, lng: s.lng });
    setSuggestions([]);
    setOpen(false);
  }

  return (
    <div className="autocomplete">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        // Delay close so a click on a suggestion registers before blur hides it.
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Start typing an address…"
        maxLength={500}
        autoComplete="off"
      />
      {loading && <span className="field-hint">Searching…</span>}
      {open && suggestions.length > 0 && (
        <ul className="autocomplete-list">
          {suggestions.map((s, i) => (
            <li key={i}>
              <button type="button" onClick={() => pick(s)}>
                {s.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
