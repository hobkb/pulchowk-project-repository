import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { projectsApi } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBookOpen, faUsers, faFolderOpen, faChevronLeft, faChevronRight } from "@fortawesome/free-solid-svg-icons";

const PAGE_SIZE = 6;

export default function Dashboard() {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    let cancelled = false;
    projectsApi
      .list()
      .then((res) => {
        if (!cancelled) setProjects(res.data || []);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Failed to load projects");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  const filteredProjects = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => {
      const title = (p.title || "").toLowerCase();
      const supervisor = (p.supervisor || "").toLowerCase();
      const authorMatch = (p.authors || []).some((a) =>
        (a.name || "").toLowerCase().includes(q)
      );
      const keywordMatch = (p.technologies || []).some((t) =>
        (t || "").toLowerCase().includes(q)
      );
      return (
        title.includes(q) ||
        supervisor.includes(q) ||
        authorMatch ||
        keywordMatch
      );
    });
  }, [projects, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filteredProjects.length / PAGE_SIZE));
  const currentProjects = useMemo(
    () =>
      filteredProjects.slice(
        (currentPage - 1) * PAGE_SIZE,
        currentPage * PAGE_SIZE
      ),
    [filteredProjects, currentPage]
  );

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(1);
  }, [currentPage, totalPages]);

  const clusters = useMemo(() => {
    return ["all", ...new Set(projects.map((p) => p.cluster).filter(Boolean))];
  }, [projects]);

  const supervisorCount = useMemo(() => {
    const set = new Set();
    projects.forEach((p) => (p.supervisors || []).forEach((s) => set.add(s)));
    return set.size;
  }, [projects]);

  if (loading) {
    return (
      <div className="flex flex-col gap-8">
        <div className="h-8 bg-border-default/50 rounded animate-pulse w-72"></div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-border-default/40 rounded-md animate-pulse"></div>
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-52 bg-surface-raised border border-border-subtle rounded-lg animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg">
        <p className="text-body text-text-secondary">Failed to load projects.</p>
        <p className="text-body-sm text-text-tertiary mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Welcome Banner */}
      <div className="flex flex-col gap-2">
        <h1 className="text-h1 font-bold tracking-tight text-text-primary">
          Welcome back, {user?.first_name || "User"}
        </h1>
        <p className="text-body text-text-secondary max-w-2xl leading-relaxed">
          Explore and query undergraduate project theses, source technologies, and key research findings from the Department of Electronics & Computer Engineering.
        </p>
      </div>

      {/* Stats Counter Section per Chapter 14 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-surface-raised border border-border-subtle rounded-md p-5 flex items-center gap-4">
          <div className="h-10 w-10 rounded-sm bg-accent-primary/10 border border-accent-primary/20 flex items-center justify-center text-accent-primary">
            <FontAwesomeIcon icon={faBookOpen} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-micro font-mono uppercase tracking-wider text-text-tertiary">Total Indexed</p>
            <p className="text-xl font-bold text-text-primary mt-0.5">{projects.length} Projects</p>
          </div>
        </div>
        <div className="bg-surface-raised border border-border-subtle rounded-md p-5 flex items-center gap-4">
          <div className="h-10 w-10 rounded-sm bg-accent-violet/10 border border-accent-violet/20 flex items-center justify-center text-accent-violet">
            <FontAwesomeIcon icon={faFolderOpen} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-micro font-mono uppercase tracking-wider text-text-tertiary">Research Domains</p>
            <p className="text-xl font-bold text-text-primary mt-0.5">{clusters.length - 1} Domains</p>
          </div>
        </div>
        <div className="bg-surface-raised border border-border-subtle rounded-md p-5 flex items-center gap-4">
          <div className="h-10 w-10 rounded-sm bg-success-emerald/10 border border-success-emerald/20 flex items-center justify-center text-success-emerald">
            <FontAwesomeIcon icon={faUsers} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-micro font-mono uppercase tracking-wider text-text-tertiary">Indexed Supervisors</p>
            <p className="text-xl font-bold text-text-primary mt-0.5">{supervisorCount} Academic Faculty</p>
          </div>
        </div>
      </div>

      {/* DEFERRED — cluster filter tabs. No domain/cluster data is ingested yet
          (16 published projects all have empty clusters), so the tabs are
          disabled to avoid rendering an empty filter bar. Re-enable once
          project_domains / research_group carry real data.
      <div className="flex flex-wrap gap-1.5 items-center border-y border-border-subtle py-4">
        <span className="text-micro font-mono uppercase tracking-wider text-text-tertiary flex items-center gap-1.5 mr-2">
          <FontAwesomeIcon icon={faFilter} className="h-3.5 w-3.5" />
          Cluster:
        </span>
        {clusters.map((cluster) => (
          <button
            key={cluster}
            onClick={() => setSelectedCluster(cluster)}
            className={`px-3 py-1 rounded-sm border capitalize cursor-pointer transition-all duration-150 ${
              selectedCluster === cluster
                ? "bg-accent-primary/10 border-accent-primary/30 text-accent-primary font-semibold"
                : "bg-surface-raised border-border-subtle text-text-secondary hover:text-text-primary"
            }`}
          >
            {cluster}
          </button>
        ))}
      </div>
      */}

      {/* Projects Grid Display */}
      {filteredProjects.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg">
          <p className="text-body text-text-secondary">No projects matching the query or filter parameters.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {currentProjects.map((p) => (
            <Link
              key={p.id}
              to={`/projects/${p.id}`}
              className="bg-surface-raised border border-border-subtle hover:border-border-default hover:bg-surface-hover/20 rounded-lg p-6 flex flex-col gap-4 transition-all duration-200 group"
            >
              {/* Card Header info */}
              <div className="flex justify-between items-start gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-micro font-mono text-text-tertiary uppercase bg-surface-sunken px-2 py-0.5 rounded-sm border border-border-subtle/50">
                    {p.department}
                  </span>
                  <span className="text-micro font-mono text-text-tertiary bg-surface-sunken px-2 py-0.5 rounded-sm border border-border-subtle/50">
                    {p.year}
                  </span>
                </div>
              </div>

              {/* Title */}
              <h3 className="text-body font-semibold text-text-primary leading-snug group-hover:text-accent-primary transition-colors duration-150 line-clamp-2">
                {p.title}
              </h3>

              {/* Excerpt Abstract */}
              <p className="text-body-sm text-text-secondary leading-relaxed line-clamp-2">
                {p.abstract}
              </p>

              {/* Footer info: Authors & Supervisor */}
              <div className="border-t border-border-subtle pt-4 mt-auto flex flex-col gap-2 text-micro text-text-secondary">
                <div className="flex justify-between items-center">
                  <span>
                    <span className="text-text-tertiary">Supervisor: </span>
                    <span className="text-text-primary font-medium">{p.supervisor || "—"}</span>
                  </span>
                  <span className="text-accent-primary text-xs font-semibold group-hover:translate-x-1 transition-transform">
                    →
                  </span>
                </div>

                <div className="flex flex-wrap gap-1 mt-1">
                  {(p.technologies || []).slice(0, 3).map((t) => (
                    <span key={t} className="bg-surface-sunken px-2 py-0.5 rounded-sm text-micro font-mono text-text-tertiary">
                      {t}
                    </span>
                  ))}
                  {(p.technologies || []).length > 3 && (
                    <span className="bg-surface-sunken px-2 py-0.5 rounded-sm text-micro font-mono text-text-tertiary">
                      +{(p.technologies || []).length - 3} more
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border-subtle pt-4 text-micro">
              <span className="font-mono text-text-tertiary">
                Page {currentPage} of {totalPages}
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-border-default bg-surface-raised text-text-secondary hover:text-text-primary hover:border-border-strong disabled:opacity-40 transition-all cursor-pointer disabled:cursor-not-allowed"
                >
                  <FontAwesomeIcon icon={faChevronLeft} className="h-3 w-3" /> Previous
                </button>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-border-default bg-surface-raised text-text-secondary hover:text-text-primary hover:border-border-strong disabled:opacity-40 transition-all cursor-pointer disabled:cursor-not-allowed"
                >
                  Next <FontAwesomeIcon icon={faChevronRight} className="h-3 w-3" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}