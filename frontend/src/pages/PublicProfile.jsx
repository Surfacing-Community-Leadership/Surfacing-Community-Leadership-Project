import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, avatarUrl } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { ConfirmDialog, ReportDialog } from "../components/dialogs.jsx";

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
  const [dialog, setDialog] = useState(null); // "block" | "report" | null

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
    setDialog(null);
    run("User blocked.", () => api.post("/api/blocks", { blocked_id: userId }));
  };
  const report = (reason) => {
    setDialog(null);
    run("Report sent to moderators.", () =>
      api.post("/api/reports", { reported_user_id: userId, reason }),
    );
  };

  const imgSrc = avatarUrl(profile.avatar_key);

  return (
    <div className="narrow">
      <Link to="/" className="muted">
        ← Back
      </Link>
      <div className="card">
        {imgSrc ? (
          <img className="avatar-img avatar-img-lg" src={imgSrc} alt="" />
        ) : (
          <div className="avatar-lg">{profile.avatar_key || "🙂"}</div>
        )}
        <h1>{profile.display_name}</h1>
        {profile.bio && <p>{profile.bio}</p>}
        {status && <div className="muted">{status}</div>}
        {!isMe && (
          <div className="row-actions">
            <button onClick={connect}>Connect</button>
            <button className="secondary" onClick={() => setDialog("block")}>
              Block
            </button>
            <button className="link-button" onClick={() => setDialog("report")}>
              Report
            </button>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={dialog === "block"}
        title={`Block ${profile.display_name}?`}
        body="They won't be able to see your events, connect with you, or reach you. Any existing connection is removed. They are not notified."
        confirmLabel="Block"
        danger
        onConfirm={block}
        onClose={() => setDialog(null)}
      />
      <ReportDialog
        open={dialog === "report"}
        what={profile.display_name}
        onSubmit={report}
        onClose={() => setDialog(null)}
      />
    </div>
  );
}
