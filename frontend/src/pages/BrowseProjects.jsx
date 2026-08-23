import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faFolderOpen, faXmark } from "@fortawesome/free-solid-svg-icons";
import { projectsApi } from "../api/client";
import { academicLevelLabel, batchLabel, personDisplayName } from "../lib/labels";
import { ProjectRecord } from "../components/ProjectRecord";
import {
  Alert,
  Breadcrumb,
  Button,
  Container,
  Crumb,
  EmptyState,
  Pagination,
  ErrorNotice,
  LoadingRows,
  SearchField,
} from "../components/ui";
import { Link } from "react-router-dom";

/**
 * The project catalogue.
 *
 * All filtering is done by the backend — the query, department, level and
 * batch go out as query parameters and the server returns the matches, so
 * the result count shown is the real number of matching records. The URL
 * carries that state, so a search can be linked and the back button works.
 *
 * The search is ordinary keyword matching over stored fields. It is
 * labelled "Search projects" because that is exactly what it is; there is
 * no ranking model or semantic component behind it and the interface does
 * not suggest otherwise.
 */

const DEBOUNCE_MS = 300;

/** Batches are stored as a three-digit admission code ("078"); readers
 *  know them as the Bikram Sambat year, so that is what is shown. The
 *  stored code remains the filter value. */
function useDebounced(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** A filter group: options with the real number of records behind each,
 *  so nothing is offered that would return nothing. */
function Facet({ legend, options, value, onChange, formatLabel = (v) => v, subLabel = () => null }) {
  if (!options || options.length === 0) return null;

  return (
    <div className="border-b border-line py-4 first:pt-0 last:border-b-0">
      <h3 className="mb-2 text-sm font-semibold text-ink">{legend}</h3>
      <ul className="max-h-56 space-y-0.5 overflow-y-auto pr-1">
        {options.map((option) => {
          const selected = value.toLowerCase() === option.name.toLowerCase();
          // A value nothing is filed under is shown (the cluster list is a
          // fixed departmental taxonomy) but cannot be selected, so no
          // filter can ever be applied that returns nothing.
          const empty = option.count === 0;
          return (
            <li key={option.name}>
              <button
                type="button"
                aria-pressed={selected}
                disabled={empty}
                onClick={() => onChange(selected ? "" : option.name)}
                className={`flex w-full items-baseline justify-between gap-3 rounded-sm px-2 py-1 text-left text-sm transition-colors ${
                  empty
                    ? "cursor-not-allowed text-ink-3"
                    : selected
                      ? "cursor-pointer bg-primary-050 font-semibold text-primary"
                      : "cursor-pointer text-ink-2 hover:bg-band hover:text-ink"
                }`}
              >
                <span className="min-w-0">
                  <span className="block truncate">{formatLabel(option.name)}</span>
                  {subLabel(option) && (
                    <span className="block truncate text-xs font-normal text-ink-3">
                      {subLabel(option)}
                    </span>
                  )}
                </span>
                <span className="shrink-0 text-xs text-ink-3 tnum">{option.count}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function BrowseProjects() {
  const [searchParams, setSearchParams] = useSearchParams();

  const queryParam = searchParams.get("q") || "";
  const department = searchParams.get("department") || "";
  const academicLevel = searchParams.get("academic_level") || "";
  const batch = searchParams.get("batch") || "";
  const cluster = searchParams.get("cluster") || "";
  const supervisor = searchParams.get("supervisor") || "";
  // The page lives in the URL alongside the filters, so the back button and
  // a shared link both land on the page the reader was actually looking at.
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10) || 1);

  const [queryInput, setQueryInput] = useState(queryParam);
  const debouncedQuery = useDebounced(queryInput, DEBOUNCE_MS);

  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [facets, setFacets] = useState(null);
  const [pagination, setPagination] = useState(null);

  useEffect(() => {
    setQueryInput((current) => (current === queryParam ? current : queryParam));
  }, [queryParam]);

  const updateParams = useCallback(
    (changes) => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          Object.entries(changes).forEach(([key, value]) => {
            if (value) next.set(key, value);
            else next.delete(key);
          });
          // Changing what is being filtered invalidates the current page
          // number; only an explicit page change keeps it.
          if (!("page" in changes)) next.delete("page");
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  useEffect(() => {
    if (debouncedQuery === queryParam) return;
    updateParams({ q: debouncedQuery });
  }, [debouncedQuery, queryParam, updateParams]);

  // Facets are refetched whenever the filters change. Counting each
  // dimension against the OTHER active filters is what makes the number
  // beside an option equal what selecting it actually returns -- with a
  // single unconditional count, "Batch 078 (4)" could still yield nothing
  // once another filter was already on.
  useEffect(() => {
    let cancelled = false;
    projectsApi
      .facets({ q: queryParam, department, academic_level: academicLevel, batch, cluster, supervisor })
      .then((body) => {
        if (!cancelled) setFacets(body.data);
      })
      .catch(() => {
        if (!cancelled) setFacets(null);
      });
    return () => {
      cancelled = true;
    };
  }, [queryParam, department, academicLevel, batch, cluster, supervisor]);

  // One request in flight at a time, so a slow earlier search can never
  // overwrite a newer one.
  const abortRef = useRef(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    projectsApi
      .list(
        {
          q: queryParam,
          department,
          academic_level: academicLevel,
          batch,
          cluster,
          supervisor,
          page,
        },
        { signal: controller.signal }
      )
      .then((body) => {
        if (controller.signal.aborted) return;
        setProjects(body.data || []);
        setPagination(body.pagination || null);
      })
      .catch((err) => {
        if (controller.signal.aborted || err.name === "AbortError") return;
        setError(err.message);
        setProjects([]);
        setPagination(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [queryParam, department, academicLevel, batch, cluster, supervisor, page]);

  const activeFilters = useMemo(
    () =>
      [
        department && { key: "department", label: department },
        academicLevel && { key: "academic_level", label: academicLevel },
        batch && { key: "batch", label: `Batch ${batchLabel(batch)}` },
        cluster && { key: "cluster", label: cluster },
        supervisor && { key: "supervisor", label: supervisor },
      ].filter(Boolean),
    [department, academicLevel, batch, cluster, supervisor]
  );

  // Cluster is a fixed departmental vocabulary rather than something that
  // emerges from the data, so every cluster is listed with its real count;
  // ones with no projects render disabled rather than being hidden.
  const clusterOptions = useMemo(() => {
    if (!facets) return [];
    const counts = new Map((facets.clusters || []).map((c) => [c.name, c.count]));
    const names = facets.cluster_choices?.length
      ? facets.cluster_choices
      : (facets.clusters || []).map((c) => c.name);
    return names.map((name) => ({ name, count: counts.get(name) || 0 }));
  }, [facets]);

  const hasCriteria = Boolean(queryParam) || activeFilters.length > 0;

  function clearAll() {
    setQueryInput("");
    setSearchParams({}, { replace: true });
  }

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb last>Projects</Crumb>
      </Breadcrumb>

      <Container width="wide" className="px-5 sm:px-8 py-8">
        <h1 className="text-title">Search projects</h1>

        <div className="mt-5 max-w-2xl">
          <SearchField
            value={queryInput}
            onChange={setQueryInput}
            onSubmit={(value) => updateParams({ q: value.trim() })}
            placeholder="Search by title, author, supervisor, rank, cluster or keyword"
            size="lg"
          />
        </div>

        {activeFilters.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-ink-3">Filters:</span>
            {activeFilters.map((filter) => (
              <button
                key={filter.key}
                type="button"
                onClick={() => updateParams({ [filter.key]: "" })}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-sm border border-line-strong bg-white px-2 py-0.5 text-xs text-ink hover:border-ink-3 hover:bg-band transition-colors"
              >
                {filter.label}
                <FontAwesomeIcon icon={faXmark} className="h-3 w-3 text-ink-3" aria-hidden="true" />
              </button>
            ))}
            <button
              type="button"
              onClick={clearAll}
              className="cursor-pointer text-xs font-semibold text-link hover:text-link-hover"
            >
              Clear all
            </button>
          </div>
        )}

        <div className="mt-7 grid grid-cols-1 gap-x-10 gap-y-6 lg:grid-cols-[15rem_minmax(0,1fr)] items-start">
          {facets && (
            <aside className="order-2 border-t border-line pt-5 lg:order-1 lg:border-t-0 lg:pt-0">
              <h2 className="mb-2 text-sm font-semibold text-ink">Refine results</h2>
              <Facet
                legend="Department"
                options={facets.departments}
                value={department}
                onChange={(value) => updateParams({ department: value })}
              />
              <Facet
                formatLabel={academicLevelLabel}
                legend="Academic level"
                options={facets.academic_levels}
                value={academicLevel}
                onChange={(value) => updateParams({ academic_level: value })}
              />
              <Facet
                legend="Batch"
                options={facets.batches}
                value={batch}
                onChange={(value) => updateParams({ batch: value })}
                formatLabel={batchLabel}
              />
              {/* Both of these are built from real project data returned by
                  the facets endpoint — no hardcoded names or codes. */}
              <Facet
                legend="Cluster"
                options={clusterOptions}
                value={cluster}
                onChange={(value) => updateParams({ cluster: value })}
              />
              <Facet
                legend="Supervisor"
                options={facets.supervisors}
                value={supervisor}
                onChange={(value) => updateParams({ supervisor: value })}
                formatLabel={(name) => {
                  const row = facets.supervisors.find((s) => s.name === name);
                  return personDisplayName({ name, title: row?.title });
                }}
                subLabel={(option) => option.designation || null}
              />
            </aside>
          )}

          <div className={`order-1 min-w-0 lg:order-2 ${facets ? "" : "lg:col-span-2"}`}>
            <div
              aria-live="polite"
              className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line pb-2"
            >
              <p className="text-sm text-ink-2">
                {loading ? (
                  "Searching…"
                ) : (
                  <>
                    Showing <span className="font-semibold text-ink tnum">{projects.length}</span>{" "}
                    {projects.length === 1 ? "project" : "projects"}
                    {queryParam && (
                      <>
                        {" "}for <span className="font-semibold text-ink">“{queryParam}”</span>
                      </>
                    )}
                  </>
                )}
              </p>
            </div>

            {loading && <LoadingRows rows={5} className="mt-1" />}

            {!loading && error && (
              <ErrorNotice
                title="Projects could not be loaded"
                detail={error}
                action={
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => updateParams({ q: queryParam })}
                  >
                    Try again
                  </Button>
                }
                className="mt-5"
              />
            )}

            {!loading && !error && projects.length === 0 && (
              <EmptyState
                icon={faFolderOpen}
                title={
                  queryParam
                    ? `No projects match “${queryParam}”`
                    : hasCriteria
                      ? "No projects match these filters"
                      : "No projects published yet"
                }
                description={
                  hasCriteria
                    ? "Search looks for every word you type, so a shorter query matches more. You can also remove a filter."
                    : "Verified project reports appear here once they have been published to the repository."
                }
                action={
                  hasCriteria ? (
                    <Button variant="secondary" size="sm" onClick={clearAll}>
                      Clear search and filters
                    </Button>
                  ) : null
                }
                className="mt-5"
              />
            )}

            {!loading && !error && projects.length > 0 && (
              <div>
                {projects.map((project) => (
                  <ProjectRecord key={project.id} project={project} />
                ))}
              </div>
            )}

            {!loading && !error && pagination && (
              <Pagination
                page={pagination.page}
                totalPages={pagination.total_pages}
                totalCount={pagination.total_count}
                label="projects"
                onChange={(next) => {
                  updateParams({ page: next > 1 ? String(next) : "" });
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              />
            )}

          </div>
        </div>
      </Container>
    </>
  );
}
