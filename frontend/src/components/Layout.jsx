import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import {
  NotificationsProvider,
  useNotifications,
} from "../context/NotificationsContext.jsx";

// A bell that links to the notifications page, badged with the unread count.
function NotificationBell() {
  const { unreadCount } = useNotifications();
  return (
    <NavLink to="/notifications" className="notif-bell" title="Notifications">
      <span aria-hidden="true">🔔</span>
      {unreadCount > 0 && (
        <span className="notif-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
      )}
    </NavLink>
  );
}

// The shell around every authenticated page: a top nav plus the routed page
// in an <Outlet />.
export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <NotificationsProvider>
      <div className="app-shell">
        <header className="topnav">
          <NavLink to="/" className="brand">
            Ours
          </NavLink>
          <nav>
            <NavLink to="/map">Map</NavLink>
            <NavLink to="/events/new">Create</NavLink>
            <NavLink to="/my-events">Events</NavLink>
            <NavLink to="/connections">Connections</NavLink>
            <NavLink to="/profile">Profile</NavLink>
          </nav>
          <div className="topnav-right">
            <NotificationBell />
            <span className="muted">{user?.email}</span>
            <button className="link-button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </NotificationsProvider>
  );
}
