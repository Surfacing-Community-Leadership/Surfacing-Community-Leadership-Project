import { useState } from "react";
import { api } from "../api/client.js";

// A star on a notice: "this was useful", one per account.
//
// The count is an anonymous aggregate and there is no way — here or anywhere —
// to see who starred what. That's the line between a useful signal and a
// popularity contest, and it's why this shows a number but never a face.
//
// Optimistic on purpose: the count is a soft signal, so a flicker matters less
// than the tap feeling instant. A failure rolls the local state back.
export default function StarButton({ notice, onChange, size = "sm" }) {
  const [starred, setStarred] = useState(notice.i_starred);
  const [stars, setStars] = useState(notice.stars ?? 0);
  const [busy, setBusy] = useState(false);

  async function toggle(event) {
    // The card is a link; starring from inside it must not navigate.
    event.preventDefault();
    event.stopPropagation();
    if (busy) return;

    const next = !starred;
    setStarred(next);
    setStars((n) => n + (next ? 1 : -1));
    setBusy(true);
    try {
      const state = next
        ? await api.put(`/api/notices/${notice.id}/star`)
        : await api.del(`/api/notices/${notice.id}/star`);
      setStarred(state.starred);
      setStars(state.stars);
      onChange?.(state);
    } catch {
      setStarred(!next);
      setStars((n) => n + (next ? -1 : 1));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className={`star-btn star-${size}${starred ? " on" : ""}`}
      onClick={toggle}
      aria-pressed={starred}
      title={starred ? "Remove your star" : "Star this — nobody sees who starred"}
    >
      <span aria-hidden="true">{starred ? "★" : "☆"}</span>
      <span className="star-count">{stars}</span>
    </button>
  );
}
