import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setToken, getToken, setUnauthorizedHandler } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // "loading" until we've checked for an existing token on first mount, so
  // protected routes don't flash the login page on a hard refresh.
  const [loading, setLoading] = useState(true);

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  // Any 401 anywhere in the app funnels here.
  useEffect(() => {
    setUnauthorizedHandler(clearSession);
  }, [clearSession]);

  const loadUser = useCallback(async () => {
    try {
      const me = await api.get("/api/users/me");
      setUser(me);
    } catch {
      clearSession();
    }
  }, [clearSession]);

  useEffect(() => {
    if (getToken()) {
      loadUser().finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [loadUser]);

  async function login(email, password) {
    const { access_token } = await api.post(
      "/api/auth/login",
      { email, password },
      { auth: false },
    );
    setToken(access_token);
    await loadUser();
  }

  async function register(email, password, displayName) {
    await api.post(
      "/api/auth/register",
      { email, password, display_name: displayName },
      { auth: false },
    );
    await login(email, password);
  }

  async function logout() {
    try {
      await api.post("/api/auth/logout");
    } catch {
      // Even if the call fails, drop the token locally.
    }
    clearSession();
  }

  const value = { user, loading, login, register, logout, refreshUser: loadUser };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
