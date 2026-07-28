import { useState } from "react";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

// Follow/unfollow a local organization, with its follower count. Following is
// one-directional and needs no approval — a library doesn't accept or decline.
export default function FollowButton({ orgId, onChange }) {
  const { data, loading } = useApi(
    () => api.get(`/api/organizations/${orgId}/follow`),
    [orgId],
  );
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Local state wins once the user has acted, so the button responds instantly.
  const current = state ?? data;
  if (loading || !current) return null;

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const next = current.following
        ? await api.del(`/api/organizations/${orgId}/follow`)
        : await api.put(`/api/organizations/${orgId}/follow`);
      setState(next);
      onChange?.(next);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="follow-control">
      <button
        className={current.following ? "secondary" : ""}
        onClick={toggle}
        disabled={busy}
      >
        {current.following ? "✓ Following" : "Follow"}
      </button>
      <span className="muted follow-count">
        {current.followers} {current.followers === 1 ? "follower" : "followers"}
      </span>
      {error && <span className="muted">{error}</span>}
    </span>
  );
}
