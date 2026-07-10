import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";

// Another person's profile, with the safety/social actions from the spec:
// connect, block, report.
export default function PublicProfile() {
  const { userId } = useParams();
  const { user } = useAuth();
  const { data: profile, error, loading } = useApi(
    () => api.get(`/api/profiles/${userId}`),
    [userId],
  );
  const [status, setStatus] = useState(null);

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

  const isMe = userId === user.id;

  async function run(label, fn) {
    setStatus(null);
    try {
      await fn();
      setStatus(label);
    } catch (err) {
      setStatus(err.message);
    }
  }

  const connect = () =>
    run("Connection request sent.", () =>
      api.post("/api/connections", { addressee_id: userId }),
    );
  const block = () => {
    if (!confirm(`Block ${profile.display_name}? This removes any connection.`)) return;
    run("User blocked.", () => api.post("/api/blocks", { blocked_id: userId }));
  };
  const report = () => {
    const reason = prompt("Why are you reporting this person?");
    if (!reason) return;
    run("Report sent to moderators.", () =>
      api.post("/api/reports", { reported_user_id: userId, reason }),
    );
  };

  return (
    <div className="narrow">
      <Link to="/" className="muted">
        ← Back
      </Link>
      <div className="card">
        <div className="avatar-lg">{profile.avatar_key || "🙂"}</div>
        <h1>{profile.display_name}</h1>
        {profile.bio && <p>{profile.bio}</p>}
        {status && <div className="muted">{status}</div>}
        {!isMe && (
          <div className="row-actions">
            <button onClick={connect}>Connect</button>
            <button className="secondary" onClick={block}>
              Block
            </button>
            <button className="link-button" onClick={report}>
              Report
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
