import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { HeartMark } from "./Logo.jsx";
import {
  NotificationsProvider,
  useNotifications,
} from "../context/NotificationsContext.jsx";

// ---- Icons (stroke, inherit color) ----------------------------------------
const ico = {
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};
const MapIcon = (p) => (
  <svg {...ico} className={p.className}>
    <path d="M12 21s-6-5.3-6-10a6 6 0 0 1 12 0c0 4.7-6 10-6 10Z" />
    <circle cx="12" cy="11" r="2.2" />
  </svg>
);
const PlusIcon = (p) => (
  <svg {...ico} className={p.className}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);
const CalIcon = (p) => (
  <svg {...ico} className={p.className}>
    <rect x="3.5" y="4.5" width="17" height="16" rx="2" />
    <path d="M3.5 9h17M8 2.5v4M16 2.5v4" />
  </svg>
);
const PeopleIcon = (p) => (
  <svg {...ico} className={p.className}>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3 20c0-3.2 2.7-5.2 6-5.2S15 16.8 15 20" />
    <path d="M16.5 6.6a3.2 3.2 0 0 1 0 5.6M18 14.9c1.9.7 3 2.2 3 4.1" />
  </svg>
);
const PersonIcon = (p) => (
  <svg {...ico} className={p.className}>
    <circle cx="12" cy="8" r="3.6" />
    <path d="M4.5 20.5c0-3.8 3.5-5.8 7.5-5.8s7.5 2 7.5 5.8" />
  </svg>
);
const BellIcon = (p) => (
  <svg {...ico} className={p.className}>
    <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" />
    <path d="M9.5 19a2.5 2.5 0 0 0 5 0" />
  </svg>
);
const OutIcon = (p) => (
  <svg {...ico} className={p.className}>
    <path d="M15 4h3.5a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H15" />
    <path d="M10 16.5 14.5 12 10 7.5M14.5 12H3.5" />
  </svg>
);

const NAV = [
  { to: "/map", label: "Map", Icon: MapIcon },
  { to: "/events/new", label: "Create", Icon: PlusIcon },
  { to: "/my-events", label: "Events", Icon: CalIcon },
  { to: "/connections", label: "People", Icon: PeopleIcon },
  { to: "/profile", label: "Profile", Icon: PersonIcon },
];

function railClass({ isActive }) {
  return isActive ? "rail-link active" : "rail-link";
}

// Compact bell for the mobile top bar (with unread badge).
function MobileBell() {
  const { unreadCount } = useNotifications();
  return (
    <NavLink to="/notifications" className="notif-bell" title="Notifications">
      <BellIcon />
      {unreadCount > 0 && (
        <span className="notif-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
      )}
    </NavLink>
  );
}

// Bell styled as a rail item for the desktop rail foot.
function RailBell() {
  const { unreadCount } = useNotifications();
  return (
    <NavLink to="/notifications" className={railClass}>
      <BellIcon className="rail-icon" />
      <span>Alerts</span>
      {unreadCount > 0 && (
        <span className="rail-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
      )}
    </NavLink>
  );
}

// The shell around every authenticated page: a vertical icon rail on desktop
// that becomes a bottom tab bar (plus a slim top bar) on mobile.
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
        <header className="mtop">
          <NavLink to="/" className="mtop-logo">
            <HeartMark size={22} title="Ours" />
            <span className="wordmark">Ours</span>
          </NavLink>
          <div className="mtop-right">
            <MobileBell />
            <button className="link-button" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </header>

        <nav className="rail" aria-label="Primary">
          <NavLink to="/" className="rail-logo" title="Ours">
            <HeartMark size={30} color="var(--on-accent)" title="Ours home" />
          </NavLink>
          <div className="rail-items">
            {NAV.map(({ to, label, Icon }) => (
              <NavLink key={to} to={to} className={railClass}>
                <Icon className="rail-icon" />
                <span>{label}</span>
              </NavLink>
            ))}
          </div>
          <div className="rail-foot">
            <RailBell />
            <button className="rail-link" onClick={handleLogout} title={user?.email}>
              <OutIcon className="rail-icon" />
              <span>Out</span>
            </button>
          </div>
        </nav>

        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </NotificationsProvider>
  );
}
