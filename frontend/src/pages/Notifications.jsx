import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useNotifications } from "../context/NotificationsContext.jsx";

function timeAgo(iso) {
  const seconds = Math.round((Date.now() - new Date(iso)) / 1000);
  const units = [
    ["d", 86400],
    ["h", 3600],
    ["m", 60],
  ];
  for (const [label, size] of units) {
    if (seconds >= size) return `${Math.floor(seconds / size)}${label} ago`;
  }
  return "just now";
}

// One icon per notification family, tinted from the ramps.
function NotifIcon({ type }) {
  const kind = type || "";
  let path = <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" />;
  let warm = false;
  if (kind.includes("invite")) {
    path = (
      <>
        <rect x="3" y="4" width="18" height="17" rx="2" />
        <path d="M3 9h18M8 2v4M16 2v4M9 15l2 2 4-4" />
      </>
    );
  } else if (kind.includes("rsvp") || kind.includes("message")) {
    path = <path d="M20 6 9 17l-5-5" />;
    warm = true;
  } else if (kind.includes("connection")) {
    path = (
      <>
        <circle cx="9" cy="8" r="3.2" />
        <path d="M3 20c0-3.2 2.7-5.2 6-5.2S15 16.8 15 20" />
        <path d="M16.5 6.6a3.2 3.2 0 0 1 0 5.6M18 14.9c1.9.7 3 2.2 3 4.1" />
      </>
    );
  } else if (kind.includes("cancel") || kind.includes("delete")) {
    path = <path d="M18 6 6 18M6 6l12 12" />;
    warm = true;
  }
  return (
    <span className={`avatar-initial sm ${warm ? "warm" : ""}`} aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        {path}
      </svg>
    </span>
  );
}

export default function Notifications() {
  const { data, error, loading, reload } = useApi(() => api.get("/api/notifications"));
  const { refresh } = useNotifications();

  useEffect(() => {
    api.post("/api/notifications/read").then(refresh).catch(() => {});
  }, [refresh]);

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

  async function markAllRead() {
    await api.post("/api/notifications/read").catch(() => {});
    await refresh();
    await reload();
  }

  return (
    <div className="org narrow">
      <div className="page-head">
        <div>
          <span className="kicker">What you missed</span>
          <h1>Alerts</h1>
        </div>
        {data.length > 0 && (
          <button className="link-button" onClick={markAllRead}>
            Mark all read
          </button>
        )}
      </div>

      {data.length === 0 ? (
        <p className="muted">
          Nothing yet. Invites, RSVPs, messages and cancellations will show up here.
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {data.map((n) => {
            const Row = n.link ? Link : "div";
            const rowProps = n.link ? { to: n.link } : {};
            return (
              <Row
                key={n.id}
                {...rowProps}
                className={n.is_read ? "notif-item" : "notif-item notif-unread"}
              >
                <NotifIcon type={n.type} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ margin: 0, fontSize: "15px", lineHeight: 1.45 }}>{n.message}</p>
                  <span className="notif-time">{timeAgo(n.created_at)}</span>
                </div>
                {!n.is_read && (
                  <span
                    aria-hidden="true"
                    style={{
                      flex: "none",
                      width: "9px",
                      height: "9px",
                      borderRadius: "50%",
                      background: "var(--color-accent)",
                    }}
                  />
                )}
              </Row>
            );
          })}
        </div>
      )}
    </div>
  );
}
