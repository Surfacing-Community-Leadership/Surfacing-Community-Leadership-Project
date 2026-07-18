import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useNotifications } from "../context/NotificationsContext.jsx";

// Turns an ISO timestamp into a short "3h ago" style label.
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

export default function Notifications() {
  const { data, error, loading } = useApi(() => api.get("/api/notifications"));
  const { refresh } = useNotifications();

  // Opening the page counts as reading everything; clear the badge afterward.
  useEffect(() => {
    api
      .post("/api/notifications/read")
      .then(refresh)
      .catch(() => {});
  }, [refresh]);

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

  return (
    <div className="narrow">
      <h1>Notifications</h1>
      {data.length === 0 ? (
        <p className="muted">
          Nothing yet. Invites, RSVPs, messages and cancellations will show up here.
        </p>
      ) : (
        <ul className="plain-list">
          {data.map((n) => (
            <li key={n.id} className={n.is_read ? "notif-item" : "notif-item notif-unread"}>
              {n.link ? (
                <Link to={n.link}>{n.message}</Link>
              ) : (
                <span>{n.message}</span>
              )}
              <span className="muted notif-time">{timeAgo(n.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
