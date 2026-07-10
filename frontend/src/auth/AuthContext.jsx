import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setUnauthorizedHandler } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // "loading" until the initial session check finishes, so protected routes
  // don't flash the login page on a hard refresh.
  const [loading, setLoading] = useState(true);

  // Any 401 anywhere in the app funnels here.
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
  }, []);

  const loadUser = useCallback(async () => {
    try {
      setUser(await api.get("/api/users/me"));
    } catch {
      setUser(null);
    }
  }, []);

  // On mount, ask the backend who we are. If the httpOnly cookie is present
  // and valid this succeeds; otherwise we're logged out. The cookie itself
  // is invisible to this code — only the server can read it.
  useEffect(() => {
    loadUser().finally(() => setLoading(false));
  }, [loadUser]);

  async function login(email, password) {
    await api.post("/api/auth/login", { email, password }); // sets the cookie
    await loadUser();
  }

  async function register(email, password, displayName) {
    await api.post("/api/auth/register", {
      email,
      password,
      display_name: displayName,
    });
    await login(email, password);
  }

  async function logout() {
    try {
      await api.post("/api/auth/logout"); // clears the cookie server-side
    } catch {
      // Even if the call fails, drop local state.
    }
    setUser(null);
  }

  const value = { user, loading, login, register, logout, refreshUser: loadUser };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
