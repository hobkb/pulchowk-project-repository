import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { notificationsApi } from "../api/client";
import { useAuth } from "./AuthContext";

const NotificationsContext = createContext(null);

/** How often the unread count is re-checked while the tab is visible.
 *  Ingestion is a background Celery job, so a notification can arrive
 *  without the user navigating; polling is the honest, minimal way to
 *  surface that without adding a websocket layer this app does not have. */
const POLL_INTERVAL_MS = 60_000;

export function NotificationsProvider({ children }) {
  const { status } = useAuth();
  const isSignedIn = status === "authenticated";

  const [unreadCount, setUnreadCount] = useState(0);
  const [countError, setCountError] = useState(null);
  const pollRef = useRef(null);

  const refreshUnreadCount = useCallback(async () => {
    if (!isSignedIn) return;
    try {
      const body = await notificationsApi.unreadCount();
      setUnreadCount(body?.data?.count ?? 0);
      setCountError(null);
    } catch (err) {
      // A failing count must never break the page chrome around it — the
      // indicator simply stops updating, and the notifications page shows
      // the real error when the user goes looking.
      setCountError(err.message);
    }
  }, [isSignedIn]);

  useEffect(() => {
    if (!isSignedIn) {
      setUnreadCount(0);
      return undefined;
    }

    refreshUnreadCount();

    function start() {
      stop();
      pollRef.current = setInterval(refreshUnreadCount, POLL_INTERVAL_MS);
    }
    function stop() {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    function handleVisibility() {
      if (document.hidden) {
        stop();
      } else {
        refreshUnreadCount();
        start();
      }
    }

    if (!document.hidden) start();
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stop();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [isSignedIn, refreshUnreadCount]);

  /** Optimistically drop the badge, then reconcile with the server. */
  const markRead = useCallback(
    async (id) => {
      setUnreadCount((n) => Math.max(0, n - 1));
      try {
        await notificationsApi.markRead(id);
      } finally {
        refreshUnreadCount();
      }
    },
    [refreshUnreadCount]
  );

  const markAllRead = useCallback(async () => {
    setUnreadCount(0);
    try {
      await notificationsApi.markAllRead();
    } finally {
      refreshUnreadCount();
    }
  }, [refreshUnreadCount]);

  const value = useMemo(
    () => ({ unreadCount, countError, refreshUnreadCount, markRead, markAllRead }),
    [unreadCount, countError, refreshUnreadCount, markRead, markAllRead]
  );

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) {
    throw new Error("useNotifications must be used inside a NotificationsProvider");
  }
  return ctx;
}

/**
 * Where a notification points. Kept next to the provider so the bell
 * dropdown and the full notifications page can never disagree about a
 * destination — and so each type maps to a route that genuinely exists.
 */
export function notificationTarget(notification) {
  // An access request is something a reviewer has to ACT on, so it points
  // at the queue where it can be decided rather than at the project page.
  if (notification.notification_type === "ACCESS_REQUESTED") {
    return "/admin/access-requests";
  }
  // Likewise a role request: only an administrator can act on it, and the
  // queue is where that happens.
  if (notification.notification_type === "ROLE_REQUESTED") {
    return "/admin/role-requests";
  }
  // A decision on your own role changes what you can do, so it points at
  // the account page where the new role is shown.
  if (
    notification.notification_type === "ROLE_APPROVED" ||
    notification.notification_type === "ROLE_DECLINED"
  ) {
    return "/settings";
  }
  if (notification.project) return `/projects/${notification.project}`;
  if (notification.job) return `/admin/jobs/${notification.job}`;
  return null;
}

export function notificationTone(type) {
  switch (type) {
    case "JOB_FAILED":
      return "bad";
    case "JOB_AWAITING_ADMIN":
      return "wait";
    case "JOB_PUBLISHED":
    case "ACCESS_APPROVED":
    case "ROLE_APPROVED":
      return "ok";
    case "ACCESS_DECLINED":
    case "ROLE_DECLINED":
      return "bad";
    case "ACCESS_REQUESTED":
    case "ROLE_REQUESTED":
      return "wait";
    default:
      return "info";
  }
}

export function notificationLabel(type) {
  switch (type) {
    case "JOB_READY_FOR_REVIEW":
      return "Ready for review";
    case "JOB_AWAITING_ADMIN":
      return "Awaiting review";
    case "JOB_FAILED":
      return "Processing failed";
    case "JOB_PUBLISHED":
      return "Published";
    case "ACCESS_REQUESTED":
      return "Access requested";
    case "ACCESS_APPROVED":
      return "Access approved";
    case "ACCESS_DECLINED":
      return "Access declined";
    case "ROLE_REQUESTED":
      return "Role requested";
    case "ROLE_APPROVED":
      return "Role approved";
    case "ROLE_DECLINED":
      return "Role declined";
    default:
      return "Notice";
  }
}

/** "3 minutes ago" — relative time, built from the real created_at. */
export function relativeTime(isoString) {
  if (!isoString) return "";
  const then = new Date(isoString);
  if (Number.isNaN(then.getTime())) return "";
  const seconds = Math.round((Date.now() - then.getTime()) / 1000);
  if (seconds < 60) return "just now";

  const units = [
    ["minute", 60],
    ["hour", 3600],
    ["day", 86400],
    ["week", 604800],
    ["month", 2592000],
    ["year", 31536000],
  ];
  let label = "year";
  let value = seconds / 31536000;
  for (let i = 0; i < units.length; i += 1) {
    const [name, size] = units[i];
    const next = units[i + 1];
    if (!next || seconds < next[1]) {
      label = name;
      value = Math.floor(seconds / size);
      break;
    }
  }
  return `${value} ${label}${value === 1 ? "" : "s"} ago`;
}
