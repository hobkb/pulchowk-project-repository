import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { projectsApi, organizationApi } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faBookOpen, faUsers, faFolderOpen, faChevronLeft, faChevronRight } from "@fortawesome/free-solid-svg-icons";

import { getDepartmentAcronym } from "../utils/departmentUtils";

const PAGE_SIZE = 6;

// Department to Faculty/Program mapping
const DEPARTMENT_FACULTIES = {
  "department of electronics and computer engineering": [
    { code: "all", label: "All Programs" },
    { code: "bct", label: "BCT (Computer Engineering)" },
    { code: "bei", label: "BEI (Electronics & Communication)" },
  ],
  "department of civil engineering": [
    { code: "all", label: "All Programs" },
    { code: "bce", label: "BCE (Civil Engineering)" },
  ],
  "department of electrical engineering": [
    { code: "all", label: "All Programs" },
    { code: "bel", label: "BEL (Electrical Engineering)" },
  ],
  "department of mechanical and aerospace engineering": [
    { code: "all", label: "All Programs" },
    { code: "bme", label: "BME (Mechanical Engineering)" },
    { code: "bas", label: "BAS (Aerospace Engineering)" },
  ],
  "department of architecture": [
    { code: "all", label: "All Programs" },
    { code: "barch", label: "B.Arch (Architecture)" },
  ],
  "department of applied sciences and chemical engineering": [
    { code: "all", label: "All Programs" },
    { code: "bch", label: "BCH (Chemical Engineering)" },
  ],
};

const ALL_FACULTIES = [
  { code: "all", label: "All Programs" },
  { code: "bct", label: "BCT (Computer)" },
  { code: "bei", label: "BEI (Electronics)" },
  { code: "bce", label: "BCE (Civil)" },
  { code: "bel", label: "BEL (Electrical)" },
  { code: "bme", label: "BME (Mechanical)" },
  { code: "bas", label: "BAS (Aerospace)" },
  { code: "barch", label: "B.Arch (Architecture)" },
  { code: "bch", label: "BCH (Chemical)" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // State
  const [projects, setProjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Read search params
  const searchQuery = searchParams.get("q") || "";
  const selectedDepartment = searchParams.get("department") || "all";
  const selectedLevel = searchParams.get("level") || "all";
  const selectedFaculty = searchParams.get("faculty") || "all";
  const selectedYear = searchParams.get("year") || "all";
  const selectedProjectType = searchParams.get("type") || "all";

  // Traversal Step state (1: Dept, 2: Level, 3: Faculty, 4: Year, 5: Category)
  const [activeStep, setActiveStep] = useState(1);

  // Sync active step with search params on initial load
  useEffect(() => {
    if (selectedProjectType !== "all") setActiveStep(5);
    else if (selectedYear !== "all") setActiveStep(5);
    else if (selectedFaculty !== "all") setActiveStep(4);
    else if (selectedLevel !== "all") setActiveStep(3);
    else if (selectedDepartment !== "all") setActiveStep(2);
    else setActiveStep(1);
  }, []);

  // Update filter parameter and automatically traverse to next step
  const updateFilterAndTraverse = (key, value, nextStep) => {
    const newParams = new URLSearchParams(searchParams);
    if (!value || value === "all" || value === "") {
      newParams.delete(key);
    } else {
      newParams.set(key, value);
    }

    // Reset downstream filters if parent changes
    if (key === "department") {
      newParams.delete("faculty");
    }

    setCurrentPage(1);
    setSearchParams(newParams, { replace: true });
    if (nextStep) setActiveStep(nextStep);
  };

  const clearAllFilters = () => {
    setCurrentPage(1);
    setActiveStep(1);
    setSearchParams({}, { replace: true });
  };

  // Fetch departments & projects
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      try {
        const [projRes, deptRes] = await Promise.all([
          projectsApi.list(),
          organizationApi.getDepartments().catch(() => ({ data: [] })),
        ]);

        if (!cancelled) {
          const rawProjects = projRes?.data || (Array.isArray(projRes) ? projRes : []);
          setProjects(rawProjects);

          const rawDepts = deptRes?.data || (Array.isArray(deptRes) ? deptRes : []);
          setDepartments(rawDepts);
        }
      } catch (e) {
        if (!cancelled) setError(e.message || "Failed to load projects repository data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  // Department counts
  const departmentCounts = useMemo(() => {
    const counts = {};
    projects.forEach((p) => {
      const dName = p.department || "Unassigned";
      counts[dName] = (counts[dName] || 0) + 1;
    });
    return counts;
  }, [projects]);

  // Supervisors count
  const supervisorCount = useMemo(() => {
    const set = new Set();
    projects.forEach((p) => (p.supervisors || []).forEach((s) => set.add(s)));
    return set.size;
  }, [projects]);

  // Academic Levels choices
  const academicLevels = [
    { id: "all", label: "All Levels" },
    { id: "UG", label: "UG (Undergraduate)" },
    { id: "Masters", label: "Masters (M.Sc. / M.E.)" },
    { id: "PhD", label: "PhD (Doctoral)" },
  ];

  // Faculty/Program choices based on selected department
  const facultyChoices = useMemo(() => {
    if (selectedDepartment === "all") return ALL_FACULTIES;
    const key = selectedDepartment.toLowerCase();
    return DEPARTMENT_FACULTIES[key] || ALL_FACULTIES;
  }, [selectedDepartment]);

  // Extract unique available years
  const availableYears = useMemo(() => {
    const yearsSet = new Set();
    projects.forEach((p) => {
      if (p.year) yearsSet.add(p.year);
      else if (p.batch) {
        const b = String(p.batch).trim();
        if (/^\d+$/.test(b) && b.length >= 2) yearsSet.add("20" + b.slice(-2));
        else yearsSet.add(b);
      }
    });
    const sorted = Array.from(yearsSet).sort().reverse();
    return [{ id: "all", label: "All Years" }, ...sorted.map((y) => ({ id: y, label: y }))];
  }, [projects]);

  // Project Types choices
  const projectTypes = [
    { id: "all", label: "All Projects" },
    { id: "Major", label: "Major Project" },
    { id: "Minor", label: "Minor Project" },
  ];

  // Filter projects through search + filters
  const filteredProjects = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();

    return projects.filter((p) => {
      // Search bar filter (from top Navbar)
      if (q) {
        const titleMatch = (p.title || "").toLowerCase().includes(q);
        const abstractMatch = (p.abstract || "").toLowerCase().includes(q);
        const supervisorMatch = (p.supervisor || "").toLowerCase().includes(q);
        const authorMatch = (p.authors || []).some(
          (a) => (a.name || "").toLowerCase().includes(q) || (a.rollNumber || "").toLowerCase().includes(q)
        );
        const techMatch =
          (p.technologies || []).some((t) => (t || "").toLowerCase().includes(q)) ||
          (p.keywords || []).some((k) =>
            (typeof k === "string" ? k : k?.name || "").toLowerCase().includes(q)
          );
        const batchMatch = (p.batch || "").toLowerCase().includes(q) || (p.year || "").toLowerCase().includes(q);

        if (!titleMatch && !abstractMatch && !supervisorMatch && !authorMatch && !techMatch && !batchMatch) {
          return false;
        }
      }

      // Department Filter
      if (selectedDepartment !== "all") {
        const pDept = (p.department || "").toLowerCase();
        const selDept = selectedDepartment.toLowerCase();
        if (!pDept.includes(selDept) && !selDept.includes(pDept)) {
          return false;
        }
      }

      // Academic Level Filter
      if (selectedLevel !== "all") {
        if ((p.academic_level || "").toLowerCase() !== selectedLevel.toLowerCase()) {
          return false;
        }
      }

      // Faculty / Program Filter (BCT, BEI, BCE, etc.)
      if (selectedFaculty !== "all") {
        const fac = selectedFaculty.toLowerCase();
        const authorRollMatch = (p.authors || []).some(
          (a) =>
            (a.rollNumber || "").toLowerCase().includes(fac) ||
            (a.email || "").toLowerCase().includes(fac)
        );
        const titleFacMatch = (p.title || "").toLowerCase().includes(fac);
        const abstractFacMatch = (p.abstract || "").toLowerCase().includes(fac);

        if (!authorRollMatch && !titleFacMatch && !abstractFacMatch) {
          return false;
        }
      }

      // Year / Batch Filter
      if (selectedYear !== "all") {
        const pYear = (p.year || "").toString();
        const pBatch = (p.batch || "").toString();
        if (!pYear.includes(selectedYear) && !selectedYear.includes(pYear) && !pBatch.includes(selectedYear)) {
          return false;
        }
      }

      // Project Type Filter (Minor vs Major)
      if (selectedProjectType !== "all") {
        if ((p.project_type || "").toLowerCase() !== selectedProjectType.toLowerCase()) {
          return false;
        }
      }

      return true;
    });
  }, [projects, searchQuery, selectedDepartment, selectedLevel, selectedFaculty, selectedYear, selectedProjectType]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filteredProjects.length / PAGE_SIZE));
  const currentProjects = useMemo(
    () => filteredProjects.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE),
    [filteredProjects, currentPage]
  );

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(1);
  }, [currentPage, totalPages]);

  const activeFilterCount =
    (searchQuery ? 1 : 0) +
    (selectedDepartment !== "all" ? 1 : 0) +
    (selectedLevel !== "all" ? 1 : 0) +
    (selectedFaculty !== "all" ? 1 : 0) +
    (selectedYear !== "all" ? 1 : 0) +
    (selectedProjectType !== "all" ? 1 : 0);

  // Filter tabs configuration (No "Step 1 2 3 4 5" prefix)
  const stepsConfig = [
    { num: 1, name: "Department", value: selectedDepartment === "all" ? "" : selectedDepartment.replace("Department of ", "") },
    { num: 2, name: "Academic Level", value: selectedLevel === "all" ? "" : selectedLevel },
    { num: 3, name: "Program / Faculty", value: selectedFaculty === "all" ? "" : selectedFaculty.toUpperCase() },
    { num: 4, name: "Batch / Year", value: selectedYear === "all" ? "" : selectedYear },
    { num: 5, name: "Project Category", value: selectedProjectType === "all" ? "" : selectedProjectType },
  ];

  if (loading) {
    return (
      <div className="flex flex-col gap-6 animate-pulse">
        <div className="h-8 bg-surface-raised border border-border-subtle rounded-md w-64"></div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-surface-raised border border-border-subtle rounded-md"></div>
          ))}
        </div>
        <div className="h-48 bg-surface-raised border border-border-subtle rounded-lg"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg bg-surface-raised">
        <p className="text-body font-medium text-text-primary">Failed to load projects.</p>
        <p className="text-body-sm text-text-tertiary mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">
          Browse Projects
        </h1>
        <p className="text-body-sm text-text-secondary">
          Filter and search academic project theses and research repositories across departments.
        </p>
      </div>

      {/* Clean Filter Panel */}
      <div className="bg-surface-raised border border-border-subtle rounded-xl p-5 flex flex-col gap-6 shadow-xs">
        
        {/* Filter Navigation Tabs */}
        <div className="flex flex-col gap-3 border-b border-border-subtle pb-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider font-semibold text-text-secondary">
              Filter Projects
            </span>
            {activeFilterCount > 0 && (
              <button
                onClick={clearAllFilters}
                className="text-xs text-text-tertiary hover:text-error-red underline cursor-pointer"
              >
                Reset Filters
              </button>
            )}
          </div>

          {/* Filter Category Tabs */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 bg-surface-sunken p-2 rounded-lg border border-border-subtle">
            {stepsConfig.map((s) => {
              const isActive = activeStep === s.num;
              const hasValue = Boolean(s.value);

              return (
                <button
                  key={s.num}
                  onClick={() => setActiveStep(s.num)}
                  className={`px-3 py-2 rounded-md transition-all cursor-pointer flex flex-col gap-0.5 text-left border ${
                    isActive
                      ? "bg-surface-canvas border-accent-primary text-text-primary font-semibold shadow-xs"
                      : hasValue
                      ? "bg-surface-canvas/60 border-border-subtle text-accent-primary font-medium hover:border-border-default"
                      : "border-transparent text-text-tertiary hover:text-text-secondary hover:bg-surface-canvas/30"
                  }`}
                >
                  <span className="text-xs font-medium truncate">
                    {s.name}
                  </span>
                  {hasValue && (
                    <span className="text-[11px] font-semibold text-accent-primary truncate">
                      {s.value}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Department Category */}
        {activeStep === 1 && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-wider font-semibold text-text-secondary">
                Select Department
              </span>
              {selectedDepartment !== "all" && (
                <button
                  onClick={() => updateFilterAndTraverse("department", "all", 2)}
                  className="text-xs text-accent-primary hover:underline cursor-pointer font-medium"
                >
                  Skip to Next Category
                </button>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => updateFilterAndTraverse("department", "all", 2)}
                className={`px-3.5 py-2 rounded-md text-xs font-medium transition-all cursor-pointer border ${
                  selectedDepartment === "all"
                    ? "bg-surface-sunken border-2 border-accent-primary text-text-primary font-semibold shadow-xs"
                    : "bg-surface-canvas border-border-subtle text-text-secondary hover:border-border-default hover:text-text-primary"
                }`}
              >
                All Departments ({projects.length})
              </button>

              {departments.map((dept) => {
                const count = departmentCounts[dept.name] || 0;
                const isSelected = selectedDepartment.toLowerCase() === dept.name.toLowerCase();

                return (
                  <button
                    key={dept.id || dept.name}
                    onClick={() => updateFilterAndTraverse("department", dept.name, 2)}
                    className={`px-3.5 py-2 rounded-md text-xs font-medium transition-all cursor-pointer border ${
                      isSelected
                        ? "bg-surface-sunken border-2 border-accent-primary text-text-primary font-semibold shadow-xs"
                        : "bg-surface-canvas border-border-subtle text-text-secondary hover:border-border-default hover:text-text-primary"
                    }`}
                  >
                    {dept.name} {count > 0 && `(${count})`}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Academic Level Category */}
        {activeStep === 2 && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveStep(1)}
                className="text-xs text-text-tertiary hover:text-text-primary cursor-pointer font-mono"
              >
                Back to Department
              </button>
              <span className="text-xs font-mono uppercase tracking-wider font-semibold text-text-secondary">
                Select Academic Level
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {academicLevels.map((lvl) => {
                const isSelected = selectedLevel.toLowerCase() === lvl.id.toLowerCase();
                return (
                  <button
                    key={lvl.id}
                    onClick={() => updateFilterAndTraverse("level", lvl.id, 3)}
                    className={`px-4 py-2 rounded-md text-xs font-medium transition-all cursor-pointer border ${
                      isSelected
                        ? "bg-surface-sunken border-2 border-accent-primary text-text-primary font-semibold shadow-xs"
                        : "bg-surface-canvas border-border-subtle text-text-secondary hover:border-border-default hover:text-text-primary"
                    }`}
                  >
                    {lvl.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Program / Faculty Category */}
        {activeStep === 3 && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveStep(2)}
                className="text-xs text-text-tertiary hover:text-text-primary cursor-pointer font-mono"
              >
                Back to Academic Level
              </button>
              <span className="text-xs font-mono uppercase tracking-wider font-semibold text-text-secondary">
                Select Program / Faculty
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {facultyChoices.map((fac) => {
                const isSelected = selectedFaculty.toLowerCase() === fac.code.toLowerCase();
                return (
                  <button
                    key={fac.code}
                    onClick={() => updateFilterAndTraverse("faculty", fac.code, 4)}
                    className={`px-4 py-2 rounded-md text-xs font-medium transition-all cursor-pointer border ${
                      isSelected
                        ? "bg-surface-sunken border-2 border-accent-primary text-text-primary font-semibold shadow-xs"
                        : "bg-surface-canvas border-border-subtle text-text-secondary hover:border-border-default hover:text-text-primary"
                    }`}
                  >
                    {fac.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Batch / Year Category */}
        {activeStep === 4 && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveStep(3)}
                className="text-xs text-text-tertiary hover:text-text-primary cursor-pointer font-mono"
              >
                Back to Program / Faculty
              </button>
              <span className="text-xs font-mono uppercase tracking-wider font-semibold text-text-secondary">
                Select Batch / Year
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {availableYears.map((yr) => {
                const isSelected = selectedYear.toLowerCase() === yr.id.toLowerCase();
                return (
                  <button
                    key={yr.id}
                    onClick={() => updateFilterAndTraverse("year", yr.id, 5)}
                    className={`px-4 py-2 rounded-md text-xs font-medium transition-all cursor-pointer border ${
                      isSelected
                        ? "bg-surface-sunken border-2 border-accent-primary text-text-primary font-semibold shadow-xs"
                        : "bg-surface-canvas border-border-subtle text-text-secondary hover:border-border-default hover:text-text-primary"
                    }`}
                  >
                    {yr.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Project Category (Minor vs Major) */}
        {activeStep === 5 && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <button
                onClick={() => setActiveStep(4)}
                className="text-xs text-text-tertiary hover:text-text-primary cursor-pointer font-mono"
              >
                Back to Batch / Year
              </button>
              <span className="text-xs font-mono uppercase tracking-wider font-semibold text-text-secondary">
                Select Project Category (Major / Minor)
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {projectTypes.map((pt) => {
                const isSelected = selectedProjectType.toLowerCase() === pt.id.toLowerCase();
                return (
                  <button
                    key={pt.id}
                    onClick={() => updateFilterAndTraverse("type", pt.id, 5)}
                    className={`px-4 py-2 rounded-md text-xs font-medium transition-all cursor-pointer border ${
                      isSelected
                        ? "bg-surface-sunken border-2 border-accent-primary text-text-primary font-semibold shadow-xs"
                        : "bg-surface-canvas border-border-subtle text-text-secondary hover:border-border-default hover:text-text-primary"
                    }`}
                  >
                    {pt.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Results Counter */}
      <div className="flex items-center justify-between px-1">
        <p className="text-body-sm text-text-secondary">
          Showing <strong className="text-text-primary">{filteredProjects.length}</strong> projects
        </p>

        {totalPages > 1 && (
          <span className="text-micro font-mono text-text-tertiary">
            Page {currentPage} of {totalPages}
          </span>
        )}
      </div>

      {/* Projects Grid */}
      {filteredProjects.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg bg-surface-raised/40">
          <p className="text-body text-text-secondary font-medium">No projects match the selected filter parameters.</p>
          <p className="text-body-sm text-text-tertiary mt-1">Try selecting different options or resetting filters.</p>
          <button
            onClick={clearAllFilters}
            className="mt-4 px-4 py-2 bg-surface-raised border border-border-default text-text-primary text-xs font-semibold rounded hover:border-border-strong cursor-pointer"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {currentProjects.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                className="bg-surface-raised border border-border-subtle hover:border-border-default rounded-lg p-5 flex flex-col gap-3 transition-all group"
              >
                {/* Header badges */}
                <div className="flex items-center justify-between gap-2 text-micro font-mono text-text-tertiary">
                  <span className="bg-surface-sunken px-2 py-0.5 rounded border border-border-subtle/50 font-semibold text-text-primary truncate max-w-[180px]">
                    {getDepartmentAcronym(p.department)}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {p.project_type && (
                      <span className="bg-surface-sunken px-2 py-0.5 rounded border border-border-subtle/50 text-text-primary font-semibold">
                        {p.project_type}
                      </span>
                    )}
                    {p.year && (
                      <span className="bg-surface-sunken px-2 py-0.5 rounded border border-border-subtle/50">
                        {p.year}
                      </span>
                    )}
                  </div>
                </div>

                {/* Title */}
                <h3 className="text-body font-semibold text-text-primary leading-snug group-hover:text-accent-primary transition-colors line-clamp-2">
                  {p.title}
                </h3>

                {/* Abstract */}
                <p className="text-body-sm text-text-secondary line-clamp-2 leading-relaxed">
                  {p.abstract || "No abstract snippet available."}
                </p>

                {/* Footer */}
                <div className="border-t border-border-subtle pt-3 mt-auto flex flex-col gap-2 text-micro text-text-secondary">
                  <div className="flex justify-between items-center">
                    <span className="truncate">
                      <span className="text-text-tertiary">Supervisor: </span>
                      <span className="text-text-primary font-medium">{p.supervisor || "—"}</span>
                    </span>
                    <span className="text-accent-primary text-xs font-bold group-hover:translate-x-1 transition-transform">
                      &rarr;
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1">
                    {(p.technologies || []).slice(0, 3).map((t) => (
                      <span key={t} className="bg-surface-sunken px-1.5 py-0.5 rounded text-micro font-mono text-text-tertiary">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination controls (6 projects per page) */}
          <div className="flex items-center justify-between border-t border-border-subtle pt-5 text-micro font-mono">
            <span className="text-text-tertiary">
              Page {currentPage} of {totalPages} ({filteredProjects.length} projects total)
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-3.5 py-1.5 rounded border border-border-default bg-surface-raised text-text-secondary hover:text-text-primary disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed flex items-center gap-1.5 transition-all"
              >
                <FontAwesomeIcon icon={faChevronLeft} /> Previous
              </button>
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-3.5 py-1.5 rounded border border-border-default bg-surface-raised text-text-secondary hover:text-text-primary disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed flex items-center gap-1.5 transition-all"
              >
                Next <FontAwesomeIcon icon={faChevronRight} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}