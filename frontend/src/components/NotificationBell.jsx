import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBell } from "@fortawesome/free-solid-svg-icons";
import { notificationsApi } from "../api/client";
import {
  notificationLabel,
  notificationTarget,
  notificationTone,
  relativeTime,
  useNotifications,
} from "../context/NotificationsContext";
import { Button, Status } from "./ui";

/**
 * The masthead notice indicator. Everything it shows comes from the real
 * notifications API — the count from /unread-count/, the list from the
 * paginated list endpoint, fetched when the panel is opened rather than
 * kept permanently in memory.
 */
export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const wrapRef = useRef(null);
  const navigate = useNavigate();
  const { unreadCount, markRead, markAllRead } = useNotifications();

  useEffect(() => {
    if (!open) return undefined;

    let cancelled = false;
    setLoading(true);
    setError(null);
    notificationsApi
      .list({ page_size: 6 })
      .then((body) => {
        if (!cancelled) setItems(body?.results || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;

    function onPointerDown(event) {
      if (!wrapRef.current?.contains(event.target)) setOpen(false);
    }
    function onKeyDown(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function openNotification(notification) {
    setOpen(false);
    if (!notification.is_read) await markRead(notification.id);
    const target = notificationTarget(notification);
    navigate(target || "/notifications");
  }

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={
          unreadCount > 0
            ? `Notifications, ${unreadCount} unread`
            : "Notifications, none unread"
        }
        className="relative flex items-center gap-1.5 rounded-sm px-2 py-1.5 text-ink-2 hover:bg-band hover:text-ink transition-colors cursor-pointer"
      >
        <FontAwesomeIcon icon={faBell} className="h-4 w-4" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="rounded-sm bg-accent px-1.5 py-px text-xs font-bold leading-tight text-white tnum">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Recent notifications"
          className="absolute right-0 top-full z-50 mt-1 flex w-[min(24rem,calc(100vw-2rem))] flex-col rounded-md border border-line bg-white shadow-pop pop-in"
        >
          <div className="flex items-center justify-between gap-3 rounded-t-md border-b border-line bg-band px-4 py-2.5">
            <h2 className="text-sm font-semibold text-ink">Notifications</h2>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => {
                  markAllRead();
                  setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
                }}
                className="text-xs font-semibold text-link hover:text-link-hover cursor-pointer"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[24rem] divide-y divide-line overflow-y-auto">
            {loading && (
              <div className="px-4 py-6 flex flex-col gap-3" aria-hidden="true">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="flex flex-col gap-1.5">
                    <div className="skeleton h-3 w-20 rounded-sm" />
                    <div className="skeleton h-3.5 w-full rounded-sm" />
                  </div>
                ))}
              </div>
            )}

            {!loading && error && (
              <p className="px-4 py-6 text-sm text-err">{error}</p>
            )}

            {!loading && !error && items.length === 0 && (
              <p className="px-4 py-8 text-center text-sm text-ink-3">
                No notifications yet. You will be told here when a deposit finishes processing.
              </p>
            )}

            {!loading &&
              !error &&
              items.map((notification) => (
                <button
                  key={notification.id}
                  type="button"
                  onClick={() => openNotification(notification)}
                  className={`flex w-full cursor-pointer flex-col gap-1.5 px-4 py-3 text-left transition-colors hover:bg-band ${
                    notification.is_read ? "" : "bg-primary-050"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <Status tone={notificationTone(notification.notification_type)}>
                      {notificationLabel(notification.notification_type)}
                    </Status>
                    <span className="shrink-0 text-xs text-ink-3 tnum">
                      {relativeTime(notification.created_at)}
                    </span>
                  </div>
                  <p className="text-sm leading-snug text-ink-2">{notification.message}</p>
                </button>
              ))}
          </div>

          <div className="rounded-b-md border-t border-line bg-band p-2.5">
            <Button
              as={Link}
              to="/notifications"
              variant="secondary"
              size="sm"
              className="w-full"
              onClick={() => setOpen(false)}
            >
              View all notifications
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
