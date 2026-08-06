import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../api/client";
import tuLogo from "../assets/tu.png";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCheckCircle, faSpinner, faSearch, faPlus, faArrowLeft, faUserCheck } from "@fortawesome/free-solid-svg-icons";

// Helper to strip embedded prefix titles like "Er. ", "Dr. ", "Prof. Dr. " from full names
const stripTitlePrefix = (name) => {
  if (!name) return "";
  return name.replace(/^(Prof\.\s*Dr\.|Dr\.|Er\.|Prof\.)\s+/i, "").trim();
};

// Helper to format academic titles (keeps (Dr.), removes Er.)
const formatTitle = (title) => {
  if (!title) return null;
  if (title.toLowerCase().includes("er")) return null;
  if (title.toLowerCase().includes("dr")) return "(Dr.)";
  return `(${title.trim()})`;
};

export default function OnboardingModal() {
  const { user, completeProfile } = useAuth();
  
  // Strictly enforce the role from backend inference
  const role = user?.inferred_role || "student";
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const prefill = user?.prefill_data || {};

  // Extract roll number from institutional email (e.g. 080bct077.sarthak@pcampus.edu.np -> 080BCT077)
  const autoRollNumber = (() => {
    if (prefill.roll_number) return prefill.roll_number;
    if (!user?.email) return "";
    const username = user.email.split("@")[0];
    const roll = username.includes(".") ? username.split(".")[0] : username;
    return roll.toUpperCase();
  })();

  // Departments list
  const [departments, setDepartments] = useState([]);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState(prefill.department_id || "");

  // Faculty extracted list states
  const [facultyList, setFacultyList] = useState([]);
  const [loadingFaculty, setLoadingFaculty] = useState(role === "faculty");
  const [facultySearch, setFacultySearch] = useState("");
  const [selectedFaculty, setSelectedFaculty] = useState(null);
  const [isCustomName, setIsCustomName] = useState(false);

  // Form states
  const [fullName, setFullName] = useState(stripTitlePrefix(prefill.full_name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim()));
  const [academicLevel, setAcademicLevel] = useState(prefill.academic_level || "UG");
  const [title, setTitle] = useState(prefill.title || "");
  const [designation, setDesignation] = useState(prefill.designation || "");

  useEffect(() => {
    authApi.getDepartments()
      .then((res) => {
        const data = res?.data || res || [];
        if (Array.isArray(data)) {
          setDepartments(data);
          if (!selectedDepartmentId && data.length > 0) {
            setSelectedDepartmentId(data[0].id);
          }
        }
      })
      .catch(() => setDepartments([]));

    if (role === "faculty") {
      setLoadingFaculty(true);
      authApi.getFacultyList()
        .then((res) => {
          const list = res?.data || res || [];
          if (Array.isArray(list)) {
            setFacultyList(list);

            // Auto-select if prefill or full name matches an existing extracted faculty member
            const matched = list.find(
              (f) => stripTitlePrefix(f.full_name).toLowerCase() === stripTitlePrefix(prefill.full_name || fullName).toLowerCase()
            );
            if (matched) {
              handleSelectFaculty(matched);
            }
          }
        })
        .catch(() => setFacultyList([]))
        .finally(() => setLoadingFaculty(false));
    }
  }, [role]);

  const handleSelectFaculty = (fac) => {
    setSelectedFaculty(fac);
    setIsCustomName(false);
    setFullName(stripTitlePrefix(fac.full_name));
    if (fac.title) setTitle(fac.title);
    if (fac.designation) setDesignation(fac.designation);
    if (fac.department_id) setSelectedDepartmentId(fac.department_id);
  };

  const handleSwitchToCustom = () => {
    setIsCustomName(true);
    setSelectedFaculty(null);
    setFullName(stripTitlePrefix(`${user?.first_name || ''} ${user?.last_name || ''}`.trim()));
  };

  const filteredFaculty = facultyList.filter((fac) => {
    const q = facultySearch.toLowerCase();
    const cleanName = stripTitlePrefix(fac.full_name).toLowerCase();
    return (
      cleanName.includes(q) ||
      (fac.designation && fac.designation.toLowerCase().includes(q)) ||
      (fac.title && fac.title.toLowerCase().includes(q))
    );
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (role === "faculty" && !selectedFaculty && !isCustomName) {
      setError("Please select your name from the extracted faculty list or choose to enter your name manually.");
      return;
    }

    if (!fullName.trim()) {
      setError("Full name is required.");
      return;
    }

    setSubmitting(true);

    try {
      let payload = { 
        full_name: stripTitlePrefix(fullName.trim()),
        department_id: selectedDepartmentId ? parseInt(selectedDepartmentId, 10) : null
      };

      if (role === "student") {
        payload.academic_level = academicLevel;
        payload.roll_number = autoRollNumber;
      } else {
        if (selectedFaculty && !isCustomName) {
          payload.faculty_id = selectedFaculty.id;
        }
        payload.title = title.trim();
        payload.designation = designation.trim();
      }

      await completeProfile(payload);
    } catch (err) {
      setError(err.message || "Failed to save profile. Please check your inputs.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-surface-raised border border-border-subtle rounded-lg max-w-lg w-full p-8 shadow-2xl relative overflow-hidden max-h-[90vh] flex flex-col">
        {/* Institutional Gold Bar at Top */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-accent-gold" />

        {/* Header */}
        <div className="flex items-center gap-4 mb-5 shrink-0">
          <img src={tuLogo} alt="TU Logo" className="h-10 w-10 object-contain" />
          <div>
            <h2 className="text-xl font-bold text-text-primary tracking-tight">Complete Your Profile</h2>
            <p className="text-xs text-text-secondary">Please confirm your academic details to activate your account</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-error-red/10 border border-error-red/30 rounded text-error-red text-xs shrink-0">
            {error}
          </div>
        )}

        {/* Form based on account role */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 overflow-y-auto pr-1">
          
          {/* STUDENT ROLE FORM */}
          {role === "student" ? (
            <>
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold"
                  placeholder="e.g. Sarthak Khadka"
                />
              </div>

              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Department
                </label>
                <select
                  value={selectedDepartmentId}
                  onChange={(e) => setSelectedDepartmentId(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold cursor-pointer"
                >
                  {departments.length > 0 ? (
                    departments.map((dept) => (
                      <option key={dept.id} value={dept.id}>
                        {dept.name}
                      </option>
                    ))
                  ) : (
                    <option value="">Department of Electronics & Computer Engineering</option>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Academic Level
                </label>
                <select
                  value={academicLevel}
                  onChange={(e) => setAcademicLevel(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold cursor-pointer"
                >
                  <option value="UG">Undergraduate (UG / Bachelors)</option>
                  <option value="Masters">Masters (M.Sc / M.E)</option>
                  <option value="PhD">Doctor of Philosophy (PhD)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Roll Number
                </label>

                <input
                  type="text"
                  readOnly
                  disabled
                  value={autoRollNumber}
                  className="w-full px-3 py-2 bg-surface-sunken/60 border border-border-subtle rounded text-sm text-text-secondary font-mono cursor-not-allowed select-none"
                />
              </div>
            </>
          ) : (
            /* FACULTY ROLE FORM WITH EXTRACTED SEARCHABLE NAMES */
            <>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary">
                    Select Your Name (Extracted from Repository Reports)
                  </label>

                  {isCustomName && (
                    <button
                      type="button"
                      onClick={() => setIsCustomName(false)}
                      className="text-xs text-accent-gold hover:underline flex items-center gap-1 font-medium cursor-pointer"
                    >
                      <FontAwesomeIcon icon={faArrowLeft} className="text-[10px]" />
                      <span>Back to extracted list</span>
                    </button>
                  )}
                </div>

                {!isCustomName ? (
                  <div className="flex flex-col gap-2">
                    {/* Search Filter Input */}
                    <div className="relative">
                      <FontAwesomeIcon
                        icon={faSearch}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-xs"
                      />
                      <input
                        type="text"
                        value={facultySearch}
                        onChange={(e) => setFacultySearch(e.target.value)}
                        placeholder="Search by name, designation, or title..."
                        className="w-full pl-8 pr-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold"
                      />
                    </div>

                    {/* Faculty Searchable List */}
                    <div className="border border-border-default rounded-md bg-surface-sunken max-h-44 overflow-y-auto divide-y divide-border-subtle">
                      {loadingFaculty ? (
                        <div className="p-4 text-center text-xs text-text-tertiary flex items-center justify-center gap-2">
                          <FontAwesomeIcon icon={faSpinner} className="animate-spin text-accent-gold" />
                          <span>Loading extracted faculty records...</span>
                        </div>
                      ) : filteredFaculty.length > 0 ? (
                        filteredFaculty.map((fac) => {
                          const isSelected = selectedFaculty?.id === fac.id;
                          const cleanName = stripTitlePrefix(fac.full_name);
                          const subtitle = [fac.designation, formatTitle(fac.title)].filter(Boolean).join(" ");

                          return (
                            <div
                              key={fac.id}
                              onClick={() => handleSelectFaculty(fac)}
                              className={`p-2.5 flex items-center justify-between text-xs cursor-pointer transition-colors ${
                                isSelected
                                  ? "bg-accent-gold/15 border-l-4 border-accent-gold text-text-primary font-semibold"
                                  : "hover:bg-surface-raised text-text-secondary"
                              }`}
                            >
                              <div className="flex flex-col gap-0.5">
                                {/* Name without prefix titles */}
                                <span className="text-sm font-medium text-text-primary">
                                  {cleanName}
                                </span>
                                {/* Title and Designation below name */}
                                {subtitle && (
                                  <span className="text-[11px] text-text-tertiary font-mono">
                                    {subtitle}
                                  </span>
                                )}
                              </div>
                              {isSelected && (
                                <FontAwesomeIcon icon={faUserCheck} className="text-accent-gold text-sm" />
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <div className="p-4 text-center flex flex-col items-center gap-2">
                          <p className="text-xs text-text-secondary">
                            No faculty found matching "{facultySearch}"
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Option to manually enter name if missing */}
                    <button
                      type="button"
                      onClick={handleSwitchToCustom}
                      className="mt-1 py-2 px-3 border border-dashed border-border-default hover:border-accent-gold rounded text-xs text-accent-gold hover:bg-accent-gold/5 transition-all flex items-center justify-center gap-1.5 cursor-pointer font-medium"
                    >
                      <FontAwesomeIcon icon={faPlus} className="text-[10px]" />
                      <span>My name is not in this list (Enter manually)</span>
                    </button>
                  </div>
                ) : (
                  /* CUSTOM FULL NAME MANUAL INPUT */
                  <div className="bg-surface-sunken/40 border border-border-default p-3 rounded-md flex flex-col gap-3 animate-fade-in">
                    <div>
                      <label className="block text-[11px] font-mono uppercase tracking-wider text-accent-gold mb-1 font-semibold">
                        Full Name (Without prefix title e.g. Ram Shrestha)
                      </label>
                      <input
                        type="text"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(stripTitlePrefix(e.target.value))}
                        className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold"
                        placeholder="e.g. Ram Shrestha"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Department
                </label>
                <select
                  value={selectedDepartmentId}
                  onChange={(e) => setSelectedDepartmentId(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold cursor-pointer"
                >
                  {departments.length > 0 ? (
                    departments.map((dept) => (
                      <option key={dept.id} value={dept.id}>
                        {dept.name}
                      </option>
                    ))
                  ) : (
                    <option value="">Department of Electronics & Computer Engineering</option>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Title (Optional)
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold"
                  placeholder="e.g. Dr. / Er. / Prof. Dr."
                />
              </div>

              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Designation (Optional)
                </label>
                <input
                  type="text"
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold"
                  placeholder="e.g. Assistant Professor"
                />
              </div>
            </>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 w-full py-3 bg-accent-gold hover:bg-accent-gold/90 text-surface-canvas font-semibold text-sm rounded transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer shrink-0"
          >
            {submitting ? (
              <>
                <FontAwesomeIcon icon={faSpinner} className="animate-spin" />
                <span>Saving Profile...</span>
              </>
            ) : (
              <>
                <FontAwesomeIcon icon={faCheckCircle} />
                <span>Save & Continue to Repository</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
