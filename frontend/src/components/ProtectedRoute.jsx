import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

// Gate for authenticated pages. While the initial token check runs we show
// nothing (avoids a login-page flash on refresh); after that, either render
// the page or redirect to /login, remembering where the user was headed.
export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="centered muted">Loading…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}
