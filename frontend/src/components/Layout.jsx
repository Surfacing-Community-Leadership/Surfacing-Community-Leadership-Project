import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

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
  );
}
