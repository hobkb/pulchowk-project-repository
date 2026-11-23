import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ingestionApi, projectsApi } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { isAdminUser } from "../lib/nav";
import { ProjectRecord } from "../components/ProjectRecord";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Container,
  EmptyState,
  ErrorNotice,
  LoadingRows,
  SearchField,
  SectionHeading,
  Status,
} from "../components/ui";

/**
 * The repository home page.
 *
 * Structured the way a real catalogue front page is: a short institutional
 * statement of what the collection is with the search directly under it,
 * then browse-by-department, then what was added recently. Figures are
 * stated in a single line of text rather than blown up into a row of
 * statistic tiles.
 */

const RECENT_COUNT = 6;

const JOB_STATE = {
  PENDING: { tone: "neutral", label: "Queued" },
  PROCESSING: { tone: "warn", label: "Processing" },
  EXTRACTED: { tone: "info", label: "Awaiting verification" },
  SECTIONS_PENDING: { tone: "warn", label: "Sections incomplete" },
  DUPLICATE: { tone: "neutral", label: "Duplicate" },
  FAILED: { tone: "err", label: "Failed" },
  VERIFIED: { tone: "ok", label: "Published" },
};

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = isAdminUser(user);

  const [recent, setRecent] = useState([]);
  const [facets, setFacets] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");

  const [openJobs, setOpenJobs] = useState([]);

  useEffect(() => {
    let cancelled = false;

    Promise.all([projectsApi.list(), projectsApi.facets()])
      .then(([listBody, facetBody]) => {
        if (cancelled) return;
        setRecent((listBody.data || []).slice(0, RECENT_COUNT));
        setFacets(facetBody.data || null);
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
  }, []);

  useEffect(() => {
    if (!isAdmin) return undefined;
    let cancelled = false;

    ingestionApi
      .listJobs({ page_size: 50 })
      .then((body) => {
        if (cancelled) return;
        const jobs = body?.results || body?.data || [];
        setOpenJobs(
          jobs.filter((job) =>
            ["EXTRACTED", "SECTIONS_PENDING", "FAILED"].includes(job.status)
          )
        );
      })
      .catch(() => {
        if (!cancelled) setOpenJobs([]);
      });

    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  const firstName = user?.first_name || user?.profile?.full_name?.split(" ")[0];

  return (
    <>
      {/* Institutional introduction and the primary way in: search. */}
      <section className="border-b border-line bg-band">
        <Container width="wide" className="px-5 sm:px-8 py-10 sm:py-12">
          <p className="text-sm font-bold text-accent">
            Institute of Engineering &middot; Pulchowk Campus
          </p>
          <h1 className="mt-2 text-hero max-w-3xl">Pulchowk Project Repository</h1>
          <p className="mt-3 max-w-2xl text-base text-ink-2">
            A catalogue of student and faculty engineering project reports submitted at Pulchowk
            Campus. Each record lists its authors, supervisor, department and abstract. Full
            reports remain confidential; access can be requested from the department.
          </p>

          <div className="mt-6 max-w-2xl">
            <SearchField
              value={query}
              onChange={setQuery}
              onSubmit={(value) => {
                const trimmed = value.trim();
                navigate(trimmed ? `/projects?q=${encodeURIComponent(trimmed)}` : "/projects");
              }}
              placeholder="Search by title, author, supervisor or keyword"
              size="lg"
            />
          </div>

          {facets && (
            <p className="mt-3 text-sm text-ink-2">
              <span className="font-semibold text-ink tnum">{facets.total}</span>{" "}
              {facets.total === 1 ? "project" : "projects"} from{" "}
              <span className="font-semibold text-ink tnum">
                {(facets.departments || []).length}
              </span>{" "}
              {(facets.departments || []).length === 1 ? "department" : "departments"}
              {(facets.batches || []).length > 0 && (
                <>
                  , covering{" "}
                  <span className="font-semibold text-ink tnum">
                    {(facets.batches || []).length}
                  </span>{" "}
                  {(facets.batches || []).length === 1 ? "batch" : "batches"}
                </>
              )}
              .
            </p>
          )}
        </Container>
      </section>

      <Container width="wide" className="px-5 sm:px-8 py-9">
        {firstName && (
          <p className="mb-6 text-sm text-ink-2">
            Signed in as <span className="font-semibold text-ink">{firstName}</span>.
          </p>
        )}

        {error && (
          <ErrorNotice
            title="The repository could not be reached"
            detail={error}
            action={
              <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
                Reload
              </Button>
            }
            className="mb-8"
          />
        )}

        {/* Reviewers see outstanding work first. */}
        {isAdmin && openJobs.length > 0 && (
          <Card className="mb-9">
            <CardHeader
              title="Deposits awaiting your attention"
              actions={<Link to="/admin/approvals" className="text-sm">Open queue</Link>}
            />
            <ul className="divide-y divide-line">
              {openJobs.slice(0, 4).map((job) => {
                const state = JOB_STATE[job.status] || JOB_STATE.PENDING;
                return (
                  <li key={job.id}>
                    <Link
                      to={`/admin/jobs/${job.id}`}
                      className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1.5 px-4 py-3 no-underline hover:bg-band hover:no-underline"
                    >
                      <span className="min-w-0 text-sm text-ink truncate">
                        <span className="text-ink-3 tnum">#{job.id}</span>{" "}
                        {job.original_filename || "Untitled deposit"}
                      </span>
                      <Status tone={state.tone}>{state.label}</Status>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-x-12 gap-y-9 lg:grid-cols-[minmax(0,1fr)_17rem] items-start">
          <section className="min-w-0">
            <SectionHeading
              title="Recently published"
              actions={<Link to="/projects">Browse all projects</Link>}
            />

            {loading && <LoadingRows rows={4} />}

            {!loading && !error && recent.length === 0 && (
              <EmptyState
                title="No projects published yet"
                description="Verified project reports appear here as they are added to the repository."
                action={
                  isAdmin ? (
                    <Button as={Link} to="/admin/upload" variant="secondary" size="sm">
                      Deposit a report
                    </Button>
                  ) : null
                }
              />
            )}

            {!loading && recent.length > 0 && (
              <div className="border-t border-line">
                {recent.map((project) => (
                  <ProjectRecord key={project.id} project={project} />
                ))}
              </div>
            )}
          </section>

          <aside className="min-w-0">
            {facets && (facets.departments || []).length > 0 && (
              <Card>
                <CardHeader title="Browse by department" />
                <ul className="divide-y divide-line">
                  {facets.departments.map((entry) => (
                    <li key={entry.name}>
                      <Link
                        to={`/projects?department=${encodeURIComponent(entry.name)}`}
                        className="flex items-baseline justify-between gap-3 px-4 py-2.5 text-sm no-underline hover:bg-band hover:no-underline"
                      >
                        <span className="min-w-0">{entry.name}</span>
                        <span className="shrink-0 text-xs text-ink-3 tnum">{entry.count}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {facets && (facets.batches || []).length > 0 && (
              <Card className="mt-5">
                <CardHeader title="Browse by batch" />
                <div className="flex flex-wrap gap-1.5 p-4">
                  {facets.batches.map((entry) => (
                    <Link
                      key={entry.name}
                      to={`/projects?batch=${encodeURIComponent(entry.name)}`}
                      className="rounded-sm border border-line bg-band px-2 py-0.5 text-xs text-ink-2 no-underline tnum hover:border-ink-3 hover:text-ink hover:no-underline"
                    >
                      {entry.name}
                    </Link>
                  ))}
                </div>
              </Card>
            )}

            <Alert tone="neutral" className="mt-5">
              Full project reports are confidential. Records here show the abstract and
              catalogue details only.
            </Alert>
          </aside>
        </div>
      </Container>
    </>
  );
}
