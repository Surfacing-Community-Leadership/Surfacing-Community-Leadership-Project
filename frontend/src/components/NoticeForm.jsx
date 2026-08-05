import { useState } from "react";
import AddressAutocomplete from "./AddressAutocomplete.jsx";
import LocationPicker from "./LocationPicker.jsx";
import { useGeolocation } from "../hooks/useGeolocation.js";
import {
  categoryHint,
  categoryLabel,
  isLongForm,
  suggestsPin,
} from "../lib/noticeCategories.js";

// The one form for writing a board post, used both to create and to edit.
//
// Shared deliberately: two copies of nine fields, an address geocoder and a map
// picker would drift within a week, and the edit form would quietly lose
// whichever refinement the create form gained.
//
// The parent owns what happens on submit — this component builds a payload and
// hands it over. `existing` switches it to edit mode, which differs in exactly
// two ways: fields start filled, and expiry defaults to "leave it alone"
// (see EXPIRY_UNCHANGED) so editing a typo doesn't silently reset the clock.

const EXPIRY_UNCHANGED = "";

function expiryLabel(days) {
  return days === 7
    ? "A week"
    : days === 14
      ? "Two weeks"
      : days === 30
        ? "A month"
        : "Three months";
}

function daysLeft(expiresAt) {
  const ms = new Date(expiresAt) - new Date();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

export default function NoticeForm({
  meta,
  existing = null,
  submitLabel,
  savingLabel,
  onSubmit,
  onCancel,
}) {
  const editing = Boolean(existing);
  const categories = meta.categories;
  const here = useGeolocation();

  const [category, setCategory] = useState(
    existing?.category ?? categories[0] ?? "giveaway",
  );
  const [title, setTitle] = useState(existing?.title ?? "");
  const [body, setBody] = useState(existing?.body ?? "");
  const [placeHint, setPlaceHint] = useState(existing?.place_hint ?? "");
  // Coordinates of an address picked from the suggestions, kept apart from
  // `location` so ticking the pin box later can still use them.
  const [addressPoint, setAddressPoint] = useState(null);
  // Editing starts at "unchanged"; creating starts at the default window.
  const [expiryDays, setExpiryDays] = useState(
    editing ? EXPIRY_UNCHANGED : meta.default_expiry_days,
  );
  const [allowInquiries, setAllowInquiries] = useState(
    existing?.allow_direct_inquiries ?? true,
  );
  const [pinned, setPinned] = useState(Boolean(existing?.location));
  const [location, setLocation] = useState(existing?.location ?? null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Follow the pin once it's placed, so fine-tuning doesn't fight the map.
  const mapCenter = location ? [location.lat, location.lng] : here;

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const payload = {
      category,
      title,
      body,
      place_hint: placeHint.trim() || null,
      allow_direct_inquiries: allowInquiries,
    };

    if (pinned && location) {
      payload.location = location;
    } else if (editing && existing.location && !pinned) {
      // An explicit flag, because a null `location` in a PATCH is
      // indistinguishable from "field not sent" once it's serialised.
      payload.clear_location = true;
    } else if (!editing) {
      payload.location = null;
    }

    if (expiryDays !== EXPIRY_UNCHANGED) {
      const expires = new Date();
      expires.setDate(expires.getDate() + Number(expiryDays));
      payload.expires_at = expires.toISOString();
    }

    try {
      await onSubmit(payload);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <form className={`notice-form form-${category}`} onSubmit={submit}>
      <h2>{editing ? "Edit your post" : "Write a post"}</h2>
      {error && <div className="alert">{error}</div>}

      <div className="field">
        <label className="field-label" htmlFor="notice-category">
          What kind of post
        </label>
        <select
          id="notice-category"
          className="input"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {categories.map((key) => (
            <option key={key} value={key}>
              {categoryLabel(key)}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-title">
          Headline
        </label>
        <input
          id="notice-title"
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={140}
          placeholder="Free bookshelf"
          required
        />
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-body">
          Details
        </label>
        <textarea
          id="notice-body"
          className="input"
          rows={isLongForm(category) ? 10 : 4}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          maxLength={meta.max_body_chars}
          required
        />
        <p className="field-hint">
          {categoryHint(category)}
          {isLongForm(category) && (
            <>
              {" "}
              <span className="muted">
                {body.length}/{meta.max_body_chars}
              </span>
            </>
          )}
        </p>
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-place">
          Whereabouts <span className="muted">(optional)</span>
        </label>
        {/* Suggests addresses but doesn't insist on one: "the bench by the
            playground" is often more use to a neighbour, and free text still
            works. Picking a suggestion is what gives us coordinates. */}
        <AddressAutocomplete
          value={placeHint}
          onChange={(text) => {
            setPlaceHint(text);
            // Typing over a chosen address invalidates its coordinates.
            setAddressPoint(null);
          }}
          onSelect={({ address, lat, lng }) => {
            setPlaceHint(address);
            const point = { lat, lng };
            setAddressPoint(point);
            // Placing the pin at the address is the whole point of picking one,
            // so it lands immediately — and it's still draggable by clicking
            // the map, since an address is often only approximately the spot.
            setLocation(point);
            setPinned(true);
          }}
          center={here ? { lat: here[0], lng: here[1] } : undefined}
        />
        <p className="field-hint">
          Pick a suggestion to place the map pin automatically, or just describe
          it — a landmark often reads better than an address.
        </p>
      </div>

      <div className="field">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={pinned}
            onChange={(e) => {
              const on = e.target.checked;
              setPinned(on);
              // Ticking the box after choosing an address reuses that address
              // rather than making the author hunt for the spot again.
              if (on && !location && addressPoint) setLocation(addressPoint);
            }}
          />
          Also drop a pin on the map
          {suggestsPin(category) && <span className="muted"> — useful for this kind</span>}
        </label>
        {pinned && (
          <>
            {/* LocationPicker needs an explicit centre — Leaflet can't
                initialise a view without one, and the map renders blank. */}
            {mapCenter ? (
              <div className="picker-map">
                <LocationPicker
                  center={mapCenter}
                  value={location}
                  onPick={setLocation}
                />
              </div>
            ) : (
              <div className="picker-map centered muted">Locating…</div>
            )}
            <p className="field-hint">
              {addressPoint && location
                ? "Placed at the address you picked — click the map to nudge it."
                : "Click the map to place it."}{" "}
              Informational only — it appears as a muted pin so nobody mistakes
              it for something to attend.
            </p>
          </>
        )}
      </div>

      <div className="field">
        <label className="field-label" htmlFor="notice-expiry">
          Take it down after
        </label>
        <select
          id="notice-expiry"
          className="input"
          value={expiryDays}
          onChange={(e) => setExpiryDays(e.target.value)}
        >
          {/* Editing a typo shouldn't quietly restart the clock, so an edit
              leaves the existing expiry alone unless the author picks a window. */}
          {editing && (
            <option value={EXPIRY_UNCHANGED}>
              Leave as it is — {daysLeft(existing.expires_at)} days left
            </option>
          )}
          {meta.expiry_choices_days.map((days) => (
            <option key={days} value={days}>
              {expiryLabel(days)}
              {editing ? " from now" : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={allowInquiries}
            onChange={(e) => setAllowInquiries(e.target.checked)}
          />
          Let neighbors send me a private reply
        </label>
        <p className="field-hint">
          Replies come to you alone and never appear on the board. Turn this off
          for something nobody needs to answer.
        </p>
      </div>

      <div className="row-actions">
        <button className="btn btn-primary" disabled={saving || (pinned && !location)}>
          {saving ? savingLabel : submitLabel}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {pinned && !location && (
        <p className="field-hint">Tap the map to place your pin.</p>
      )}
    </form>
  );
}
