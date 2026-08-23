import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { projectsApi, authApi } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { getDepartmentAcronym } from "../utils/departmentUtils";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faArrowRight,
  faFolderTree,
} from "@fortawesome/free-solid-svg-icons";

export default function DashboardHome() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    Promise.all([projectsApi.list(), authApi.getDepartments()])
      .then(([projRes, deptRes]) => {
        if (cancelled) return;
        const projList = Array.isArray(projRes?.data)
          ? projRes.data
          : Array.isArray(projRes)
          ? projRes
          : [];
        const deptList = Array.isArray(deptRes?.data)
          ? deptRes.data
          : Array.isArray(deptRes)
          ? deptRes
          : [];

        setProjects(projList);
        setDepartments(deptList);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const departmentCards = [
    {
      code: "DoECE",
      name: "Department of Electronics & Computer Engineering",
      query: "Department of Electronics and Computer Engineering",
      desc: "Software Engineering, AI, Computer Architecture, Embedded Systems, Communication Networks.",
    },
    {
      code: "DoCE",
      name: "Department of Civil Engineering",
      query: "Department of Civil Engineering",
      desc: "Structural Engineering, Water Resources, Transportation, Geotechnical & Environmental Engineering.",
    },
    {
      code: "DoEE",
      name: "Department of Electrical Engineering",
      query: "Department of Electrical Engineering",
      desc: "Power Systems, Control Engineering, Renewable Energy, High Voltage & Smart Grid Systems.",
    },
    {
      code: "DoME",
      name: "Department of Mechanical & Aerospace Engineering",
      query: "Department of Mechanical and Aerospace Engineering",
      desc: "Aerospace Systems, Energy Technology, Robotics, Thermal Science & Automotive Design.",
    },
    {
      code: "DoARCH",
      name: "Department of Architecture & Urban Planning",
      query: "Department of Architecture and Urban Planning",
      desc: "Sustainable Architecture, Urban Design, Conservation, Landscape Architecture & Spatial Planning.",
    },
    {
      code: "DoAS",
      name: "Department of Applied Sciences & Chemical Engineering",
      query: "Department of Applied Sciences and Chemical Engineering",
      desc: "Chemical Technology, Applied Physics, Mathematics, Polymer Engineering & Process Dynamics.",
    },
  ];

  const recentProjects = [...projects]
    .sort((a, b) => {
      if (a.created_at && b.created_at) {
        return new Date(b.created_at) - new Date(a.created_at);
      }
      return (b.id || 0) - (a.id || 0);
    })
    .slice(0, 6);

  // Compute unique supervisors count
  const supervisorCount = new Set(
    projects.map((p) => p.supervisor).filter(Boolean)
  ).size;

  return (
    <div className="flex flex-col gap-8 max-w-6xl mx-auto py-2">
      {/* Welcome Banner */}
      <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 sm:p-8 flex flex-col gap-6 shadow-xs relative overflow-hidden">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex flex-col gap-1 max-w-2xl">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary">
              Welcome back, {user?.first_name || user?.username || "User"}
            </h1>
            <p className="text-body-sm text-text-secondary leading-relaxed">
              Explore academic theses, final year projects, and departmental research records indexed across Pulchowk Campus.
            </p>
          </div>

          <Link
            to="/projects"
            className="px-4 py-2.5 bg-accent-primary hover:bg-accent-primary-hover text-text-inverse text-xs font-semibold rounded-md shadow-xs flex items-center gap-2 transition-all cursor-pointer shrink-0"
          >
            <FontAwesomeIcon icon={faFolderTree} />
            <span>Browse All Projects</span>
          </Link>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 border-t border-border-subtle pt-6">
          <div className="bg-surface-sunken border border-border-subtle/60 rounded-lg p-4 flex flex-col gap-0.5">
            <span className="text-2xl font-bold text-text-primary font-mono">
              {projects.length}
            </span>
            <span className="text-xs text-text-tertiary">Indexed Projects</span>
          </div>

          <div className="bg-surface-sunken border border-border-subtle/60 rounded-lg p-4 flex flex-col gap-0.5">
            <span className="text-2xl font-bold text-text-primary font-mono">
              {departments.length || 6}
            </span>
            <span className="text-xs text-text-tertiary">Departments</span>
          </div>

          <div className="bg-surface-sunken border border-border-subtle/60 rounded-lg p-4 flex flex-col gap-0.5">
            <span className="text-2xl font-bold text-text-primary font-mono">
              {supervisorCount || "15+"}
            </span>
            <span className="text-xs text-text-tertiary">Faculty Supervisors</span>
          </div>
        </div>
      </div>

      {/* Explore Departments Quick Links Section */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-h2 font-bold text-text-primary">
              Explore by Department
            </h2>
            <p className="text-body-sm text-text-secondary">
              Select a department to filter research repositories instantly
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {departmentCards.map((dept) => (
            <button
              key={dept.code}
              onClick={() =>
                navigate(`/projects?department=${encodeURIComponent(dept.query)}`)
              }
              className="bg-surface-raised border border-border-subtle hover:border-border-default rounded-lg p-5 flex flex-col justify-between gap-3 text-left transition-all duration-150 hover:bg-surface-hover/30 group cursor-pointer"
            >
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="px-2.5 py-0.5 rounded font-mono font-semibold text-xs bg-surface-sunken border border-border-subtle text-text-primary">
                    {dept.code}
                  </span>
                  <FontAwesomeIcon
                    icon={faArrowRight}
                    className="text-text-tertiary group-hover:text-accent-primary group-hover:translate-x-1 transition-all h-3.5 w-3.5"
                  />
                </div>
                <h3 className="text-sm font-semibold text-text-primary group-hover:text-accent-primary transition-colors leading-snug">
                  {dept.name}
                </h3>
              </div>
              <p className="text-xs text-text-tertiary line-clamp-2 leading-relaxed">
                {dept.desc}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Recent Published Research Section */}
      <div className="flex flex-col gap-4 border-t border-border-subtle pt-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-h2 font-bold text-text-primary">
              Recently Indexed Research
            </h2>
            <p className="text-body-sm text-text-secondary">
              Latest published theses and capstone projects
            </p>
          </div>

          <Link
            to="/projects"
            className="text-xs font-semibold text-accent-primary hover:underline flex items-center gap-1"
          >
            <span>View All ({projects.length})</span>
            <FontAwesomeIcon icon={faArrowRight} className="h-3 w-3" />
          </Link>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-44 bg-surface-raised border border-border-subtle rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recentProjects.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                className="bg-surface-raised border border-border-subtle hover:border-border-default rounded-lg p-5 flex flex-col gap-3 transition-all group"
              >
                <div className="flex items-center justify-between gap-2 text-micro font-mono text-text-tertiary">
                  <span className="bg-surface-sunken px-2 py-0.5 rounded border border-border-subtle/50 font-semibold text-text-primary truncate max-w-[160px]">
                    {getDepartmentAcronym(p.department)}
                  </span>
                  {p.year && (
                    <span className="bg-surface-sunken px-2 py-0.5 rounded border border-border-subtle/50">
                      {p.year}
                    </span>
                  )}
                </div>

                <h3 className="text-body font-semibold text-text-primary leading-snug group-hover:text-accent-primary transition-colors line-clamp-2">
                  {p.title}
                </h3>

                <p className="text-body-sm text-text-secondary line-clamp-2 leading-relaxed text-xs">
                  {p.abstract || "No abstract snippet available."}
                </p>

                <div className="border-t border-border-subtle pt-3 mt-auto flex justify-between items-center text-micro text-text-secondary">
                  <span className="truncate">
                    <span className="text-text-tertiary">Supervisor: </span>
                    <span className="text-text-primary font-medium">
                      {p.supervisor || "—"}
                    </span>
                  </span>
                  <FontAwesomeIcon
                    icon={faArrowRight}
                    className="text-accent-primary text-xs group-hover:translate-x-1 transition-transform"
                  />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
