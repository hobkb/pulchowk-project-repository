import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faChevronLeft, faChevronRight, faListCheck } from "@fortawesome/free-solid-svg-icons";
import { ingestionApi } from "../api/client";
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
  Table,
  TableBody,
  TableHead,
  Td,
  Th,
  Tr,
  statusRowAccent,
} from "../components/ui";

/**
 * The verification queue.
 *
 * Behaviour is unchanged: the same status filter, the same paginated
 * ingestion job list, the same link into the review workflow. Only the
 * presentation is new — a bordered table with a status accent down the
 * left of each row.
 */

const STATUS_META = {
  EXTRACTED: { tone: "info", label: "Awaiting verification" },
  PENDING: { tone: "neutral", label: "Queued" },
  PROCESSING: { tone: "warn", label: "Processing", pulse: true },
  VERIFIED: { tone: "ok", label: "Published" },
  SECTIONS_PENDING: { tone: "warn", label: "Sections incomplete" },
  DUPLICATE: { tone: "neutral", label: "Duplicate" },
  FAILED: { tone: "err", label: "Processing failed" },
};

function statusMeta(status) {
  return STATUS_META[status] || { tone: "neutral", label: status };
}

const FILTERS = [
  { label: "All", value: "ALL" },
  { label: "Awaiting verification", value: "EXTRACTED" },
  { label: "Queued", value: "PENDING" },
  { label: "Processing", value: "PROCESSING" },
  { label: "Published", value: "VERIFIED" },
  { label: "Sections incomplete", value: "SECTIONS_PENDING" },
  { label: "Failed", value: "FAILED" },
];

const PAGE_SIZE = 10;

export default function PendingApprovals() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function fetchJobs() {
      try {
        setLoading(true);
        setError(null);
        const params = {
          ...(selectedStatus !== "ALL" ? { status: selectedStatus } : {}),
          page,
        };
        const res = await ingestionApi.listJobs(params);
        if (cancelled) return;

        const list = Array.isArray(res?.data)
          ? res.data
          : Array.isArray(res?.results)
            ? res.results
            : Array.isArray(res)
              ? res
              : [];
        setJobs(list);

        const count = res?.count ?? list.length;
        setTotalCount(count);
        setTotalPages(Math.max(1, Math.ceil(count / PAGE_SIZE)));
      } catch (err) {
        if (!cancelled) setError(err.message || "Failed to load ingestion jobs.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchJobs();
    return () => {
      cancelled = true;
    };
  }, [selectedStatus, page, reloadKey]);

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb>Administration</Crumb>
        <Crumb last>Verification queue</Crumb>
      </Breadcrumb>

      <Container width="wide" className="px-5 sm:px-8 py-8">
        <PageHeading
          title="Verification queue"
          actions={
            <Button as={Link} to="/admin/upload" variant="primary" size="sm">
              Deposit a report
            </Button>
          }
        />

        <div className="mt-6 flex flex-wrap gap-x-6 gap-y-1 border-b border-line">
          {FILTERS.map((option) => {
            const selected = selectedStatus === option.value;
            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={selected}
                onClick={() => {
                  setPage(1);
                  setSelectedStatus(option.value);
                }}
                className={`-mb-px cursor-pointer border-b-[3px] pb-2 text-sm transition-colors ${
                  selected
                    ? "border-b-accent font-semibold text-primary"
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
              title="The queue could not be loaded"
              detail={error}
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setReloadKey((key) => key + 1)}
                >
                  Try again
                </Button>
              }
            />
          )}

          {!loading && !error && jobs.length === 0 && (
            <EmptyState
              icon={faListCheck}
              title={selectedStatus === "ALL" ? "No deposits yet" : "No deposits with this status"}
              description="Depositing a project report starts the extraction pipeline; it appears here as soon as it is queued."
              action={
                <Button as={Link} to="/admin/upload" variant="secondary" size="sm">
                  Deposit a report
                </Button>
              }
            />
          )}

          {!loading && !error && jobs.length > 0 && (
            <Table>
              <TableHead>
                <Th className="w-16">Ref</Th>
                <Th>Document</Th>
                <Th>Status</Th>
                <Th hide="md">Deposited by</Th>
                <Th hide="sm">Date</Th>
                <Th align="right">
                  <span className="sr-only">Actions</span>
                </Th>
              </TableHead>
              <TableBody>
                {jobs.map((job) => {
                  const meta = statusMeta(job.status);
                  return (
                    <Tr key={job.id} accentClass={statusRowAccent(meta.tone)}>
                      <Td className="whitespace-nowrap text-xs text-ink-3 tnum">#{job.id}</Td>
                      <Td className="max-w-xs">
                        <span className="block truncate text-ink">{job.original_filename}</span>
                      </Td>
                      <Td>
                        <Status tone={meta.tone} pulse={meta.pulse}>
                          {meta.label}
                        </Status>
                      </Td>
                      <Td hide="md" className="text-sm text-ink-2">
                        <span className="block max-w-[180px] truncate">
                          {job.uploaded_by_email || job.uploaded_by || "—"}
                        </span>
                      </Td>
                      <Td hide="sm" className="whitespace-nowrap text-sm text-ink-3 tnum">
                        {new Date(job.created_at).toLocaleDateString(undefined, {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}
                      </Td>
                      <Td align="right">
                        <Link
                          to={`/admin/jobs/${job.id}`}
                          className="whitespace-nowrap text-sm font-semibold"
                        >
                          Review
                        </Link>
                      </Td>
                    </Tr>
                  );
                })}
              </TableBody>
            </Table>
          )}

          {!loading && !error && totalPages > 1 && (
            <nav
              aria-label="Queue pages"
              className="mt-4 flex flex-wrap items-center justify-between gap-3"
            >
              <p className="text-sm text-ink-2">
                Page <span className="tnum">{page}</span> of{" "}
                <span className="tnum">{totalPages}</span> &middot;{" "}
                <span className="tnum">{totalCount}</span> deposits
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <FontAwesomeIcon icon={faChevronLeft} className="h-3 w-3" aria-hidden="true" />
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Next
                  <FontAwesomeIcon icon={faChevronRight} className="h-3 w-3" aria-hidden="true" />
                </Button>
              </div>
            </nav>
          )}
        </div>
      </Container>
    </>
  );
}
