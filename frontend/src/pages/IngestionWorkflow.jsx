import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ingestionApi,
  metadataApi,
  organizationApi,
  accountsApi,
} from "../api/client";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faSpinner,
  faCheckCircle,
  faCircleExclamation,
  faChevronLeft,
  faChevronRight,
  faPlus,
  faTrash,
  faArrowUp,
  faArrowDown,
  faUserPlus,
  faTags,
  faFileLines,
  faBuilding,
  faGraduationCap,
  faBookOpen,
  faEye,
  faRocket,
  faCodeBranch,
  faSearch,
  faFilePdf,
  faColumns,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";

const CANONICAL_SECTIONS = [
  "Introduction",
  "Background",
  "Literature Review",
  "Methodology",
  "Implementation",
  "Results",
  "Discussion",
  "Conclusion",
  "Future Work",
  "Evaluation",
  "Recommendations",
  "Appendix",
  "References",
];

function autoCanonicalizeHeading(title) {
  if (!title) return "Introduction";
  const cleaned = title.replace(/^\d+(?:\.\d+)*\s*/, "").trim();
  if (!cleaned) return "Introduction";

  const lower = cleaned.toLowerCase();
  for (const candidate of CANONICAL_SECTIONS) {
    const candLower = candidate.toLowerCase();
    if (lower.includes(candLower) || candLower.includes(lower)) {
      return candidate;
    }
  }

  if (lower.includes("intro")) return "Introduction";
  if (lower.includes("lit") || lower.includes("review")) return "Literature Review";
  if (lower.includes("method") || lower.includes("approach") || lower.includes("design")) return "Methodology";
  if (lower.includes("implement") || lower.includes("system")) return "Implementation";
  if (lower.includes("result") || lower.includes("experiment") || lower.includes("output")) return "Results";
  if (lower.includes("discuss")) return "Discussion";
  if (lower.includes("conclus")) return "Conclusion";
  if (lower.includes("future")) return "Future Work";
  if (lower.includes("evalu")) return "Evaluation";
  if (lower.includes("recommend")) return "Recommendations";
  if (lower.includes("appendix") || lower.includes("annex")) return "Appendix";
  if (lower.includes("ref") || lower.includes("biblio")) return "References";

  return cleaned;
}

export default function IngestionWorkflow() {
  const { id } = useParams();
  const navigate = useNavigate();

  // Workflow job & metadata state
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);

  // Side-by-side PDF preview toggle
  const [showPdf, setShowPdf] = useState(true);

  // Stepper step: 1 (Info), 2 (Abstract), 3 (Keywords), 4 (Sections), 5 (Review)
  const [currentStep, setCurrentStep] = useState(1);
  // editingSections: true when admin clicks "Add Section Content Now" from SECTIONS_PENDING screen
  const [editingSections, setEditingSections] = useState(false);

  // Metadata dropdown choices
  const [choices, setChoices] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [campuses, setCampuses] = useState([]);
  const [researchGroups, setResearchGroups] = useState([]);
  const [facultyList, setFacultyList] = useState([]);

  // Faculty search filter
  const [facultySearch, setFacultySearch] = useState("");

  // Form State (copied from extracted_payload)
  const [projectFields, setProjectFields] = useState({
    title: "",
    project_type: "Major",
    academic_level: "UG",
    batch: "078",
    department_name: "",
    campus_name: "",
    research_group_name: "",
    repository_url: "",
    abstract: "",
  });

  const [departmentId, setDepartmentId] = useState("");
  const [campusId, setCampusId] = useState("");
  const [researchGroupId, setResearchGroupId] = useState("");

  const [selectedSupervisors, setSelectedSupervisors] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [keywords, setKeywords] = useState([]);
  const [sections, setSections] = useState([]);
  const [skipSections, setSkipSections] = useState(false);

  // Add Faculty Modal State
  const [showAddFacultyModal, setShowAddFacultyModal] = useState(false);
  const [newFaculty, setNewFaculty] = useState({
    full_name: "",
    title: "Dr.",
    designation: "Assistant Professor",
    department: "",
  });
  const [creatingFaculty, setCreatingFaculty] = useState(false);

  // Verification & Publication state
  const [verifying, setVerifying] = useState(false);
  const [verifiedSuccess, setVerifiedSuccess] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});

  // 1. Fetch Job detail
  const fetchJob = useCallback(async () => {
    try {
      const res = await ingestionApi.getJob(id);
      const j = res.data;
      setJob(j);

      // Populate form states when payload exists
      if (j.extracted_payload) {
        const payload = j.extracted_payload;
        const pf = payload.project_fields || {};

        setProjectFields({
          title: pf.title || "",
          project_type: pf.project_type || "Major",
          academic_level: pf.academic_level || "UG",
          batch: pf.batch || "078",
          department_name: pf.department_name || "",
          campus_name: pf.campus_name || "",
          research_group_name: pf.research_group_name || "",
          repository_url: pf.repository_url || pf.github_url || "",
          abstract: pf.abstract || "",
        });

        // Supervisors — start empty for manual selection by admin
        if (Array.isArray(pf.supervisors) && payload._verified_by_admin) {
          setSelectedSupervisors(
            pf.supervisors.map((s) => {
              if (typeof s === "string") return { full_name: s.trim(), title: "", designation: "" };
              return {
                full_name: (s?.full_name || s?.name || "").trim(),
                title: (s?.title || "").trim(),
                designation: (s?.designation || "").trim(),
              };
            }).filter((s) => s.full_name)
          );
        } else {
          setSelectedSupervisors([]);
        }

        // Parse Authors from people_and_roles
        const people = payload.people_and_roles || [];
        const authorList = people
          .filter((p) => (p.role || "").toLowerCase() === "author")
          .map((p, idx) => ({
            id: idx + 1,
            full_name: p.full_name || "",
            roll_number: p.roll_number || "",
            academic_level: p.academic_level || pf.academic_level || "UG",
            display_order: p.display_order || idx + 1,
            matchedStudent: null,
          }));
        setAuthors(authorList.length > 0 ? authorList : [{ id: 1, full_name: "", roll_number: "", academic_level: "UG", display_order: 1 }]);

        // Keywords
        setKeywords(payload.keywords || []);

        // Sections
        const rawSecs = payload.project_sections || [];
        setSections(
          rawSecs.map((s) => ({
            ...s,
            canonical_section: s.canonical_section || autoCanonicalizeHeading(s.heading),
          }))
        );
      }
    } catch (err) {
      setError(err.message || "Failed to load job details.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  // Auto-polling when status is PENDING or PROCESSING
  useEffect(() => {
    if (!job) return;
    if (job.status === "PENDING" || job.status === "PROCESSING") {
      const timer = setInterval(() => {
        fetchJob();
      }, 2500);
      return () => clearInterval(timer);
    }
  }, [job, fetchJob]);

  // Load choices and database entities (parse res.data || res.results || res)
  useEffect(() => {
    metadataApi.getChoices().then((res) => setChoices(res.data)).catch(() => { });
    organizationApi.getDepartments().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setDepartments(list);
    }).catch(() => { });

    organizationApi.getCampuses().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setCampuses(list);
    }).catch(() => { });

    organizationApi.getResearchGroups().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setResearchGroups(list);
    }).catch(() => { });

    accountsApi.getFacultyList().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setFacultyList(list);
    }).catch(() => { });
  }, []);

  // Pre-select database records by extracted names
  useEffect(() => {
    if (departments.length > 0 && projectFields.department_name) {
      const match = departments.find(
        (d) => d.name.toLowerCase() === projectFields.department_name.toLowerCase()
      );
      if (match) setDepartmentId(match.id);
    }
  }, [departments, projectFields.department_name]);

  useEffect(() => {
    if (campuses.length > 0 && projectFields.campus_name) {
      const match = campuses.find(
        (c) => c.name.toLowerCase() === projectFields.campus_name.toLowerCase()
      );
      if (match) setCampusId(match.id);
    }
  }, [campuses, projectFields.campus_name]);

  useEffect(() => {
    if (researchGroups.length > 0 && projectFields.research_group_name) {
      const match = researchGroups.find(
        (rg) => rg.name.toLowerCase() === projectFields.research_group_name.toLowerCase()
      );
      if (match) setResearchGroupId(match.id);
    }
  }, [researchGroups, projectFields.research_group_name]);

  // Filter Faculty Supervisors by Department
  const filteredFacultyList = useMemo(() => {
    if (!departmentId) return facultyList;
    return facultyList.filter((f) => String(f.department_id) === String(departmentId));
  }, [facultyList, departmentId]);

  const searchedFaculty = useMemo(() => {
    const baseList = filteredFacultyList.length > 0 ? filteredFacultyList : facultyList;
    if (!facultySearch.trim()) return baseList;
    const q = facultySearch.toLowerCase();
    return baseList.filter(
      (f) =>
        (f.full_name || "").toLowerCase().includes(q) ||
        (f.designation || "").toLowerCase().includes(q)
    );
  }, [filteredFacultyList, facultyList, facultySearch]);

  // Fetch logs on demand
  const handleFetchLogs = async () => {
    try {
      const res = await ingestionApi.getJobLogs(id);
      setLogs(res.data || []);
      setShowLogs(true);
    } catch (err) {
      console.error(err);
    }
  };

  // Author Management
  const handleAddAuthor = () => {
    setAuthors((prev) => [
      ...prev,
      {
        id: Date.now(),
        full_name: "",
        roll_number: "",
        academic_level: projectFields.academic_level || "UG",
        display_order: prev.length + 1,
        matchedStudent: null,
      },
    ]);
  };

  const handleRemoveAuthor = (idx) => {
    setAuthors((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleAuthorChange = (idx, field, value) => {
    setAuthors((prev) => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], [field]: value };
      return updated;
    });
  };

  const handleMatchStudentByRoll = async (idx, rollNumber) => {
    if (!rollNumber || !rollNumber.trim()) return;
    try {
      const res = await accountsApi.getStudents({ roll_number: rollNumber.trim() });
      const matched = res.data?.[0];
      setAuthors((prev) => {
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          matchedStudent: matched || null,
          full_name: matched ? matched.full_name : updated[idx].full_name,
        };
        return updated;
      });
    } catch (err) {
      console.error(err);
    }
  };

  // Inline Faculty Creation
  const handleCreateFaculty = async (e) => {
    e.preventDefault();
    if (!newFaculty.full_name) return;
    setCreatingFaculty(true);
    try {
      const res = await accountsApi.createFaculty({
        ...newFaculty,
        department: departmentId || departments[0]?.id || null,
      });
      const created = res.data;
      setFacultyList((prev) => [...prev, created]);
      setSelectedSupervisors((prev) => [
        ...prev,
        {
          full_name: created.full_name,
          title: created.title || "",
          designation: created.designation || "",
        },
      ]);
      setShowAddFacultyModal(false);
      setNewFaculty({ full_name: "", title: "Dr.", designation: "Assistant Professor", department: "" });
    } catch (err) {
      alert("Failed to create faculty member: " + err.message);
    } finally {
      setCreatingFaculty(false);
    }
  };

  // Keyword Chip Management
  const [newKeywordInput, setNewKeywordInput] = useState("");
  const handleAddKeyword = () => {
    const val = newKeywordInput.trim();
    if (val && !keywords.includes(val)) {
      setKeywords((prev) => [...prev, val]);
      setNewKeywordInput("");
    }
  };

  const handleRemoveKeyword = (idx) => {
    setKeywords((prev) => prev.filter((_, i) => i !== idx));
  };

  // Section Editor Management (with Automatic Canonicalization)
  const handleAddSection = () => {
    setSections((prev) => [
      ...prev,
      {
        heading: "New Section",
        canonical_section: "Introduction",
        heading_level: 1,
        display_order: prev.length + 1,
        content: "",
        page_start: 1,
        page_end: 1,
        word_count: 0,
      },
    ]);
  };

  const handleSectionChange = (idx, field, value) => {
    setSections((prev) => {
      const updated = [...prev];
      const sec = { ...updated[idx], [field]: value };
      if (field === "heading") {
        sec.canonical_section = autoCanonicalizeHeading(value);
      }
      if (field === "content") {
        sec.word_count = (value.match(/\w+/g) || []).length;
      }
      updated[idx] = sec;
      return updated;
    });
  };

  const handleMoveSection = (idx, direction) => {
    setSections((prev) => {
      const updated = [...prev];
      const targetIdx = direction === "up" ? idx - 1 : idx + 1;
      if (targetIdx < 0 || targetIdx >= updated.length) return prev;
      const temp = updated[idx];
      updated[idx] = updated[targetIdx];
      updated[targetIdx] = temp;
      return updated.map((s, i) => ({ ...s, display_order: i + 1 }));
    });
  };

  const handleDeleteSection = (idx) => {
    setSections((prev) => prev.filter((_, i) => i !== idx).map((s, i) => ({ ...s, display_order: i + 1 })));
  };

  // Validation
  const validateForm = () => {
    const errors = {};
    if (!projectFields.title.trim()) errors.title = "Title is required.";
    if (!projectFields.batch || !/^\d{3}$/.test(projectFields.batch)) {
      errors.batch = "Batch must be exactly 3 digits (e.g. 078).";
    }
    const validAuthors = authors.filter((a) => a.full_name.trim());
    if (validAuthors.length === 0) errors.authors = "At least one author full name is required.";

    const authorNames = validAuthors.map((a) => a.full_name.trim().toLowerCase());
    const duplicates = authorNames.filter((item, index) => authorNames.indexOf(item) !== index);
    if (duplicates.length > 0) errors.authors = `Duplicate author names found: ${duplicates.join(", ")}`;

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Verify / Patch Payload
  const handleVerifyMetadata = async () => {
    if (!validateForm()) {
      setCurrentStep(5);
      return;
    }
    setVerifying(true);
    setVerifiedSuccess(false);

    try {
      const selectedDept = departments.find((d) => String(d.id) === String(departmentId));
      const selectedCamp = campuses.find((c) => String(c.id) === String(campusId));
      const selectedRG = researchGroups.find((rg) => String(rg.id) === String(researchGroupId));

      const updatedAuthors = authors
        .filter((a) => a.full_name.trim())
        .map((a, idx) => ({
          full_name: a.full_name.trim(),
          role: "Author",
          roll_number: a.roll_number.trim(),
          academic_level: a.academic_level || projectFields.academic_level,
          designation: "",
          display_order: idx + 1,
        }));

      const updatedSupervisors = selectedSupervisors
        .filter((s) => (typeof s === "string" ? s.trim() : s?.full_name?.trim()))
        .map((sObj, idx) => {
          const isObj = typeof sObj === "object" && sObj !== null;
          const name = isObj ? (sObj.full_name || "").trim() : sObj.trim();
          const title = isObj ? (sObj.title || "").trim() : "";
          const designation = isObj ? (sObj.designation || "").trim() : "";
          const matchedFac = facultyList.find((f) => f.full_name.toLowerCase() === name.toLowerCase());

          return {
            full_name: name,
            title: title || matchedFac?.title || "",
            designation: designation || matchedFac?.designation || "",
            role: "Supervisor",
            academic_level: "Faculty",
            display_order: updatedAuthors.length + idx + 1,
          };
        });

      // Exclude existing authors AND supervisors/co-supervisors so deleted supervisors are removed!
      const MANAGED_ROLES = new Set(["author", "supervisor", "co-supervisor", "co supervisor"]);
      const existingOtherPeople = (job.extracted_payload?.people_and_roles || []).filter(
        (p) => !MANAGED_ROLES.has((p.role || "").toLowerCase().trim())
      );

      const people_and_roles = [...updatedAuthors, ...updatedSupervisors, ...existingOtherPeople];

      const patchData = {
        _verified_by_admin: true,
        project_fields: {
          title: projectFields.title.trim(),
          project_type: projectFields.project_type,
          academic_level: projectFields.academic_level,
          batch: projectFields.batch,
          department_name: selectedDept ? selectedDept.name : projectFields.department_name,
          campus_name: selectedCamp ? selectedCamp.name : projectFields.campus_name,
          research_group_name: selectedRG ? selectedRG.name : projectFields.research_group_name,
          supervisors: selectedSupervisors.map((s) =>
            typeof s === "string"
              ? s
              : { full_name: s.full_name, title: s.title || "", designation: s.designation || "" }
          ),
          repository_url: projectFields.repository_url.trim(),
          abstract: projectFields.abstract.trim(),
        },
        people_and_roles,
        keywords,
      };

      if (!skipSections) {
        patchData.project_sections = sections.map((s, idx) => ({
          heading: s.heading,
          canonical_section: s.canonical_section || autoCanonicalizeHeading(s.heading),
          heading_level: parseInt(s.heading_level) || 1,
          display_order: idx + 1,
          content: s.content,
          page_start: s.page_start ? parseInt(s.page_start) : null,
          page_end: s.page_end ? parseInt(s.page_end) : null,
          word_count: s.word_count || 0,
        }));
      }

      // Tell the backend whether sections were skipped so it can set SECTIONS_PENDING
      patchData._sections_skipped = skipSections;

      await ingestionApi.patchJobPayload(id, patchData);
      await fetchJob();
      setVerifiedSuccess(true);
    } catch (err) {
      alert("Verification patch failed: " + err.message);
    } finally {
      setVerifying(false);
    }
  };

  // Publish Project
  const handlePublishProject = async () => {
    setPublishing(true);
    try {
      const res = await ingestionApi.publishJob(id);
      const publishedId = res.data?.project_id;
      if (publishedId) {
        navigate(`/projects/${publishedId}`);
      } else {
        await fetchJob();
      }
    } catch (err) {
      alert("Publish failed: " + err.message);
    } finally {
      setPublishing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <FontAwesomeIcon icon={faSpinner} className="animate-spin h-8 w-8 text-accent-primary" />
        <p className="text-body font-mono text-text-secondary">Loading submission details...</p>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-3xl mx-auto py-12 text-center flex flex-col items-center gap-4">
        <div className="h-16 w-16 rounded-full bg-error-red/10 border border-error-red/20 flex items-center justify-center text-error-red">
          <FontAwesomeIcon icon={faCircleExclamation} className="h-8 w-8" />
        </div>
        <h2 className="text-h2 font-bold text-text-primary">Failed to load Submission #{id}</h2>
        <p className="text-body-sm text-text-secondary">{error || "Submission not found."}</p>
        <Link
          to="/admin/approvals"
          className="mt-2 px-4 py-2 bg-surface-raised border border-border-default rounded-md text-text-primary text-body-sm font-medium hover:border-border-strong transition-all"
        >
          Return to Submissions
        </Link>
      </div>
    );
  }

  // State 1: PENDING or PROCESSING
  if (job.status === "PENDING" || job.status === "PROCESSING") {
    return (
      <div className="max-w-3xl mx-auto py-12 flex flex-col items-center text-center gap-6">
        <div className="relative">
          <div className="h-24 w-24 rounded-full bg-accent-primary/10 border border-accent-primary/30 flex items-center justify-center text-accent-primary animate-pulse">
            <FontAwesomeIcon icon={faSpinner} className="animate-spin h-10 w-10" />
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-micro font-mono uppercase tracking-wider text-warning-amber bg-warning-amber/10 border border-warning-amber/20 px-3 py-1 rounded-full w-fit mx-auto">
            Submission #{job.id} &middot; {job.status}
          </span>
          <h2 className="text-h2 font-bold text-text-primary">
            Processing Document Text & Structure
          </h2>
          <p className="text-body text-text-secondary max-w-lg leading-relaxed">
            The repository system is processing <span className="font-semibold text-text-primary">{job.original_filename}</span>, organizing author details, and cataloging section text.
          </p>
        </div>

        <div className="flex items-center gap-4 border-t border-border-subtle pt-6 w-full justify-center">
          <button
            onClick={handleFetchLogs}
            className="px-4 py-2 rounded-md bg-surface-raised border border-border-default text-text-secondary text-body-sm font-medium hover:text-text-primary transition-all cursor-pointer"
          >
            View Processing Details
          </button>
        </div>

        {showLogs && (
          <div className="w-full text-left bg-surface-sunken border border-border-subtle rounded-lg p-4 font-mono text-xs max-h-64 overflow-y-auto">
            <p className="text-text-tertiary uppercase text-[10px] mb-2 font-bold">Processing Details:</p>
            {logs.length === 0 ? (
              <p className="text-text-tertiary">No processing log entries yet.</p>
            ) : (
              logs.map((l) => (
                <div key={l.id} className="py-0.5 border-b border-border-subtle/30 text-text-secondary">
                  <span className="text-accent-primary">[{l.level}]</span> {l.message}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    );
  }

  // State 2: FAILED
  if (job.status === "FAILED") {
    return (
      <div className="max-w-3xl mx-auto py-12 flex flex-col items-center text-center gap-6">
        <div className="h-20 w-20 rounded-full bg-error-red/10 border border-error-red/20 flex items-center justify-center text-error-red">
          <FontAwesomeIcon icon={faCircleExclamation} className="h-10 w-10" />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-micro font-mono uppercase tracking-wider text-error-red bg-error-red/10 border border-error-red/20 px-3 py-1 rounded-full w-fit mx-auto">
            Processing Error &middot; Submission #{job.id}
          </span>
          <h2 className="text-h2 font-bold text-text-primary">
            Document Processing Encountered an Error
          </h2>
          <p className="text-body text-text-secondary max-w-lg">
            {job.error_message || "Unable to extract content from the PDF file."}
          </p>
        </div>

        <div className="flex items-center gap-4 border-t border-border-subtle pt-6">
          <button
            onClick={handleFetchLogs}
            className="px-4 py-2 rounded-md bg-surface-raised border border-border-default text-text-secondary text-body-sm font-medium hover:text-text-primary transition-all cursor-pointer"
          >
            View Logs
          </button>
          <Link
            to="/admin/upload"
            className="px-4 py-2 rounded-md bg-accent-primary text-white text-body-sm font-medium hover:bg-accent-primary/90 transition-all"
          >
            Retry Upload
          </Link>
        </div>

        {showLogs && (
          <div className="w-full text-left bg-surface-sunken border border-border-subtle rounded-lg p-4 font-mono text-xs max-h-64 overflow-y-auto">
            <p className="text-text-tertiary uppercase text-[10px] mb-2 font-bold">Error Details:</p>
            {logs.map((l) => (
              <div key={l.id} className="py-0.5 text-error-red/80">
                [{l.level}] {l.message}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // State 3: VERIFIED / Published — fully complete
  if (job.status === "VERIFIED" && job.published_project) {
    return (
      <div className="max-w-3xl mx-auto py-12 flex flex-col items-center text-center gap-6">
        <div className="h-20 w-20 rounded-full bg-success-emerald/10 border border-success-emerald/20 flex items-center justify-center text-success-emerald">
          <FontAwesomeIcon icon={faCheckCircle} className="h-10 w-10" />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-micro font-mono uppercase tracking-wider text-success-emerald bg-success-emerald/10 border border-success-emerald/20 px-3 py-1 rounded-full w-fit mx-auto">
            Published &middot; Submission #{job.id}
          </span>
          <h2 className="text-h2 font-bold text-text-primary">
            Project Report Published to Repository Catalog
          </h2>
          <p className="text-body text-text-secondary max-w-lg">
            This project has been verified and published into the academic repository catalog.
          </p>
        </div>

        <Link
          to={`/projects/${job.published_project}`}
          className="px-6 py-2.5 rounded-md bg-accent-primary text-white text-body-sm font-medium hover:bg-accent-primary/90 flex items-center gap-2 transition-all shadow-sm"
        >
          <FontAwesomeIcon icon={faEye} />
          View Published Project Page
        </Link>
      </div>
    );
  }

  // State 3b: SECTIONS_PENDING — published but sections not yet added
  // (only show splash if not actively editing sections)
  if (job.status === "SECTIONS_PENDING" && job.published_project && !editingSections) {
    return (
      <div className="max-w-3xl mx-auto py-12 flex flex-col items-center text-center gap-6">
        <div className="h-20 w-20 rounded-full bg-warning-amber/10 border border-warning-amber/20 flex items-center justify-center text-warning-amber">
          <FontAwesomeIcon icon={faFileLines} className="h-10 w-10" />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-micro font-mono uppercase tracking-wider text-warning-amber bg-warning-amber/10 border border-warning-amber/20 px-3 py-1 rounded-full w-fit mx-auto">
            Sections Incomplete &middot; Submission #{job.id}
          </span>
          <h2 className="text-h2 font-bold text-text-primary">
            Project is Live — Section Content Pending
          </h2>
          <p className="text-body text-text-secondary max-w-lg leading-relaxed">
            <span className="font-semibold text-text-primary">{job.original_filename}</span> has been
            published to the repository catalog, but its section content has not yet been added.
            Add sections now to complete the record.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to={`/projects/${job.published_project}`}
            className="px-4 py-2 rounded-md bg-surface-raised border border-border-default text-text-secondary text-body-sm font-medium hover:text-text-primary transition-all flex items-center gap-2"
          >
            <FontAwesomeIcon icon={faEye} />
            View Published Project
          </Link>
          <button
            type="button"
            onClick={() => { setEditingSections(true); setCurrentStep(4); }}
            className="px-6 py-2.5 rounded-md bg-warning-amber text-white text-body-sm font-medium hover:bg-warning-amber/90 flex items-center gap-2 transition-all shadow-sm cursor-pointer"
          >
            <FontAwesomeIcon icon={faFileLines} />
            Add Section Content Now
          </button>
        </div>
      </div>
    );
  }

  // State 4: EXTRACTED — Guided 5-Step Form Stepper (with optional PDF Split View)
  const batchOptions = choices?.batch?.options || [
    "065", "066", "067", "068", "069", "070", "071", "072", "073", "074", "075", "076", "077", "078", "079", "080", "081", "082"
  ];
  const academicLevelChoices = choices?.academic_levels || [
    { value: "UG", label: "UG" },
    { value: "Masters", label: "Masters" },
    { value: "PhD", label: "PhD" },
    { value: "Faculty", label: "Faculty" },
  ];
  const projectTypeChoices = choices?.project_types || [
    { value: "Major", label: "Major" },
    { value: "Minor", label: "Minor" },
    { value: "Thesis", label: "Thesis" },
    { value: "Faculty Project", label: "Faculty Project" },
    { value: "Research", label: "Research" },
  ];

  return (
    <div className="max-w-[1600px] mx-auto flex flex-col gap-6 py-4">
      {/* Header Read-Only Metadata & Split-View Controls */}
      <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            {job.status === "SECTIONS_PENDING" ? (
              <span className="text-micro font-mono uppercase tracking-wider text-warning-amber bg-warning-amber/10 border border-warning-amber/20 px-2 py-0.5 rounded-sm">
                Sections Incomplete
              </span>
            ) : (
              <span className="text-micro font-mono uppercase tracking-wider text-accent-primary bg-accent-primary/10 border border-accent-primary/20 px-2 py-0.5 rounded-sm">
                Document Verification
              </span>
            )}
            <span className="text-micro font-mono text-text-tertiary">
              SUBMISSION #{job.id}
            </span>
          </div>
          <h2 className="text-h2 font-bold text-text-primary leading-tight">
            {job.original_filename}
          </h2>
          <p className="text-micro font-mono text-text-secondary mt-0.5">
            Uploaded by: {job.uploaded_by_email || "Admin"} &middot; {new Date(job.created_at).toLocaleDateString()}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {job.file && (
            <button
              type="button"
              onClick={() => setShowPdf(!showPdf)}
              className={`px-3.5 py-2 rounded-md border text-body-sm font-medium transition-all flex items-center gap-2 cursor-pointer ${showPdf
                ? "bg-accent-primary/10 border-accent-primary text-accent-primary"
                : "bg-surface-sunken border-border-default text-text-secondary hover:text-text-primary"
                }`}
            >
              <FontAwesomeIcon icon={faColumns} className="h-4 w-4" />
              {showPdf ? "Hide PDF Side-by-Side" : "Show PDF Side-by-Side"}
            </button>
          )}

          <button
            onClick={handleFetchLogs}
            className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-subtle text-text-secondary text-body-sm hover:text-text-primary transition-all cursor-pointer"
          >
            View Logs
          </button>
        </div>
      </div>

      {/* Stepper Navigation Bar */}
      <div className="grid grid-cols-5 gap-2 border-b border-border-subtle pb-4">
        {[
          { step: 1, label: "1. Details", icon: faBuilding },
          { step: 2, label: "2. Abstract", icon: faBookOpen },
          { step: 3, label: "3. Keywords", icon: faTags },
          { step: 4, label: "4. Sections", icon: faFileLines },
          { step: 5, label: "5. Publish", icon: faCheckCircle },
        ].map((s) => (
          <button
            key={s.step}
            onClick={() => setCurrentStep(s.step)}
            className={`flex flex-col sm:flex-row items-center justify-center gap-2 p-3 rounded-lg border text-body-sm font-medium transition-all cursor-pointer ${currentStep === s.step
              ? "bg-accent-primary/10 border-accent-primary text-accent-primary font-semibold shadow-sm"
              : "bg-surface-raised border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-default"
              }`}
          >
            <FontAwesomeIcon icon={s.icon} className="h-4 w-4 shrink-0" />
            <span className="truncate">{s.label}</span>
          </button>
        ))}
      </div>

      {/* Main Split-Screen / Full-Width Container */}
      <div className={`grid grid-cols-1 ${showPdf && job.file ? "lg:grid-cols-12" : ""} gap-6 items-start`}>
        {/* Left Side PDF Viewer (when split-view enabled) */}
        {showPdf && job.file && (
          <div className="lg:col-span-6 sticky top-20 bg-surface-raised border border-border-default rounded-xl overflow-hidden h-[calc(100vh-140px)] flex flex-col shadow-lg">
            <div className="bg-surface-sunken px-4 py-2.5 border-b border-border-subtle flex items-center justify-between">
              <span className="text-micro font-mono font-bold text-text-tertiary uppercase flex items-center gap-2">
                <FontAwesomeIcon icon={faFilePdf} className="text-error-red h-4 w-4" />
                Original Document Viewer
              </span>
              <a
                href={job.file}
                target="_blank"
                rel="noreferrer"
                className="text-micro font-mono text-accent-primary hover:underline"
              >
                Open in Full Window ↗
              </a>
            </div>
            <iframe
              src={job.file}
              className="w-full h-full border-0"
              title="PDF Document Viewer"
            />
          </div>
        )}

        {/* Right Side Form Stepper — independently scrollable in split view */}
        <div className={showPdf && job.file ? "lg:col-span-6 flex flex-col gap-6 lg:overflow-y-auto lg:max-h-[calc(100vh-140px)] lg:pr-1" : "flex flex-col gap-6 max-w-5xl mx-auto w-full"}>
          {/* Step 1: Project Information */}
          {currentStep === 1 && (
            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 flex flex-col gap-6">
              <h3 className="text-h3 font-bold text-text-primary flex items-center gap-2">
                <FontAwesomeIcon icon={faBuilding} className="text-accent-primary h-4 w-4" />
                1. General Information
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Title */}
                <div className="md:col-span-2 flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary">
                    Project Title <span className="text-error-red">*</span>
                  </label>
                  <input
                    type="text"
                    value={projectFields.title}
                    onChange={(e) => setProjectFields({ ...projectFields, title: e.target.value })}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                    placeholder="Enter complete project thesis title"
                  />
                  {validationErrors.title && (
                    <span className="text-micro font-mono text-error-red">{validationErrors.title}</span>
                  )}
                </div>

                {/* Project Category */}
                <div className="flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary">
                    Project Category
                  </label>
                  <select
                    value={projectFields.project_type}
                    onChange={(e) => setProjectFields({ ...projectFields, project_type: e.target.value })}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  >
                    {projectTypeChoices.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Academic Level */}
                <div className="flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary">
                    Academic Level
                  </label>
                  <select
                    value={projectFields.academic_level}
                    onChange={(e) => setProjectFields({ ...projectFields, academic_level: e.target.value })}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  >
                    {academicLevelChoices.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Academic Batch */}
                <div className="flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary">
                    Academic Batch
                  </label>
                  <select
                    value={projectFields.batch}
                    onChange={(e) => setProjectFields({ ...projectFields, batch: e.target.value })}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  >
                    {batchOptions.map((b) => (
                      <option key={b} value={b}>
                        Batch {b}
                      </option>
                    ))}
                  </select>
                  {validationErrors.batch && (
                    <span className="text-micro font-mono text-error-red">{validationErrors.batch}</span>
                  )}
                </div>

                {/* Department (Database Record) */}
                <div className="flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary">
                    Department
                  </label>
                  <select
                    value={departmentId}
                    onChange={(e) => setDepartmentId(e.target.value)}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  >
                    <option value="">-- Select Department --</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} {d.campus_name ? `(${d.campus_name})` : ""}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Campus (Database Record) */}
                <div className="flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary">
                    Campus
                  </label>
                  <select
                    value={campusId}
                    onChange={(e) => setCampusId(e.target.value)}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  >
                    <option value="">-- Select Campus --</option>
                    {campuses.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} &middot; {c.location}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Research Group (Database Record) */}
                <div className="flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary">
                    Research Group
                  </label>
                  <select
                    value={researchGroupId}
                    onChange={(e) => setResearchGroupId(e.target.value)}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  >
                    <option value="">-- None / Select Research Group --</option>
                    {researchGroups.map((rg) => (
                      <option key={rg.id} value={rg.id}>
                        {rg.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Repository URL */}
                <div className="md:col-span-2 flex flex-col gap-2">
                  <label className="text-body-sm font-medium text-text-primary flex items-center gap-2">
                    <FontAwesomeIcon icon={faCodeBranch} className="h-3.5 w-3.5 text-text-tertiary" />
                    Repository URL
                  </label>
                  <input
                    type="url"
                    value={projectFields.repository_url}
                    onChange={(e) => setProjectFields({ ...projectFields, repository_url: e.target.value })}
                    className="px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                    placeholder="https://github.com/organization/repo"
                  />
                </div>
              </div>

              {/* Faculty Supervisors Section */}
              <div className="border-t border-border-subtle pt-6 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <label className="text-body font-semibold text-text-primary flex items-center gap-2">
                    <FontAwesomeIcon icon={faGraduationCap} className="text-accent-primary" />
                    Faculty Supervisors
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowAddFacultyModal(true)}
                    className="px-3 py-1.5 rounded-md bg-accent-primary/10 border border-accent-primary/30 text-accent-primary text-body-sm font-medium hover:bg-accent-primary/20 transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <FontAwesomeIcon icon={faUserPlus} className="h-3.5 w-3.5" />
                    Add Faculty
                  </button>
                </div>

                {/* Selected Faculty Pills with Title & Designation */}
                <div className="flex flex-wrap gap-2">
                  {selectedSupervisors.map((s, sIdx) => {
                    const isObj = typeof s === "object" && s !== null;
                    const name = isObj ? s.full_name : s;
                    const title = isObj && s.title ? `${s.title} ` : "";
                    const desig = isObj && s.designation ? ` (${s.designation})` : "";
                    const label = `${title}${name}${desig}`;

                    return (
                      <span
                        key={sIdx}
                        className="bg-accent-primary/10 border border-accent-primary/30 text-accent-primary text-body-sm px-3 py-1.5 rounded-full flex items-center gap-2 font-medium"
                      >
                        <span>{label}</span>
                        <button
                          type="button"
                          onClick={() => setSelectedSupervisors(selectedSupervisors.filter((_, i) => i !== sIdx))}
                          className="hover:text-error-red transition-colors cursor-pointer"
                        >
                          <FontAwesomeIcon icon={faXmark} className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    );
                  })}
                  {selectedSupervisors.length === 0 && (
                    <p className="text-body-sm text-text-tertiary">No supervisors assigned yet.</p>
                  )}
                </div>

                {/* Search & Selector */}
                <div className="flex flex-col gap-2 bg-surface-sunken p-3 rounded-lg border border-border-subtle">
                  <input
                    type="text"
                    placeholder="Search faculty directory by name..."
                    value={facultySearch}
                    onChange={(e) => setFacultySearch(e.target.value)}
                    className="w-full px-3 py-1.5 rounded bg-surface-raised border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  />

                  <div className="max-h-40 overflow-y-auto flex flex-col gap-1 pr-1">
                    {searchedFaculty.map((f) => {
                      const isSel = selectedSupervisors.some((s) => {
                        const name = typeof s === "string" ? s : (s?.full_name || "");
                        return name.toLowerCase().trim() === f.full_name.toLowerCase().trim();
                      });

                      return (
                        <div
                          key={f.id}
                          onClick={() => {
                            if (isSel) {
                              setSelectedSupervisors(
                                selectedSupervisors.filter((s) => {
                                  const name = typeof s === "string" ? s : (s?.full_name || "");
                                  return name.toLowerCase().trim() !== f.full_name.toLowerCase().trim();
                                })
                              );
                            } else {
                              setSelectedSupervisors([
                                ...selectedSupervisors,
                                { full_name: f.full_name, title: f.title || "", designation: f.designation || "" },
                              ]);
                            }
                          }}
                          className={`px-3 py-1.5 rounded text-body-sm cursor-pointer flex items-center justify-between transition-colors ${isSel
                            ? "bg-accent-primary/10 text-accent-primary font-semibold"
                            : "hover:bg-surface-hover text-text-secondary hover:text-text-primary"
                            }`}
                        >
                          <span>
                            {f.title ? `${f.title} ` : ""}{f.full_name}{" "}
                            <span className="text-micro text-text-tertiary font-mono">
                              ({f.designation || "Faculty"})
                            </span>
                          </span>
                          {isSel && <FontAwesomeIcon icon={faCheckCircle} className="h-3.5 w-3.5 text-accent-primary" />}
                        </div>
                      );
                    })}
                    {searchedFaculty.length === 0 && (
                      <p className="text-micro font-mono text-text-tertiary p-2">No matching faculty found.</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Authors Section */}
              <div className="border-t border-border-subtle pt-6 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <label className="text-body font-semibold text-text-primary flex items-center gap-2">
                    <FontAwesomeIcon icon={faGraduationCap} className="text-accent-violet" />
                    Authors / Student Members <span className="text-error-red">*</span>
                  </label>
                  <button
                    type="button"
                    onClick={handleAddAuthor}
                    className="px-3 py-1.5 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm font-medium hover:bg-surface-hover transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <FontAwesomeIcon icon={faPlus} className="h-3.5 w-3.5" />
                    Add Author
                  </button>
                </div>

                {validationErrors.authors && (
                  <span className="text-micro font-mono text-error-red">{validationErrors.authors}</span>
                )}

                <div className="flex flex-col gap-3">
                  {authors.map((author, idx) => (
                    <div
                      key={author.id || idx}
                      className="bg-surface-sunken border border-border-subtle rounded-lg p-4 flex flex-col sm:flex-row items-start sm:items-center gap-3"
                    >
                      <span className="text-micro font-mono text-text-tertiary w-6 shrink-0">
                        #{idx + 1}
                      </span>

                      <input
                        type="text"
                        placeholder="Full Name"
                        value={author.full_name}
                        onChange={(e) => handleAuthorChange(idx, "full_name", e.target.value)}
                        className="flex-1 px-3 py-1.5 rounded bg-surface-raised border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                      />

                      <div className="flex items-center gap-2 w-full sm:w-auto">
                        <input
                          type="text"
                          placeholder="Roll (e.g. 075BCT001)"
                          value={author.roll_number}
                          onChange={(e) => handleAuthorChange(idx, "roll_number", e.target.value)}
                          className="w-36 px-3 py-1.5 rounded bg-surface-raised border border-border-default text-text-primary text-body-sm font-mono focus:outline-none focus:border-accent-primary"
                        />

                        <button
                          type="button"
                          title="Match Student DB"
                          onClick={() => handleMatchStudentByRoll(idx, author.roll_number)}
                          className="p-2 rounded bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 transition-all shrink-0 cursor-pointer"
                        >
                          <FontAwesomeIcon icon={faSearch} className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {author.matchedStudent && (
                        <span className="text-micro font-mono text-success-emerald bg-success-emerald/10 border border-success-emerald/20 px-2 py-0.5 rounded shrink-0">
                          DB Matched
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={() => handleRemoveAuthor(idx)}
                        disabled={authors.length <= 1}
                        className="p-2 text-text-tertiary hover:text-error-red disabled:opacity-30 transition-all shrink-0 cursor-pointer"
                      >
                        <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Abstract */}
          {currentStep === 2 && (
            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 flex flex-col gap-6">
              <h3 className="text-h3 font-bold text-text-primary flex items-center gap-2">
                <FontAwesomeIcon icon={faBookOpen} className="text-accent-primary h-4 w-4" />
                2. Abstract
              </h3>

              <div className="flex flex-col gap-2">
                <div className="flex justify-between items-center">
                  <label className="text-body-sm font-medium text-text-primary">
                    Abstract Content
                  </label>
                  <span className="text-micro font-mono text-text-tertiary">
                    Word Count: {(projectFields.abstract.match(/\w+/g) || []).length} &middot; Chars: {projectFields.abstract.length}
                  </span>
                </div>
                <textarea
                  rows={14}
                  value={projectFields.abstract}
                  onChange={(e) => setProjectFields({ ...projectFields, abstract: e.target.value })}
                  className="px-4 py-3 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm leading-relaxed focus:outline-none focus:border-accent-primary resize-y font-sans min-h-[320px]"
                  placeholder="Paste or edit the full project abstract here..."
                />
              </div>
            </div>
          )}

          {/* Step 3: Keywords */}
          {currentStep === 3 && (
            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 flex flex-col gap-6">
              <h3 className="text-h3 font-bold text-text-primary flex items-center gap-2">
                <FontAwesomeIcon icon={faTags} className="text-accent-primary h-4 w-4" />
                3. Subject Keywords
              </h3>

              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newKeywordInput}
                    onChange={(e) => setNewKeywordInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddKeyword())}
                    placeholder="Enter keyword or technology tag (e.g. Deep Learning)..."
                    className="flex-1 px-3.5 py-2 rounded-md bg-surface-sunken border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                  />
                  <button
                    type="button"
                    onClick={handleAddKeyword}
                    className="px-4 py-2 rounded-md bg-accent-primary text-white text-body-sm font-medium hover:bg-accent-primary/90 transition-all cursor-pointer shrink-0"
                  >
                    Add Tag
                  </button>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  {keywords.map((kw, idx) => (
                    <span
                      key={idx}
                      className="bg-accent-primary/10 border border-accent-primary/20 text-accent-primary text-body-sm px-3 py-1 rounded-full flex items-center gap-2"
                    >
                      <span>{kw}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveKeyword(idx)}
                        className="hover:text-error-red transition-colors cursor-pointer"
                      >
                        <FontAwesomeIcon icon={faXmark} className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  {keywords.length === 0 && (
                    <p className="text-body-sm text-text-tertiary">No keywords added yet.</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Section Editor (Large Editor Area + Automatic Canonical Badge) */}
          {currentStep === 4 && (
            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 flex flex-col gap-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-subtle pb-4">
                <div>
                  <h3 className="text-h3 font-bold text-text-primary flex items-center gap-2">
                    <FontAwesomeIcon icon={faFileLines} className="text-accent-primary h-4 w-4" />
                    4. Document Sections
                  </h3>
                  <p className="text-body-sm text-text-secondary mt-0.5">
                    Review section content. Heading canonicalization is computed automatically based on heading titles.
                  </p>
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 cursor-pointer bg-surface-sunken px-3 py-1.5 rounded-md border border-border-subtle text-body-sm font-medium text-text-primary">
                    <input
                      type="checkbox"
                      checked={skipSections}
                      onChange={(e) => setSkipSections(e.target.checked)}
                      className="rounded border-border-default text-accent-primary focus:ring-0 cursor-pointer"
                    />
                    Skip Section Editing
                  </label>

                  {!skipSections && (
                    <button
                      type="button"
                      onClick={handleAddSection}
                      className="px-3 py-1.5 rounded-md bg-accent-primary text-white text-body-sm font-medium hover:bg-accent-primary/90 transition-all flex items-center gap-1.5 cursor-pointer shrink-0"
                    >
                      <FontAwesomeIcon icon={faPlus} className="h-3.5 w-3.5" />
                      Add Section
                    </button>
                  )}
                </div>
              </div>

              {skipSections ? (
                <div className="p-6 text-center border border-dashed border-border-subtle rounded-lg bg-surface-sunken">
                  <p className="text-body font-semibold text-text-primary">Section editing is currently skipped.</p>
                  <p className="text-body-sm text-text-tertiary mt-1">
                    All extracted sections will be preserved exactly as extracted without any modifications.
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-4 max-h-[600px] overflow-y-auto pr-1 rounded-md">
                  {sections.map((sec, idx) => (
                    <div
                      key={idx}
                      className="bg-surface-sunken border border-border-default hover:border-border-strong rounded-xl p-5 flex flex-col gap-5 shadow-sm transition-all"
                    >
                      {/* Section Card Header */}
                      <div className="flex items-center justify-between gap-4 border-b border-border-subtle pb-3">
                        <div className="flex items-center gap-2.5 flex-wrap">
                          <span className="text-micro font-mono bg-surface-raised px-2.5 py-1 rounded border border-border-subtle text-text-primary font-bold">
                            Section #{idx + 1}
                          </span>
                          <span className="text-micro font-mono bg-accent-primary/10 border border-accent-primary/30 text-accent-primary px-3 py-1 rounded-full font-medium">
                            Canonical: {sec.canonical_section || "Introduction"}
                          </span>
                        </div>

                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleMoveSection(idx, "up")}
                            disabled={idx === 0}
                            className="p-1.5 rounded hover:bg-surface-raised text-text-secondary hover:text-text-primary disabled:opacity-30 cursor-pointer transition-all"
                            title="Move Section Up"
                          >
                            <FontAwesomeIcon icon={faArrowUp} className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleMoveSection(idx, "down")}
                            disabled={idx === sections.length - 1}
                            className="p-1.5 rounded hover:bg-surface-raised text-text-secondary hover:text-text-primary disabled:opacity-30 cursor-pointer transition-all"
                            title="Move Section Down"
                          >
                            <FontAwesomeIcon icon={faArrowDown} className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteSection(idx)}
                            className="p-1.5 rounded hover:bg-error-red/10 text-text-tertiary hover:text-error-red cursor-pointer ml-1 transition-all"
                            title="Delete Section"
                          >
                            <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Heading & Metadata Inputs */}
                      <div className="grid grid-cols-1 sm:grid-cols-12 gap-4 items-end">
                        {/* Heading Title (6 cols) */}
                        <div className="sm:col-span-6 flex flex-col gap-1.5">
                          <label className="text-micro font-mono uppercase text-text-secondary font-semibold">
                            Heading Title <span className="text-error-red">*</span>
                          </label>
                          <input
                            type="text"
                            value={sec.heading}
                            onChange={(e) => handleSectionChange(idx, "heading", e.target.value)}
                            className="w-full px-3 py-2 rounded-md bg-surface-raised border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                            placeholder="e.g. 1. Introduction"
                          />
                        </div>

                        {/* Heading Level (2 cols) */}
                        <div className="sm:col-span-2 flex flex-col gap-1.5">
                          <label className="text-micro font-mono uppercase text-text-secondary font-semibold">
                            Level
                          </label>
                          <select
                            value={sec.heading_level || 1}
                            onChange={(e) => handleSectionChange(idx, "heading_level", e.target.value)}
                            className="w-full px-3 py-2 rounded-md bg-surface-raised border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary"
                          >
                            {[1, 2, 3, 4, 5, 6].map((l) => (
                              <option key={l} value={l}>
                                H{l}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Page Start (2 cols) */}
                        <div className="sm:col-span-2 flex flex-col gap-1.5">
                          <label className="text-micro font-mono uppercase text-text-secondary font-semibold">
                            Page Start
                          </label>
                          <input
                            type="number"
                            value={sec.page_start || ""}
                            onChange={(e) => handleSectionChange(idx, "page_start", e.target.value)}
                            className="w-full px-3 py-2 rounded-md bg-surface-raised border border-border-default text-text-primary text-body-sm font-mono focus:outline-none focus:border-accent-primary"
                            placeholder="1"
                          />
                        </div>

                        {/* Page End (2 cols) */}
                        <div className="sm:col-span-2 flex flex-col gap-1.5">
                          <label className="text-micro font-mono uppercase text-text-secondary font-semibold">
                            Page End
                          </label>
                          <input
                            type="number"
                            value={sec.page_end || ""}
                            onChange={(e) => handleSectionChange(idx, "page_end", e.target.value)}
                            className="w-full px-3 py-2 rounded-md bg-surface-raised border border-border-default text-text-primary text-body-sm font-mono focus:outline-none focus:border-accent-primary"
                            placeholder="5"
                          />
                        </div>
                      </div>

                      {/* Section Content Textarea */}
                      <div className="flex flex-col gap-2 pt-1">
                        <div className="flex justify-between items-center">
                          <label className="text-micro font-mono uppercase text-text-secondary font-semibold">
                            Section Content
                          </label>
                          <span className="text-micro font-mono text-text-tertiary bg-surface-raised px-2 py-0.5 rounded border border-border-subtle">
                            Word Count: {sec.word_count || (sec.content ? (sec.content.match(/\w+/g) || []).length : 0)}
                          </span>
                        </div>
                        <textarea
                          rows={12}
                          value={sec.content || ""}
                          onChange={(e) => handleSectionChange(idx, "content", e.target.value)}
                          className="w-full px-4 py-3 rounded-md bg-surface-raised border border-border-default text-text-primary text-body-sm focus:outline-none focus:border-accent-primary font-sans leading-relaxed min-h-[260px] resize-y"
                          placeholder="Section text content..."
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 5: Review & Verify */}
          {currentStep === 5 && (
            <div className="bg-surface-raised border border-border-subtle rounded-xl p-6 flex flex-col gap-6">
              <h3 className="text-h3 font-bold text-text-primary flex items-center gap-2">
                <FontAwesomeIcon icon={faCheckCircle} className="text-accent-primary h-4 w-4" />
                5. Final Review & Publish
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Project Summary Card */}
                <div className="bg-surface-sunken border border-border-subtle rounded-lg p-5 flex flex-col gap-3">
                  <div className="flex justify-between items-center border-b border-border-subtle pb-2">
                    <span className="text-body font-semibold text-text-primary">Project Overview</span>
                    <button
                      type="button"
                      onClick={() => setCurrentStep(1)}
                      className="text-micro font-mono text-accent-primary hover:underline cursor-pointer"
                    >
                      Edit Details
                    </button>
                  </div>
                  <p className="text-body font-bold text-text-primary">{projectFields.title}</p>
                  <div className="grid grid-cols-2 gap-2 text-body-sm text-text-secondary">
                    <div><span className="text-text-tertiary">Category:</span> {projectFields.project_type}</div>
                    <div><span className="text-text-tertiary">Level:</span> {projectFields.academic_level}</div>
                    <div><span className="text-text-tertiary">Batch:</span> {projectFields.batch}</div>
                    <div>
                      <span className="text-text-tertiary">Department:</span>{" "}
                      {departments.find((d) => String(d.id) === String(departmentId))?.name || projectFields.department_name}
                    </div>
                  </div>
                  <div className="text-body-sm text-text-secondary">
                    <span className="text-text-tertiary">Supervisors:</span>{" "}
                    {selectedSupervisors.length === 0
                      ? "None selected"
                      : selectedSupervisors
                        .map((s) => {
                          if (typeof s === "string") return s;
                          const titleStr = s?.title ? `${s.title} ` : "";
                          const desigStr = s?.designation ? ` (${s.designation})` : "";
                          return `${titleStr}${s?.full_name || "Unknown"}${desigStr}`;
                        })
                        .join(", ")}
                  </div>
                  <div className="text-body-sm text-text-secondary">
                    <span className="text-text-tertiary">Authors:</span>{" "}
                    {authors.filter((a) => a.full_name).map((a) => `${a.full_name} (${a.roll_number || "No roll"})`).join(", ")}
                  </div>
                </div>

                {/* Abstract & Keywords Preview */}
                <div className="bg-surface-sunken border border-border-subtle rounded-lg p-5 flex flex-col gap-3">
                  <div className="flex justify-between items-center border-b border-border-subtle pb-2">
                    <span className="text-body font-semibold text-text-primary">Abstract & Keywords</span>
                    <button
                      type="button"
                      onClick={() => setCurrentStep(2)}
                      className="text-micro font-mono text-accent-primary hover:underline cursor-pointer"
                    >
                      Edit Abstract
                    </button>
                  </div>
                  <p className="text-body-sm text-text-secondary line-clamp-4 leading-relaxed">
                    {projectFields.abstract || "No abstract provided."}
                  </p>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {keywords.map((kw, i) => (
                      <span key={i} className="bg-accent-primary/10 border border-accent-primary/20 text-accent-primary text-micro font-mono px-2 py-0.5 rounded">
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Sections Summary */}
              <div className="bg-surface-sunken border border-border-subtle rounded-lg p-5 flex flex-col gap-2">
                <div className="flex justify-between items-center border-b border-border-subtle pb-2">
                  <span className="text-body font-semibold text-text-primary">Sections Summary</span>
                  <button
                    type="button"
                    onClick={() => setCurrentStep(4)}
                    className="text-micro font-mono text-accent-primary hover:underline cursor-pointer"
                  >
                    Edit Sections
                  </button>
                </div>
                {skipSections ? (
                  <p className="text-body-sm text-text-tertiary">Original sections preserved (skipped editing).</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {sections.map((s, idx) => (
                      <span key={idx} className="bg-surface-raised border border-border-subtle text-text-primary text-micro font-mono px-2.5 py-1 rounded">
                        #{idx + 1} {s.heading} ({s.canonical_section || "Introduction"})
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Verification & Publication Action Bar */}
              <div className="border-t border-border-subtle pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div>
                  {verifiedSuccess ? (
                    <span className="text-body-sm font-semibold text-success-emerald flex items-center gap-1.5">
                      <FontAwesomeIcon icon={faCheckCircle} />
                      Metadata saved and validated! Ready for catalog publication.
                    </span>
                  ) : (
                    <span className="text-body-sm text-text-secondary">
                      Please validate document details before publishing to the repository catalog.
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleVerifyMetadata}
                    disabled={verifying || publishing}
                    className="px-5 py-2.5 rounded-md bg-surface-raised border border-accent-primary/50 text-accent-primary hover:bg-accent-primary/10 text-body-sm font-medium transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40"
                  >
                    {verifying ? (
                      <FontAwesomeIcon icon={faSpinner} className="animate-spin h-4 w-4" />
                    ) : (
                      <FontAwesomeIcon icon={faCheckCircle} className="h-4 w-4" />
                    )}
                    Save & Validate Metadata
                  </button>

                  <button
                    type="button"
                    onClick={handlePublishProject}
                    disabled={!verifiedSuccess || publishing}
                    className={`px-6 py-2.5 rounded-md text-white text-body-sm font-medium shadow-sm transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${job.status === "SECTIONS_PENDING"
                      ? "bg-warning-amber hover:bg-warning-amber/90"
                      : "bg-success-emerald hover:bg-success-emerald/90"
                      }`}
                  >
                    {publishing ? (
                      <FontAwesomeIcon icon={faSpinner} className="animate-spin h-4 w-4" />
                    ) : (
                      <FontAwesomeIcon icon={faRocket} className="h-4 w-4" />
                    )}
                    {job.status === "SECTIONS_PENDING" ? "Update Sections" : "Publish to Repository"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Stepper Footer Controls */}
          <div className="flex items-center justify-between border-t border-border-subtle pt-6">
            <button
              type="button"
              onClick={() => setCurrentStep((s) => Math.max(1, s - 1))}
              disabled={currentStep === 1}
              className="px-4 py-2 rounded-md bg-surface-raised border border-border-default text-text-secondary text-body-sm font-medium hover:text-text-primary disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed transition-all flex items-center gap-1.5"
            >
              <FontAwesomeIcon icon={faChevronLeft} className="h-3.5 w-3.5" /> Previous Step
            </button>

            <span className="text-micro font-mono text-text-tertiary">Step {currentStep} of 5</span>

            <button
              type="button"
              onClick={() => setCurrentStep((s) => Math.min(5, s + 1))}
              disabled={currentStep === 5}
              className="px-4 py-2 rounded-md bg-accent-primary text-white text-body-sm font-medium hover:bg-accent-primary/90 disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed transition-all flex items-center gap-1.5"
            >
              Next Step <FontAwesomeIcon icon={faChevronRight} className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Add Faculty Modal */}
      {showAddFacultyModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-raised border border-border-default rounded-xl p-6 max-w-md w-full flex flex-col gap-4 shadow-2xl">
            <h3 className="text-h3 font-bold text-text-primary">Add Faculty Member</h3>
            <form onSubmit={handleCreateFaculty} className="flex flex-col gap-4">
              <div className="flex gap-2">
                <div className="w-28 flex flex-col gap-1">
                  <label className="text-micro font-mono uppercase text-text-tertiary">Title</label>
                  <input
                    type="text"
                    value={newFaculty.title}
                    onChange={(e) => setNewFaculty({ ...newFaculty, title: e.target.value })}
                    className="px-3 py-1.5 rounded bg-surface-sunken border border-border-default text-text-primary text-body-sm"
                  />
                </div>
                <div className="flex-1 flex flex-col gap-1">
                  <label className="text-micro font-mono uppercase text-text-tertiary">Full Name</label>
                  <input
                    type="text"
                    required
                    value={newFaculty.full_name}
                    onChange={(e) => setNewFaculty({ ...newFaculty, full_name: e.target.value })}
                    className="px-3 py-1.5 rounded bg-surface-sunken border border-border-default text-text-primary text-body-sm"
                    placeholder="e.g. Rajiv Gupta"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-micro font-mono uppercase text-text-tertiary">Designation</label>
                <input
                  type="text"
                  value={newFaculty.designation}
                  onChange={(e) => setNewFaculty({ ...newFaculty, designation: e.target.value })}
                  className="px-3 py-1.5 rounded bg-surface-sunken border border-border-default text-text-primary text-body-sm"
                  placeholder="e.g. Associate Professor"
                />
              </div>

              <div className="flex justify-end gap-3 border-t border-border-subtle pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddFacultyModal(false)}
                  className="px-4 py-2 rounded-md bg-surface-sunken border border-border-subtle text-text-secondary text-body-sm hover:text-text-primary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingFaculty}
                  className="px-4 py-2 rounded-md bg-accent-primary text-white text-body-sm font-medium hover:bg-accent-primary/90"
                >
                  {creatingFaculty ? "Saving..." : "Create & Select"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
