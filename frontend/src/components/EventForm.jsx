import { useState } from "react";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Field from "./Field.jsx";
import LocationPicker from "./LocationPicker.jsx";
import AddressAutocomplete from "./AddressAutocomplete.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import { tagIcon } from "../lib/tagIcons.js";

// The current local wall-clock time as "YYYY-MM-DDTHH:MM" — the format a
// datetime-local input's `min` expects. Shifting by the timezone offset makes
// the UTC-based toISOString() read out local time.
function localNow() {
  const now = new Date();
  return new Date(now - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

// The shared create/edit form for events and help requests. The parent owns
// what "submit" means (POST vs PATCH, where to navigate); this component owns
// the fields, validation, and payload shape so the two flows never drift.
//
// Props:
//   initial      - seed values { kind, title, description, location, address,
//                  startsAt, endsAt, visibility, capacity, tagId }
//   submitLabel  - text for the submit button
//   onSubmit     - async (payload) => void; throws to surface an error here
//   lockKind     - true on edit: the gathering/help-request type is fixed
//   enforceFutureStart - true on create: disallow scheduling in the past
export default function EventForm({
  initial = {},
  submitLabel = "Save",
  onSubmit,
  lockKind = false,
  enforceFutureStart = false,
}) {
  const here = useGeolocation(); // [lat, lng]; null until located
  const minStart = enforceFutureStart ? localNow() : undefined;
  const { data: interests } = useApi(() => api.get("/api/interests"));

  const [kind, setKind] = useState(initial.kind ?? "gathering");
  const [title, setTitle] = useState(initial.title ?? "");
  const [description, setDescription] = useState(initial.description ?? "");
  const [location, setLocation] = useState(initial.location ?? null); // { lat, lng }
  const [address, setAddress] = useState(initial.address ?? "");
  const [startsAt, setStartsAt] = useState(initial.startsAt ?? "");
  const [endsAt, setEndsAt] = useState(initial.endsAt ?? "");
  const [visibility, setVisibility] = useState(initial.visibility ?? "public");
  const [capacity, setCapacity] = useState(initial.capacity ?? "");
  const [tagId, setTagId] = useState(initial.tagId ?? "");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Center the pickers on the event's location if it has one, else on "here".
  const mapCenter = location ? [location.lat, location.lng] : here;

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (!location) {
      setError("Please pick a location on the map.");
      return;
    }
    setSubmitting(true);
    try {
      // datetime-local yields a naive string; append Z to send as UTC.
      await onSubmit({
        kind,
        title,
        description: description || null,
        location,
        address: address || null,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        visibility,
        capacity: capacity ? Number(capacity) : null,
        tag_id: tagId || null,
      });
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      {error && <div className="alert">{error}</div>}

      <Field label="Type">
        {lockKind ? (
          <input
            value={kind === "help_request" ? "Help request" : "Gathering"}
            disabled
          />
        ) : (
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="gathering">Gathering — bring people together</option>
            <option value="help_request">Help request — ask for a hand</option>
          </select>
        )}
      </Field>

      <Field label="Title">
        <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
      </Field>

      <Field label="Description">
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          maxLength={5000}
        />
      </Field>

      <Field
        label="Address"
        hint="Start typing to search; picking a result drops the map pin. Shown only to confirmed attendees."
      >
        <AddressAutocomplete
          value={address}
          onChange={setAddress}
          onSelect={({ address: picked, lat, lng }) => {
            setAddress(picked);
            setLocation({ lat, lng });
          }}
          center={location || (here ? { lat: here[0], lng: here[1] } : undefined)}
        />
      </Field>

      <Field label="Location" hint="Click the map to fine-tune the exact spot.">
        {mapCenter ? (
          <LocationPicker center={mapCenter} value={location} onPick={setLocation} />
        ) : (
          <div className="picker-map centered muted">Locating…</div>
        )}
      </Field>

      <div className="field-row">
        <Field label="Starts">
          <input
            type="datetime-local"
            value={startsAt}
            min={minStart}
            onChange={(e) => setStartsAt(e.target.value)}
            required
          />
        </Field>
        <Field label="Ends (optional)">
          <input
            type="datetime-local"
            value={endsAt}
            min={startsAt || minStart}
            onChange={(e) => setEndsAt(e.target.value)}
          />
        </Field>
      </div>

      <div className="field-row">
        <Field label="Visibility">
          <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
            <option value="public">Public — anyone nearby</option>
            <option value="community">Community only</option>
            <option value="private">Private — invite only</option>
          </select>
        </Field>
        <Field label="Capacity (optional)">
          <input
            type="number"
            min="1"
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
          />
        </Field>
      </div>

      {interests && (
        <Field label="Category" hint="Pick one — it sets the event's map icon.">
          <div className="chip-grid">
            {interests.map((i) => (
              <button
                type="button"
                key={i.id}
                className={tagId === i.id ? "chip chip-on" : "chip"}
                // Click the selected one again to clear it (category is optional).
                onClick={() => setTagId((cur) => (cur === i.id ? "" : i.id))}
              >
                {tagIcon(i.slug)} {i.name}
              </button>
            ))}
          </div>
        </Field>
      )}

      <button type="submit" disabled={submitting}>
        {submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
