import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, avatarUrl } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { ConfirmDialog, ReportDialog } from "../components/dialogs.jsx";
import TrustBadge from "../components/TrustBadge.jsx";
import FollowButton from "../components/FollowButton.jsx";

function initial(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}

const ORG_LABELS = {
  library: "Library",
  school: "School",
  parks: "Parks & recreation",
  faith: "Faith group",
  nonprofit: "Nonprofit",
  government: "Government body",
  other: "Organization",
};

// An organization always says so. Until a moderator has checked it, it says
// that too — so nobody mistakes a self-declared account for a vetted one.
function OrgLine({ profile }) {
  return (
    <div className="org-line">
      <span className="tag tag-gathering">
        {ORG_LABELS[profile.org_category] || "Organization"}
      </span>
      {profile.verified ? (
        <span className="trust-verified">✓ Verified</span>
      ) : (
        <span className="org-unverified" title="A moderator hasn't checked this account yet">
          Unverified
        </span>
      )}
      {profile.org_website && (
        <a href={profile.org_website} target="_blank" rel="noreferrer noopener">
          Website ↗
        </a>
      )}
    </div>
  );
}

// Another person's profile, with the safety/social actions: connect, block,
// report.
export default function PublicProfile() {
  const { userId } = useParams();
  const { user } = useAuth();
  const { data: profile, error, loading } = useApi(
    () => api.get(`/api/profiles/${userId}`),
    [userId],
  );
  const [status, setStatus] = useState(null);
  const [dialog, setDialog] = useState(null); // "block" | "report" | null

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

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
    <div className="org narrow">
      <Link to="/connections" className="link-button" style={{ display: "inline-block", marginBottom: "22px" }}>
        ← Back to people
      </Link>

      <section className="card" style={{ padding: "32px", gap: "20px", position: "relative", overflow: "hidden" }}>
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            right: "-60px",
            top: "-60px",
            width: "200px",
            height: "200px",
            borderRadius: "50%",
            background: "var(--color-accent-2-100)",
          }}
        />
        <div style={{ position: "relative", display: "flex", gap: "22px", alignItems: "center", flexWrap: "wrap" }}>
          {imgSrc ? (
            <img className="avatar-img avatar-img-lg" src={imgSrc} alt="" />
          ) : (
            <span className="avatar-initial lg">{initial(profile.display_name)}</span>
          )}
          <div style={{ flex: 1, minWidth: "180px" }}>
            <h1 style={{ margin: "0 0 8px" }}>{profile.display_name}</h1>
            {profile.account_type === "organization" && (
              <OrgLine profile={profile} />
            )}
            {profile.open_to_help && (
              <span className="tag tag-help_request">Open to helping neighbors</span>
            )}
          </div>
          {!isMe &&
            (profile.account_type === "organization" ? (
              <FollowButton orgId={userId} />
            ) : (
              <button onClick={connect}>Connect</button>
            ))}
        </div>

        {profile.bio && (
          <p style={{ position: "relative", margin: 0, fontSize: "15.5px", lineHeight: 1.65, color: "color-mix(in srgb, var(--color-text) 84%, transparent)" }}>
            {profile.bio}
          </p>
        )}
        {profile.account_type === "organization" &&
          (profile.org_phone || profile.org_address) && (
            <p className="muted org-contact" style={{ position: "relative", margin: 0 }}>
              {[profile.org_address, profile.org_phone].filter(Boolean).join(" · ")}
            </p>
          )}

        <div style={{ position: "relative" }}>
          <TrustBadge userId={userId} />
        </div>

        {status && <div className="muted" style={{ position: "relative" }}>{status}</div>}

        {!isMe && (
          <div style={{ position: "relative", display: "flex", gap: "16px", marginTop: "4px" }}>
            <button className="link-button" onClick={() => setDialog("block")}>
              Block
            </button>
            <button className="link-button" onClick={() => setDialog("report")}>
              Report
            </button>
          </div>
        )}
      </section>

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
