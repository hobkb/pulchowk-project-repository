import { useState } from "react";
import { Link } from "react-router-dom";
import { mockProjects } from "../api/mockProjects";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faFilter, faBookOpen, faUsers, faFolderOpen, faCheckCircle, faClock, faExclamationCircle } from "@fortawesome/free-solid-svg-icons";

export default function Dashboard() {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCluster, setSelectedCluster] = useState("all");

  const isAdmin = user?.role === "admin";

  // Filter projects by search query and cluster
  const filteredProjects = mockProjects.filter((p) => {
    const matchesSearch =
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.supervisor.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.authors.some((a) => a.name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      p.technologies.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCluster = selectedCluster === "all" || p.cluster === selectedCluster;

    // General users only see approved projects, admins see all
    const matchesRoleVisibility = isAdmin ? true : p.status === "approved";

    return matchesSearch && matchesCluster && matchesRoleVisibility;
  });

  // Extract unique clusters for filter tabs
  const clusters = ["all", ...new Set(mockProjects.map((p) => p.cluster))];

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
            <p className="text-xl font-bold text-text-primary mt-0.5">{mockProjects.length} Projects</p>
          </div>
        </div>
        <div className="bg-surface-raised border border-border-subtle rounded-md p-5 flex items-center gap-4">
          <div className="h-10 w-10 rounded-sm bg-accent-violet/10 border border-accent-violet/20 flex items-center justify-center text-accent-violet">
            <FontAwesomeIcon icon={faFolderOpen} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-micro font-mono uppercase tracking-wider text-text-tertiary">Research Clusters</p>
            <p className="text-xl font-bold text-text-primary mt-0.5">{clusters.length - 1} Domains</p>
          </div>
        </div>
        <div className="bg-surface-raised border border-border-subtle rounded-md p-5 flex items-center gap-4">
          <div className="h-10 w-10 rounded-sm bg-success-emerald/10 border border-success-emerald/20 flex items-center justify-center text-success-emerald">
            <FontAwesomeIcon icon={faUsers} className="h-5 w-5" />
          </div>
          <div>
            <p className="text-micro font-mono uppercase tracking-wider text-text-tertiary">Indexed Supervisors</p>
            <p className="text-xl font-bold text-text-primary mt-0.5">3 Academic Faculty</p>
          </div>
        </div>
      </div>

      {/* Cluster Selector Tabs */}
      <div className="flex flex-wrap gap-1.5 items-center border-y border-border-subtle py-4">
<span className="text-micro font-mono uppercase tracking-wider text-text-tertiary flex items-center gap-1.5 mr-2">
            <FontAwesomeIcon icon={faFilter} className="h-3.5 w-3.5" />
            Cluster:
          </span>
        {clusters.map((cluster) => (
          <button
            key={cluster}
            onClick={() => setSelectedCluster(cluster)}
            className={`px-3 py-1 text-micro rounded-sm border capitalize cursor-pointer transition-all duration-150 ${
              selectedCluster === cluster
                ? "bg-accent-primary/10 border-accent-primary/30 text-accent-primary font-semibold"
                : "bg-surface-raised border-border-subtle text-text-secondary hover:text-text-primary"
            }`}
          >
            {cluster}
          </button>
        ))}
      </div>

      {/* Projects Grid Display */}
      {filteredProjects.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg">
          <p className="text-body text-text-secondary">No projects matching the query or filter parameters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProjects.map((p) => (
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

                {/* Admin-only review indicator badge - ICONS ONLY, no text */}
                {isAdmin && (
                  <span className={`flex items-center gap-1 text-micro font-mono uppercase tracking-wider px-2 py-0.5 rounded-sm border ${
                    p.status === "approved"
                      ? "bg-success-emerald/10 border-success-emerald/20 text-success-emerald"
                      : p.status === "pending"
                      ? "bg-warning-amber/10 border-warning-amber/20 text-warning-amber"
                      : "bg-error-red/10 border-error-red/20 text-error-red"
                  }`}>
                    {p.status === "approved" ? <FontAwesomeIcon icon={faCheckCircle} className="h-4 w-4" /> : p.status === "pending" ? <FontAwesomeIcon icon={faClock} className="h-4 w-4" /> : <FontAwesomeIcon icon={faExclamationCircle} className="h-4 w-4" />}
                  </span>
                )}
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
                    <span className="text-text-primary font-medium">{p.supervisor}</span>
                  </span>
                  <span className="text-accent-primary text-xs font-semibold group-hover:translate-x-1 transition-transform">
                    →
                  </span>
                </div>

                <div className="flex flex-wrap gap-1 mt-1">
                  {p.technologies.slice(0, 3).map((t) => (
                    <span key={t} className="bg-surface-sunken px-2 py-0.5 rounded-sm text-micro font-mono text-text-tertiary">
                      {t}
                    </span>
                  ))}
                  {p.technologies.length > 3 && (
                    <span className="bg-surface-sunken px-2 py-0.5 rounded-sm text-micro font-mono text-text-tertiary">
                      +{p.technologies.length - 3} more
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}