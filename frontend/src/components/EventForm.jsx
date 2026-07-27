import { useState } from "react";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Field from "./Field.jsx";
import LocationPicker from "./LocationPicker.jsx";
import AddressAutocomplete from "./AddressAutocomplete.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import { tagIcon } from "../lib/tagIcons.js";

// The current local wall-clock time as "YYYY-MM-DDTHH:MM" for a datetime-local
// input's `min`.
function localNow() {
  const now = new Date();
  return new Date(now - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

// Shared create/edit form for events and help requests. The parent owns what
// "submit" means (POST vs PATCH, where to navigate); this owns fields,
// validation and payload shape. The form tints itself to its type (sage for a
// gathering, terracotta for a help request).
export default function EventForm({
  initial = {},
  submitLabel = "Save",
  onSubmit,
  lockKind = false,
  enforceFutureStart = false,
}) {
  const here = useGeolocation();
  const minStart = enforceFutureStart ? localNow() : undefined;
  const { data: interests } = useApi(() => api.get("/api/interests"));

  const [kind, setKind] = useState(initial.kind ?? "gathering");
  const [title, setTitle] = useState(initial.title ?? "");
  const [description, setDescription] = useState(initial.description ?? "");
  const [location, setLocation] = useState(initial.location ?? null);
  const [address, setAddress] = useState(initial.address ?? "");
  const [startsAt, setStartsAt] = useState(initial.startsAt ?? "");
  const [endsAt, setEndsAt] = useState(initial.endsAt ?? "");
  const [visibility, setVisibility] = useState(initial.visibility ?? "public");
  const [capacity, setCapacity] = useState(initial.capacity ?? "");
  const [tagId, setTagId] = useState(initial.tagId ?? "");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

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
    <form
      className={`card event-form ${kind === "help_request" ? "form-help" : "form-gathering"}`}
      onSubmit={handleSubmit}
      style={{ gap: "22px", padding: "30px" }}
    >
      {error && <div className="alert">{error}</div>}

      <div className="field">
        <span className="field-label">Type</span>
        {lockKind ? (
          <div className="pill-tabs">
            <span className="pill-tab on">
              {kind === "help_request" ? "Help request" : "Gathering"}
            </span>
          </div>
        ) : (
          <div className="pill-tabs">
            <button
              type="button"
              className={kind === "gathering" ? "pill-tab on" : "pill-tab"}
              onClick={() => setKind("gathering")}
            >
              Gathering
            </button>
            <button
              type="button"
              className={kind === "help_request" ? "pill-tab on" : "pill-tab"}
              onClick={() => setKind("help_request")}
            >
              Help request
            </button>
          </div>
        )}
        <span className="field-hint">
          Bring people together, or ask a neighbor for a hand.
        </span>
      </div>

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

      <div className="field">
        <span className="field-label">Location</span>
        {mapCenter ? (
          <div className="picker-map">
            <LocationPicker center={mapCenter} value={location} onPick={setLocation} />
          </div>
        ) : (
          <div className="picker-map centered muted">Locating…</div>
        )}
        <span className="field-hint">Click the map to fine-tune the exact spot.</span>
      </div>

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
        <div className="field">
          <span className="field-label">Category</span>
          <span className="field-hint">Pick one — it sets the event's map icon.</span>
          <div className="chip-grid">
            {interests.map((i) => (
              <button
                type="button"
                key={i.id}
                className={tagId === i.id ? "chip chip-on" : "chip"}
                onClick={() => setTagId((cur) => (cur === i.id ? "" : i.id))}
              >
                {tagIcon(i.slug)} {i.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <button type="submit" disabled={submitting} style={{ alignSelf: "flex-start", padding: "13px 30px", fontSize: "16px" }}>
        {submitting ? "Saving…" : `${submitLabel} →`}
      </button>
    </form>
  );
}
