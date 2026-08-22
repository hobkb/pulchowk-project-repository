import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ingestionApi } from "../api/client";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faListCheck,
  faClock,
  faSpinner,
  faCheckCircle,
  faCircleXmark,
  faFileLines,
  faArrowRight,
  faFilter,
  faChevronLeft,
  faChevronRight,
} from "@fortawesome/free-solid-svg-icons";

export default function PendingApprovals() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedStatus, setSelectedStatus] = useState("ALL");

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const fetchJobs = async () => {
      try {
        setLoading(true);
        const params = {
          ...(selectedStatus !== "ALL" ? { status: selectedStatus } : {}),
          page,
        };
        const res = await ingestionApi.listJobs(params);
        if (!cancelled) {
          const list = Array.isArray(res?.data)
            ? res.data
            : Array.isArray(res?.results)
            ? res.results
            : Array.isArray(res)
            ? res
            : [];
          setJobs(list);

          const count = res?.count || list.length;
          setTotalCount(count);
          setTotalPages(Math.max(1, Math.ceil(count / 10)));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load ingestion jobs.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchJobs();
    return () => {
      cancelled = true;
    };
  }, [selectedStatus, page]);

  const renderStatusBadge = (status) => {
    switch (status) {
      case "EXTRACTED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-micro font-mono bg-accent-primary/10 text-accent-primary border border-accent-primary/20">
            <FontAwesomeIcon icon={faFileLines} className="h-3 w-3" /> Awaiting Review
          </span>
        );
      case "PENDING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-micro font-mono bg-warning-amber/10 text-warning-amber border border-warning-amber/20">
            <FontAwesomeIcon icon={faClock} className="h-3 w-3" /> Queued
          </span>
        );
      case "PROCESSING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-micro font-mono bg-warning-amber/10 text-warning-amber border border-warning-amber/20">
            <FontAwesomeIcon icon={faSpinner} className="animate-spin h-3 w-3" /> Processing
          </span>
        );
      case "VERIFIED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-micro font-mono bg-success-emerald/10 text-success-emerald border border-success-emerald/20">
            <FontAwesomeIcon icon={faCheckCircle} className="h-3 w-3" /> Published
          </span>
        );
      case "SECTIONS_PENDING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-micro font-mono bg-warning-amber/10 text-warning-amber border border-warning-amber/20">
            <FontAwesomeIcon icon={faFileLines} className="h-3 w-3" /> Sections Incomplete
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-micro font-mono bg-error-red/10 text-error-red border border-error-red/20">
            <FontAwesomeIcon icon={faCircleXmark} className="h-3 w-3" /> Processing Error
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-micro font-mono bg-surface-sunken text-text-tertiary">
            <FontAwesomeIcon icon={faClock} className="h-3 w-3" /> {status}
          </span>
        );
    }
  };

  const statusOptions = [
    { label: "All Submissions", value: "ALL" },
    { label: "Awaiting Review", value: "EXTRACTED" },
    { label: "Queued", value: "PENDING" },
    { label: "Processing", value: "PROCESSING" },
    { label: "Published", value: "VERIFIED" },
    { label: "Sections Incomplete", value: "SECTIONS_PENDING" },
    { label: "Processing Error", value: "FAILED" },
  ];

  return (
    <div className="flex flex-col gap-8 max-w-6xl mx-auto py-4">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="text-micro font-mono uppercase tracking-wider text-accent-primary bg-accent-primary/10 border border-accent-primary/20 px-2 py-0.5 rounded-sm">
            Department Archive
          </span>
        </div>
        <h1 className="text-h1 font-bold tracking-tight text-text-primary">
          Project Submissions & Approvals
        </h1>
        <p className="text-body text-text-secondary leading-relaxed max-w-2xl">
          Review submitted project documents, verify bibliographic details, and publish verified research to the department catalog.
        </p>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2 items-center border-b border-border-subtle pb-4">
        <span className="text-micro font-mono uppercase tracking-wider text-text-tertiary flex items-center gap-1.5 mr-2">
          <FontAwesomeIcon icon={faFilter} className="h-3 w-3" />
          Status Filter:
        </span>
        {statusOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setSelectedStatus(opt.value)}
            className={`px-3 py-1 rounded-sm text-body-sm transition-all duration-150 cursor-pointer border ${
              selectedStatus === opt.value
                ? "bg-accent-primary/10 border-accent-primary/30 text-accent-primary font-semibold"
                : "bg-surface-raised border-border-subtle text-text-secondary hover:text-text-primary"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Content Area */}
      {loading ? (
        <div className="flex flex-col gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-20 bg-surface-raised border border-border-subtle rounded-lg animate-pulse"
            />
          ))}
        </div>
      ) : error ? (
        <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg">
          <p className="text-body text-text-secondary">Failed to load ingestion jobs.</p>
          <p className="text-body-sm text-error-red mt-1">{error}</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg flex flex-col items-center gap-3">
          <FontAwesomeIcon icon={faListCheck} className="h-10 w-10 text-text-tertiary/40" />
          <p className="text-body font-semibold text-text-primary">No ingestion jobs found.</p>
          <p className="text-body-sm text-text-secondary">
            Upload a project thesis PDF to start the automated extraction pipeline.
          </p>
          <Link
            to="/admin/upload"
            className="mt-2 px-4 py-2 bg-accent-primary text-white text-body-sm font-medium rounded-md hover:bg-accent-primary/90 transition-all"
          >
            Upload Project PDF
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="bg-surface-raised border border-border-subtle hover:border-border-default rounded-lg p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all duration-150"
            >
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-micro font-mono text-text-tertiary bg-surface-sunken px-2 py-0.5 rounded-sm border border-border-subtle/50">
                    JOB #{job.id}
                  </span>
                  {renderStatusBadge(job.status)}
                  <span className="text-micro font-mono text-text-tertiary">
                    {new Date(job.created_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>

                <h3 className="text-body font-semibold text-text-primary leading-snug">
                  {job.original_filename}
                </h3>

                <p className="text-micro font-mono text-text-secondary">
                  Uploaded by: {job.uploaded_by_email || job.uploaded_by || "Admin"}
                </p>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <Link
                  to={`/admin/jobs/${job.id}`}
                  className="px-4 py-2 rounded-md bg-surface-sunken hover:bg-surface-hover border border-border-default text-text-primary text-body-sm font-medium flex items-center gap-2 transition-all cursor-pointer"
                >
                  <span>Review Submission</span>
                  <FontAwesomeIcon icon={faArrowRight} className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border-subtle pt-4 text-micro mt-2">
          <span className="font-mono text-text-tertiary">
            Page {page} of {totalPages} &middot; Total {totalCount} jobs
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-border-default bg-surface-raised text-text-secondary hover:text-text-primary hover:border-border-strong disabled:opacity-40 transition-all cursor-pointer disabled:cursor-not-allowed font-medium text-body-sm"
            >
              <FontAwesomeIcon icon={faChevronLeft} className="h-3 w-3" /> Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-border-default bg-surface-raised text-text-secondary hover:text-text-primary hover:border-border-strong disabled:opacity-40 transition-all cursor-pointer disabled:cursor-not-allowed font-medium text-body-sm"
            >
              Next <FontAwesomeIcon icon={faChevronRight} className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
