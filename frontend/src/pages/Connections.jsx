import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { useState } from "react";
import FollowButton from "../components/FollowButton.jsx";

function initial(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}
// Alternate the two accent tints so a list of avatars has some rhythm.
function tint(seed) {
  return (String(seed).charCodeAt(0) || 0) % 2 ? "warm" : "";
}

export default function Connections() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi(async () => {
    const [friends, requests] = await Promise.all([
      api.get("/api/connections"),
      api.get("/api/connections/requests"),
    ]);
    const withNames = await Promise.all(
      requests.map(async (r) => {
        const otherId = r.requester_id === user.id ? r.addressee_id : r.requester_id;
        let name = otherId;
        try {
          name = (await api.get(`/api/profiles/${otherId}`)).display_name;
        } catch {
          /* fall back to id */
        }
        return { ...r, otherId, name, iAmAddressee: r.addressee_id === user.id };
      }),
    );
    return { friends, requests: withNames };
  });

  const [actionError, setActionError] = useState(null);
  const [tab, setTab] = useState("people"); // "people" | "orgs"

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

  async function act(fn) {
    setActionError(null);
    try {
      await fn();
      await reload();
    } catch (err) {
      setActionError(err.message);
    }
  }

  const accept = (id) => act(() => api.patch(`/api/connections/${id}`, { status: "accepted" }));
  const remove = (id) => act(() => api.del(`/api/connections/${id}`));

  return (
    <div className="org wide">
      <span className="kicker">Your neighborhood</span>
      <h1>People &amp; organizations</h1>

      <div className="pill-tabs" style={{ marginBottom: "24px" }}>
        <button
          className={tab === "people" ? "pill-tab on" : "pill-tab"}
          onClick={() => setTab("people")}
        >
          Neighbors
        </button>
        <button
          className={tab === "orgs" ? "pill-tab on" : "pill-tab"}
          onClick={() => setTab("orgs")}
        >
          Organizations
        </button>
      </div>
      {actionError && <div className="alert" style={{ marginTop: "16px" }}>{actionError}</div>}

      {tab === "orgs" && <OrganizationsPanel />}

      {tab === "people" && <PeopleSearch onConnected={reload} />}

      {tab === "people" && data.requests.length > 0 && (
        <section style={{ marginBottom: "32px" }}>
          <h2 style={{ fontSize: "18px" }}>Pending requests</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {data.requests.map((r) => (
              <div
                key={r.id}
                className="card row-card"
                style={{ background: "var(--color-accent-100)", padding: "16px 20px", marginBottom: 0 }}
              >
                <span className={`avatar-initial ${tint(r.name)}`}>{initial(r.name)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <Link to={`/profile/${r.otherId}`} style={{ fontWeight: 700, textDecoration: "none" }}>
                    {r.name}
                  </Link>
                  <div className="muted" style={{ fontSize: "13px" }}>
                    {r.iAmAddressee ? "Wants to connect" : "Request sent"}
                  </div>
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  {r.iAmAddressee ? (
                    <>
                      <button onClick={() => accept(r.id)} style={{ fontSize: "13px", padding: "8px 16px" }}>
                        Accept
                      </button>
                      <button className="secondary" onClick={() => remove(r.id)} style={{ fontSize: "13px", padding: "8px 16px" }}>
                        Decline
                      </button>
                    </>
                  ) : (
                    <button className="secondary" onClick={() => remove(r.id)} style={{ fontSize: "13px", padding: "8px 16px" }}>
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {tab === "people" && (
      <section>
        <h2 style={{ fontSize: "18px" }}>Your connections</h2>
        {data.friends.length === 0 ? (
          <p className="muted">
            None yet. Search for someone above, or visit a profile from an event.
          </p>
        ) : (
          <div className="card-grid">
            {data.friends.map((f) => (
              <div key={f.id} className="card" style={{ alignItems: "flex-start", gap: "12px", padding: "22px" }}>
                <span className={`avatar-initial ${tint(f.display_name)}`}>{initial(f.display_name)}</span>
                <strong style={{ fontSize: "16px" }}>{f.display_name}</strong>
                <div style={{ display: "flex", gap: "8px", alignSelf: "stretch" }}>
                  <Link
                    to={`/profile/${f.user_id}`}
                    className="btn secondary"
                    style={{ flex: 1, justifyContent: "center", fontSize: "13px", padding: "8px 16px" }}
                  >
                    View profile
                  </Link>
                  <button className="link-button" onClick={() => remove(f.id)} style={{ fontSize: "13px" }}>
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
      )}
    </div>
  );
}

// Local institutions you can follow. Following one means hearing about what it
// posts — see the org_event notification.
function OrganizationsPanel() {
  const { data, error, loading, reload } = useApi(() =>
    api.get("/api/organizations"),
  );

  if (loading) return <p className="muted">Loading organizations…</p>;
  if (error) return <div className="alert">{error}</div>;
  if (data.length === 0) {
    return (
      <p className="muted">
        No organizations yet. Libraries, schools, parks departments and
        nonprofits can create an account from the sign-up page.
      </p>
    );
  }

  const following = data.filter((o) => o.following);
  const rest = data.filter((o) => !o.following);

  return (
    <>
      {following.length > 0 && (
        <section style={{ marginBottom: "32px" }}>
          <h2 style={{ fontSize: "18px" }}>You follow</h2>
          <div className="card-grid">
            {following.map((org) => (
              <OrgCard key={org.user_id} org={org} onChange={reload} />
            ))}
          </div>
        </section>
      )}
      <section>
        <h2 style={{ fontSize: "18px" }}>
          {following.length > 0 ? "More in your area" : "Organizations in your area"}
        </h2>
        <div className="card-grid">
          {rest.map((org) => (
            <OrgCard key={org.user_id} org={org} onChange={reload} />
          ))}
        </div>
      </section>
    </>
  );
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

function OrgCard({ org, onChange }) {
  return (
    <div className="card" style={{ gap: "12px", padding: "22px", alignItems: "flex-start" }}>
      <span className="avatar-initial warm">{initial(org.display_name)}</span>
      <div>
        <Link to={`/profile/${org.user_id}`} style={{ fontWeight: 700, textDecoration: "none" }}>
          {org.display_name}
        </Link>
        <div className="org-line" style={{ marginTop: "6px" }}>
          <span className="tag tag-gathering">
            {ORG_LABELS[org.org_category] || "Organization"}
          </span>
          {org.verified ? (
            <span className="trust-verified">✓ Verified</span>
          ) : (
            <span className="org-unverified">Unverified</span>
          )}
        </div>
      </div>
      {org.bio && (
        <p className="muted" style={{ margin: 0, fontSize: "13.5px" }}>
          {org.bio}
        </p>
      )}
      <FollowButton orgId={org.user_id} onChange={onChange} />
    </div>
  );
}

function PeopleSearch({ onConnected }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [status, setStatus] = useState(null);
  const [searching, setSearching] = useState(false);

  async function search(e) {
    e.preventDefault();
    setStatus(null);
    setSearching(true);
    try {
      setResults(await api.get(`/api/profiles?q=${encodeURIComponent(q)}`));
    } catch (err) {
      setStatus(err.message);
    } finally {
      setSearching(false);
    }
  }

  async function connect(person) {
    setStatus(null);
    try {
      await api.post("/api/connections", { addressee_id: person.user_id });
      setStatus(`Request sent to ${person.display_name}.`);
      onConnected?.();
    } catch (err) {
      setStatus(err.message);
    }
  }

  return (
    <section className="card" style={{ marginBottom: "32px" }}>
      <h2 style={{ fontSize: "20px", margin: 0 }}>Find people</h2>
      <form className="message-form" onSubmit={search}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search neighbors by name…"
          minLength={2}
          required
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={searching}>
          {searching ? "Searching…" : "Search"}
        </button>
      </form>
      {status && <p className="muted" style={{ margin: 0 }}>{status}</p>}
      {results && results.length === 0 && (
        <p className="muted" style={{ margin: 0 }}>No one found by that name.</p>
      )}
      {results && results.length > 0 && (
        <ul className="plain-list">
          {results.map((p) => (
            <li key={p.user_id} className="invite-row">
              <span style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
                <span className={`avatar-initial sm ${tint(p.display_name)}`}>{initial(p.display_name)}</span>
                <Link to={`/profile/${p.user_id}`} style={{ textDecoration: "none", fontWeight: 600 }}>
                  {p.display_name}
                </Link>
              </span>
              <button className="secondary" onClick={() => connect(p)} style={{ fontSize: "13px", padding: "8px 16px" }}>
                Connect
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
