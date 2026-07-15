import { useEffect, useState } from "react";

// Sunset Park, Brooklyn — the default when geolocation is denied or absent,
// and the neighborhood the demo seed data lives in.
export const FALLBACK_CENTER = [40.6552, -74.0069];

// Resolves the user's location once, as [lat, lng] (null while still
// resolving), falling back to FALLBACK_CENTER if the browser has no
// geolocation or the user denies it.
//
// Both the discovery map and the create-event picker use this same hook, so
// they always agree on where "here" is — otherwise an event created on one
// map can land outside the other map's view and appear to vanish.
export function useGeolocation() {
  const [center, setCenter] = useState(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setCenter(FALLBACK_CENTER);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setCenter([pos.coords.latitude, pos.coords.longitude]),
      () => setCenter(FALLBACK_CENTER),
      { timeout: 5000 },
    );
  }, []);

  return center;
}
