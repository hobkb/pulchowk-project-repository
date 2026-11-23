import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { faBell, faSpinner, faTrash } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { notificationsApi } from "../api/client";
import { useToast } from "../context/ToastContext";
import {
  notificationLabel,
  notificationTarget,
  notificationTone,
  relativeTime,
  useNotifications,
} from "../context/NotificationsContext";
import {
  Breadcrumb,
  Button,
  Container,
  Crumb,
  Dialog,
  EmptyState,
  ErrorNotice,
  LoadingRows,
  PageHeading,
  Status,
} from "../components/ui";

/**
 * Notifications.
 *
 * Every row is a real record from the notifications API, raised by an
 * actual ingestion event. The backend scopes the list to the requesting
 * user, so this page can only ever show that user's own notifications.
 * Paging follows the `next` link the API itself returns.
 */

function formatTimestamp(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function Notifications() {
  const [items, setItems] = useState([]);
  const [nextPage, setNextPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const { unreadCount, markRead, markAllRead, clearAll, refreshUnreadCount } = useNotifications();
  const { showToast } = useToast();
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [clearing, setClearing] = useState(false);

  const load = useCallback(async (page) => {
    const body = await notificationsApi.list(page ? { page } : {});
    return {
      results: body?.results || [],
      next: body?.next ? new URL(body.next).searchParams.get("page") : null,
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    load()
      .then(({ results, next }) => {
        if (cancelled) return;
        setItems(results);
        setNextPage(next);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    refreshUnreadCount();
    return () => {
      cancelled = true;
    };
  }, [load, refreshUnreadCount]);

  async function loadMore() {
    if (!nextPage || loadingMore) return;
    setLoadingMore(true);
    try {
      const { results, next } = await load(nextPage);
      setItems((previous) => [...previous, ...results]);
      setNextPage(next);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingMore(false);
    }
  }

  async function open(notification) {
    if (!notification.is_read) {
      setItems((previous) =>
        previous.map((item) => (item.id === notification.id ? { ...item, is_read: true } : item))
      );
      await markRead(notification.id);
    }
    const target = notificationTarget(notification);
    if (target) navigate(target);
  }

  async function handleMarkAllRead() {
    setItems((previous) => previous.map((item) => ({ ...item, is_read: true })));
    await markAllRead();
  }

  async function handleClearAll() {
    if (clearing) return;
    setClearing(true);
    try {
      await clearAll();
      setItems([]);
      setNextPage(null);
      setConfirmingClear(false);
      showToast("Notifications cleared.");
    } catch (err) {
      setError(err.message);
    } finally {
      setClearing(false);
    }
  }

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb last>Notifications</Crumb>
      </Breadcrumb>

      <Container width="normal" className="px-5 sm:px-8 py-8">
        <PageHeading
          title="Notifications"
          actions={
            <div className="flex flex-wrap gap-2">
              {unreadCount > 0 && (
                <Button variant="secondary" size="sm" onClick={handleMarkAllRead}>
                  Mark all as read
                </Button>
              )}
              {items.length > 0 && (
                <Button variant="subtle" size="sm" onClick={() => setConfirmingClear(true)}>
                  <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" aria-hidden="true" />
                  Clear all
                </Button>
              )}
            </div>
          }
        />

        <Dialog
          open={confirmingClear}
          onClose={() => !clearing && setConfirmingClear(false)}
          title="Clear all notifications?"
          description="This permanently deletes every notification you have. It cannot be undone."
          width="max-w-md"
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirmingClear(false)} disabled={clearing}>
                Cancel
              </Button>
              <Button variant="danger" onClick={handleClearAll} disabled={clearing}>
                {clearing && (
                  <FontAwesomeIcon icon={faSpinner} className="h-3.5 w-3.5 spin" aria-hidden="true" />
                )}
                {clearing ? "Clearing…" : "Clear all"}
              </Button>
            </>
          }
        />

        <div className="mt-6">
          {loading && <LoadingRows rows={5} />}

          {!loading && error && (
            <ErrorNotice
              title="Notifications could not be loaded"
              detail={error}
              action={
                <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
                  Try again
                </Button>
              }
            />
          )}

          {!loading && !error && items.length === 0 && (
            <EmptyState
              icon={faBell}
              title="No notifications"
              description="When a report you deposited finishes processing, needs verification, or is published, it will be listed here."
              action={
                <Button as={Link} to="/projects" variant="secondary" size="sm">
                  Browse projects
                </Button>
              }
            />
          )}

          {!loading && !error && items.length > 0 && (
            <>
              <ul className="divide-y divide-line border-y border-line">
                {items.map((notification) => {
                  const target = notificationTarget(notification);
                  const body = (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1.5">
                        <Status tone={notificationTone(notification.notification_type)}>
                          {notificationLabel(notification.notification_type)}
                        </Status>
                        <span className="flex shrink-0 items-center gap-3">
                          {!notification.is_read && (
                            <span className="rounded-sm bg-accent-050 px-1.5 py-0.5 text-xs font-semibold text-accent">
                              Unread
                            </span>
                          )}
                          <time
                            dateTime={notification.created_at}
                            title={formatTimestamp(notification.created_at)}
                            className="text-xs text-ink-3 tnum"
                          >
                            {relativeTime(notification.created_at)}
                          </time>
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm text-ink">{notification.message}</p>
                      {target && (
                        <p className="mt-1 text-xs text-link">
                          {notification.project ? "Open project" : "Open deposit"}
                        </p>
                      )}
                    </>
                  );

                  return (
                    <li key={notification.id} className={notification.is_read ? "" : "bg-primary-050"}>
                      {target ? (
                        <button
                          type="button"
                          onClick={() => open(notification)}
                          className="w-full cursor-pointer px-4 py-3.5 text-left transition-colors hover:bg-band"
                        >
                          {body}
                        </button>
                      ) : (
                        <div className="px-4 py-3.5">{body}</div>
                      )}
                    </li>
                  );
                })}
              </ul>

              {nextPage && (
                <div className="mt-5 flex justify-center">
                  <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
                    {loadingMore ? "Loading…" : "Load older notifications"}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </Container>
    </>
  );
}
