import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client.js";

// Holds the unread-notification count for the whole authenticated shell: the
// bell badge reads it, and the Notifications page calls refresh() after marking
// things read so the badge clears immediately instead of waiting for the poll.
const NotificationsContext = createContext(null);

export function NotificationsProvider({ children }) {
  const [unreadCount, setUnreadCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const { count } = await api.get("/api/notifications/unread-count");
      setUnreadCount(count);
    } catch {
      // Ignore — a failed count check shouldn't disrupt the app.
    }
  }, []);

  // Fetch once on mount, then poll so the badge stays roughly current.
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 60000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <NotificationsContext.Provider value={{ unreadCount, refresh }}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications must be used inside NotificationsProvider");
  return ctx;
}
