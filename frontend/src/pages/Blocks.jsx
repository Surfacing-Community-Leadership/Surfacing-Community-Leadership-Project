import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

export default function Blocks() {
  const { data, error, loading, reload } = useApi(() => api.get("/api/blocks"));
  const [actionError, setActionError] = useState(null);

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

  async function unblock(blockedId) {
    setActionError(null);
    try {
      await api.del(`/api/blocks/${blockedId}`);
      await reload();
    } catch (err) {
      setActionError(err.message);
    }
  }

  return (
    <div className="narrow">
      <Link to="/profile" className="muted">
        ← Back to profile
      </Link>
      <h1>Blocked users</h1>
      {actionError && <div className="alert">{actionError}</div>}
      <div className="card">
        {data.length === 0 && <p className="muted">You haven't blocked anyone.</p>}
        <ul className="plain-list">
          {data.map((b) => (
            <li key={b.blocked_id} className="invite-row">
              <span>{b.display_name}</span>
              <button className="secondary" onClick={() => unblock(b.blocked_id)}>
                Unblock
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
