import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useGeolocation } from "../hooks/useGeolocation.js";

// Lets the user pick their neighborhood from live OpenStreetMap suggestions
// near where they are, nearest first, with a "wider area" fallback.
//
// The parent only cares about a community_id (a UUID). But OSM candidates
// aren't rows yet, so on select we POST the candidate to materialize it
// (find-or-create) and hand the resulting id up via onChange.
const RADII = [3000, 8000, 20000]; // meters: neighborhood → district → metro

export default function CommunityPicker({ value, onChange }) {
  const here = useGeolocation();
  const [radiusStep, setRadiusStep] = useState(0);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyRef, setBusyRef] = useState(null); // osm_ref being materialized
  // The label to highlight the current choice. Track the selected osm_ref for
  // fresh picks; fall back to fetching the name if we arrive with a saved id.
  const [selectedName, setSelectedName] = useState(null);
  const [selectedRef, setSelectedRef] = useState(null);

  // Fetch nearby suggestions whenever we know "here" or widen the radius.
  useEffect(() => {
    if (!here) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get(
        `/api/communities/nearby?lat=${here[0]}&lng=${here[1]}&radius=${RADII[radiusStep]}`,
      )
      .then((rows) => {
        if (!cancelled) setCandidates(rows);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [here, radiusStep]);

  // If we arrived with a previously-saved community, show its name.
  useEffect(() => {
    if (value && !selectedRef) {
      api
        .get(`/api/communities/${value}`)
        .then((c) => setSelectedName(c.name))
        .catch(() => setSelectedName(null));
    }
    if (!value) setSelectedName(null);
  }, [value, selectedRef]);

  async function pick(candidate) {
    setBusyRef(candidate.osm_ref);
    setError(null);
    try {
      const community = await api.post("/api/communities", {
        osm_ref: candidate.osm_ref,
      });
      setSelectedRef(candidate.osm_ref);
      setSelectedName(community.name);
      onChange(community.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyRef(null);
    }
  }

  function chooseLater() {
    setSelectedRef(null);
    setSelectedName(null);
    onChange("");
  }

  if (!here) return <p className="muted">Finding neighborhoods near you…</p>;

  return (
    <div className="community-picker">
      <p className="muted">
        {selectedName
          ? `Selected: ${selectedName}`
          : "Pick the neighborhood that fits you best."}
      </p>

      {error && <div className="alert">{error}</div>}

      {loading ? (
        <p className="muted">Loading neighborhoods…</p>
      ) : candidates.length === 0 ? (
        <p className="muted">
          No neighborhoods found nearby.{" "}
          {radiusStep < RADII.length - 1 && "Try a wider area below."}
        </p>
      ) : (
        <div className="chip-grid">
          {candidates.map((c) => (
            <button
              type="button"
              key={c.osm_ref}
              className={selectedRef === c.osm_ref ? "chip chip-on" : "chip"}
              disabled={busyRef !== null}
              onClick={() => pick(c)}
            >
              {busyRef === c.osm_ref ? "Saving…" : c.name}
            </button>
          ))}
        </div>
      )}

      <div className="row-actions">
        {radiusStep < RADII.length - 1 && (
          <button
            type="button"
            className="secondary"
            disabled={loading}
            onClick={() => setRadiusStep((s) => s + 1)}
          >
            Search a wider area
          </button>
        )}
        {value && (
          <button type="button" className="link-button" onClick={chooseLater}>
            Choose later
          </button>
        )}
      </div>
    </div>
  );
}
