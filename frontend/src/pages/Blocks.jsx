import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

function initial(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}

export default function Blocks() {
  const { data, error, loading, reload } = useApi(() => api.get("/api/blocks"));
  const [actionError, setActionError] = useState(null);

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

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
    <div className="org narrow">
      <Link to="/profile" className="link-button" style={{ display: "inline-block", marginBottom: "22px" }}>
        ← Back to profile
      </Link>
      <h1>Blocked users</h1>
      <p className="muted" style={{ maxWidth: "50ch", lineHeight: 1.6, marginBottom: "28px" }}>
        Blocked neighbors can't see your events, invite you, or send requests —
        and you won't see theirs. Unblocking takes effect right away.
      </p>
      {actionError && <div className="alert">{actionError}</div>}

      {data.length === 0 ? (
        <p className="muted">You haven't blocked anyone.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {data.map((b) => (
            <div
              key={b.blocked_id}
              className="card row-card"
              style={{ padding: "16px 20px", marginBottom: 0 }}
            >
              <span className="avatar-initial neutral sm">{initial(b.display_name)}</span>
              <strong style={{ flex: 1, fontSize: "15px" }}>{b.display_name}</strong>
              <button
                className="secondary"
                onClick={() => unblock(b.blocked_id)}
                style={{ fontSize: "13px", padding: "8px 16px" }}
              >
                Unblock
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
