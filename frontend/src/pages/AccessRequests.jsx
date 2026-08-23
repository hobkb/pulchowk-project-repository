import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faInbox, faSpinner } from "@fortawesome/free-solid-svg-icons";
import { accessRequestsApi } from "../api/client";
import { useNotifications } from "../context/NotificationsContext";
import {
  Breadcrumb,
  Button,
  Container,
  Crumb,
  EmptyState,
  ErrorNotice,
  LoadingRows,
  PageHeading,
  Pagination,
  Status,
} from "../components/ui";

/**
 * Report access requests, for reviewers.
 *
 * Every request from a reader lands here and notifies all administrators;
 * any one of them can decide it. Approving unlocks the report for that
 * reader immediately and notifies them — there is no email anywhere in
 * this flow.
 */

const FILTERS = [
  { label: "Pending", value: "PENDING" },
  { label: "Approved", value: "APPROVED" },
  { label: "Declined", value: "DECLINED" },
  { label: "All", value: "" },
];

const STATUS_TONE = { PENDING: "warn", APPROVED: "ok", DECLINED: "bad" };

function formatWhen(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function AccessRequests() {
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deciding, setDeciding] = useState(null);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const { refreshUnreadCount } = useNotifications();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await accessRequestsApi.queue({
        ...(statusFilter ? { status: statusFilter } : {}),
        page,
      });
      setRows(body.data || []);
      setPagination(body.pagination || null);
    } catch (err) {
      setError(err.message);
      setRows([]);
      setPagination(null);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(row, decision) {
    if (deciding) return;
    setDeciding(row.id);
    setError(null);
    try {
      await accessRequestsApi.decide(row.id, decision);
      // Reflect it at once, then reconcile with the server.
      setRows((current) =>
        current.map((r) =>
          r.id === row.id
            ? { ...r, status: decision === "approve" ? "APPROVED" : "DECLINED" }
            : r
        )
      );
      refreshUnreadCount();
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeciding(null);
    }
  }

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb>Administration</Crumb>
        <Crumb last>Access requests</Crumb>
      </Breadcrumb>

      <Container width="normal" className="px-5 sm:px-8 py-8">
        <PageHeading
          title="Report access requests"
          lead="Approving a request opens that report to that reader immediately."
        />

        <div className="mt-6 flex flex-wrap gap-x-6 gap-y-1 border-b border-line">
          {FILTERS.map((option) => {
            const selected = statusFilter === option.value;
            return (
              <button
                key={option.label}
                type="button"
                aria-pressed={selected}
                onClick={() => {
                  setStatusFilter(option.value);
                  setPage(1);
                }}
                className={`-mb-px cursor-pointer border-b-[3px] pb-2 text-sm transition-colors ${
                  selected
                    ? "border-b-ochre font-semibold text-nav"
                    : "border-b-transparent text-ink-2 hover:text-ink"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>

        <div className="mt-6">
          {loading && <LoadingRows rows={4} />}

          {!loading && error && (
            <ErrorNotice
              title="Requests could not be loaded"
              detail={error}
              action={
                <Button variant="secondary" size="sm" onClick={load}>
                  Try again
                </Button>
              }
            />
          )}

          {!loading && !error && rows.length === 0 && (
            <EmptyState
              icon={faInbox}
              title="Nothing here"
              description="Requests from readers for a project's full report will appear here."
            />
          )}

          {!loading && !error && rows.length > 0 && (
            <ul className="divide-y divide-line border-y border-line">
              {rows.map((row) => (
                <li key={row.id} className="py-4">
                  <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
                    <div className="min-w-0">
                      <Link
                        to={`/projects/${row.project}`}
                        className="text-sm font-semibold"
                      >
                        {row.project_title}
                      </Link>
                      <p className="mt-0.5 text-sm text-ink-2">
                        {row.requester_name}{" "}
                        <span className="text-ink-3">&lt;{row.requester_email}&gt;</span>
                      </p>
                      <p className="mt-0.5 text-xs text-ink-3 tnum">
                        {formatWhen(row.created_at)}
                      </p>
                    </div>
                    <Status tone={STATUS_TONE[row.status] || "neutral"}>
                      {row.status.charAt(0) + row.status.slice(1).toLowerCase()}
                    </Status>
                  </div>

                  {row.reason && (
                    <p className="mt-2 border-l-2 border-line pl-3 text-sm text-ink-2 measure">
                      {row.reason}
                    </p>
                  )}

                  {row.status === "PENDING" && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => decide(row, "approve")}
                        disabled={deciding === row.id}
                      >
                        {deciding === row.id && (
                          <FontAwesomeIcon
                            icon={faSpinner}
                            className="h-3.5 w-3.5 spin"
                            aria-hidden="true"
                          />
                        )}
                        Approve
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => decide(row, "decline")}
                        disabled={deciding === row.id}
                      >
                        Decline
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {!loading && !error && pagination && (
            <Pagination
              page={pagination.page}
              totalPages={pagination.total_pages}
              totalCount={pagination.total_count}
              label="requests"
              onChange={setPage}
            />
          )}
        </div>
      </Container>
    </>
  );
}
