import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Field from "../components/Field.jsx";
import LocationPicker from "../components/LocationPicker.jsx";

const FALLBACK_CENTER = [40.6552, -74.0069];

export default function CreateEvent() {
  const navigate = useNavigate();
  const { data: interests } = useApi(() => api.get("/api/interests"));

  const [kind, setKind] = useState("gathering");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState(null); // { lat, lng }
  const [address, setAddress] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [capacity, setCapacity] = useState("");
  const [selectedInterests, setSelectedInterests] = useState(new Set());
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function toggleInterest(id) {
    setSelectedInterests((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

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
      const created = await api.post("/api/events", {
        kind,
        title,
        description: description || null,
        location,
        address: address || null,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: endsAt ? new Date(endsAt).toISOString() : null,
        visibility,
        capacity: capacity ? Number(capacity) : null,
        interest_ids: [...selectedInterests],
      });
      navigate(`/events/${created.id}`);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="narrow">
      <h1>Create</h1>
      <form className="card" onSubmit={handleSubmit}>
        {error && <div className="alert">{error}</div>}

        <Field label="Type">
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="gathering">Gathering — bring people together</option>
            <option value="help_request">Help request — ask for a hand</option>
          </select>
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

        <Field label="Location" hint="Click the map to place your pin.">
          <LocationPicker
            center={FALLBACK_CENTER}
            value={location}
            onPick={setLocation}
          />
        </Field>

        <Field label="Address" hint="Shown only to confirmed attendees.">
          <input value={address} onChange={(e) => setAddress(e.target.value)} maxLength={500} />
        </Field>

        <div className="field-row">
          <Field label="Starts">
            <input
              type="datetime-local"
              value={startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
              required
            />
          </Field>
          <Field label="Ends (optional)">
            <input
              type="datetime-local"
              value={endsAt}
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
          <Field label="Tags">
            <div className="chip-grid">
              {interests.map((i) => (
                <button
                  type="button"
                  key={i.id}
                  className={selectedInterests.has(i.id) ? "chip chip-on" : "chip"}
                  onClick={() => toggleInterest(i.id)}
                >
                  {i.name}
                </button>
              ))}
            </div>
          </Field>
        )}

        <button type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create"}
        </button>
      </form>
    </div>
  );
}
