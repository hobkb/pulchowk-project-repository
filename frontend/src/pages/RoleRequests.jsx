import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faSpinner, faUserShield } from "@fortawesome/free-solid-svg-icons";
import { roleRequestsApi } from "../api/client";
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
  Status,
} from "../components/ui";

/**
 * Role requests, for administrators.
 *
 * Choosing "Faculty" or "Administrator" during onboarding grants nothing;
 * it files a request that lands here. Only a superuser can decide one,
 * because `is_staff` alone already makes someone a reviewer — letting
 * reviewers grant roles would let privilege spread without an
 * administrator ever being involved.
 */

const FILTERS = [
  { label: "Pending", value: "PENDING" },
  { label: "Approved", value: "APPROVED" },
  { label: "Declined", value: "DECLINED" },
  { label: "All", value: "" },
];

const STATUS_TONE = { PENDING: "warn", APPROVED: "ok", DECLINED: "bad" };

const ROLE_LABEL = {
  admin: "Administrator",
  faculty: "Faculty",
  student: "Student",
};

/** What approving actually turns on, stated rather than implied. */
const ROLE_GRANTS = {
  admin: "Full administrative access: verifying deposits, deciding access and role requests.",
  faculty: "Reviewer access: depositing and verifying project reports.",
};

function formatWhen(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function RoleRequests() {
  const [rows, setRows] = useState([]);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deciding, setDeciding] = useState(null);
  const { refreshUnreadCount } = useNotifications();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await roleRequestsApi.queue(
        statusFilter ? { status: statusFilter } : {}
      );
      setRows(body.data || []);
    } catch (err) {
      setError(err.message);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(row, decision) {
    if (deciding) return;
    setDeciding(row.id);
    setError(null);
    try {
      await roleRequestsApi.decide(row.id, decision);
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
        <Crumb last>Role requests</Crumb>
      </Breadcrumb>

      <Container width="normal" className="px-5 sm:px-8 py-8">
        <PageHeading
          title="Role requests"
          lead="People who asked for faculty or administrator access when they signed up. Until you approve one, the account stays an ordinary reader."
        />

        <div className="mt-6 flex flex-wrap gap-x-6 gap-y-1 border-b border-line">
          {FILTERS.map((option) => {
            const selected = statusFilter === option.value;
            return (
              <button
                key={option.label}
                type="button"
                aria-pressed={selected}
                onClick={() => setStatusFilter(option.value)}
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
              title="Role requests could not be loaded"
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
              icon={faUserShield}
              title="Nothing here"
              description="Requests for faculty or administrator access will appear here."
            />
          )}

          {!loading && !error && rows.length > 0 && (
            <ul className="divide-y divide-line border-y border-line">
              {rows.map((row) => (
                <li key={row.id} className="py-4">
                  <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-ink">{row.user_name}</p>
                      <p className="mt-0.5 text-sm text-ink-3">{row.user_email}</p>
                      <p className="mt-0.5 text-xs text-ink-3 tnum">
                        {formatWhen(row.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Status tone="info">
                        {ROLE_LABEL[row.requested_role] || row.requested_role}
                      </Status>
                      <Status tone={STATUS_TONE[row.status] || "neutral"}>
                        {row.status.charAt(0) + row.status.slice(1).toLowerCase()}
                      </Status>
                    </div>
                  </div>

                  {ROLE_GRANTS[row.requested_role] && (
                    <p className="mt-2 text-sm text-ink-2 measure">
                      {ROLE_GRANTS[row.requested_role]}
                    </p>
                  )}

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
                            className="h-3.5 w-3.5 animate-spin"
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
        </div>
      </Container>
    </>
  );
}
