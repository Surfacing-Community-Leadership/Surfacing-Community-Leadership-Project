import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { useState } from "react";

export default function Connections() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi(async () => {
    const [friends, requests] = await Promise.all([
      api.get("/api/connections"),
      api.get("/api/connections/requests"),
    ]);
    // Requests carry only ids; resolve the *other* person's name for each.
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

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

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
    <div className="narrow">
      <h1>Connections</h1>
      {actionError && <div className="alert">{actionError}</div>}

      <section className="card">
        <h2>Requests</h2>
        {data.requests.length === 0 && <p className="muted">No pending requests.</p>}
        <ul className="plain-list">
          {data.requests.map((r) => (
            <li key={r.id} className="invite-row">
              <Link to={`/profile/${r.otherId}`}>{r.name}</Link>
              <span className="row-actions">
                {r.iAmAddressee ? (
                  <>
                    <button onClick={() => accept(r.id)}>Accept</button>
                    <button className="secondary" onClick={() => remove(r.id)}>
                      Decline
                    </button>
                  </>
                ) : (
                  <button className="secondary" onClick={() => remove(r.id)}>
                    Cancel request
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Your connections</h2>
        {data.friends.length === 0 && (
          <p className="muted">
            None yet. Visit someone's profile from an event to connect.
          </p>
        )}
        <ul className="plain-list">
          {data.friends.map((f) => (
            <li key={f.id} className="invite-row">
              <Link to={`/profile/${f.user_id}`}>{f.display_name}</Link>
              <button className="secondary" onClick={() => remove(f.id)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
