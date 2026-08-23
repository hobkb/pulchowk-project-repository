import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../api/client";
import tuLogo from "../assets/tu.png";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCheckCircle, faSpinner, faSearch, faPlus, faArrowLeft, faUserCheck } from "@fortawesome/free-solid-svg-icons";
import { Button, Dialog, ErrorNotice, Eyebrow } from "./ui";

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

const fieldLabel = "block text-xs font-semibold text-ink-2 mb-1.5";
const fieldInput =
  "w-full px-3 py-2 bg-white border border-line-strong rounded-sm text-base text-ink placeholder:text-ink-3 hover:border-ink-3 transition-colors";

export default function OnboardingModal() {
  const { user, completeProfile } = useAuth();

  // Strictly enforce the role from backend inference
  // The email shape is only a default: it cannot tell a faculty member
  // from an administrator, so the account holder chooses.
  const [role, setRole] = useState(user?.inferred_role || "student");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const prefill = user?.prefill_data || {};

  // Extract roll number from institutional email (e.g. 080bct077.sarthak@pcampus.edu.np -> 080BCT077)
  const autoRollNumber = (() => {
    if (prefill.roll_number) return prefill.roll_number;
    if (!user?.email) return "";
    const username = user.email.split("@")[0];
    const roll = username.includes(".") ? username.split(".")[0] : username;
    // A campus roll is three digits, letters, then digits (080BCT083).
    // Anything else -- a personal address, a name -- is not a roll number
    // and must not be pre-filled as one.
    return /^\d{3}[a-zA-Z]{2,5}\d{2,4}$/.test(roll) ? roll.toUpperCase() : "";
  })();

  const [rollNumber, setRollNumber] = useState(autoRollNumber);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        role,
        full_name: stripTitlePrefix(fullName.trim()),
        department_id: selectedDepartmentId ? parseInt(selectedDepartmentId, 10) : null
      };

      if (role === "student") {
        payload.academic_level = academicLevel;
        payload.roll_number = rollNumber;
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
    // A mandatory gate: it uses the shared Dialog for real dialog
    // semantics and a focus trap, but is explicitly non-dismissible --
    // there is nothing behind it to go back to until the profile exists.
    <Dialog open dismissible={false} width="max-w-lg">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-4">
          <img src={tuLogo} alt="" aria-hidden="true" className="h-10 w-10 object-contain shrink-0" />
          <div className="min-w-0">
            <Eyebrow tone="primary">Institute of Engineering</Eyebrow>
            <h2 className="text-section">Complete your profile</h2>
          </div>
        </div>

        <p className="text-base text-ink-2 leading-relaxed">
          These details identify you on the repository, and are matched against the names
          already extracted from deposited reports. Confirm them to continue.
        </p>

        {error && <ErrorNotice title="Your profile could not be saved" detail={error} />}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label htmlFor="onboarding-role" className={fieldLabel}>
              I am joining as
            </label>
            <select
              id="onboarding-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className={`${fieldInput} cursor-pointer`}
            >
              <option value="student">Student</option>
              <option value="faculty">Faculty</option>
              <option value="admin">Administrator</option>
            </select>
            <p className="mt-1 text-xs text-ink-3">
              {role === "student"
                ? "You can search the catalogue and request full reports."
                : role === "faculty"
                  ? "Depositing and reviewing reports. An administrator has to approve this before it takes effect — until then your account is an ordinary reader."
                  : "Publishing, verification, and deciding requests. An administrator has to approve this before it takes effect — until then your account is an ordinary reader."}
            </p>
          </div>

          {role === "student" ? (
            <>
              <div>
                <label htmlFor="onboarding-fullname" className={fieldLabel}>Full name</label>
                <input
                  id="onboarding-fullname"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className={fieldInput}
                  placeholder="e.g. Sarthak Khadka"
                />
              </div>

              <div>
                <label htmlFor="onboarding-department" className={fieldLabel}>Department</label>
                <select
                  id="onboarding-department"
                  value={selectedDepartmentId}
                  onChange={(e) => setSelectedDepartmentId(e.target.value)}
                  className={`${fieldInput} cursor-pointer`}
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
                <label htmlFor="onboarding-level" className={fieldLabel}>Academic level</label>
                <select
                  id="onboarding-level"
                  value={academicLevel}
                  onChange={(e) => setAcademicLevel(e.target.value)}
                  className={`${fieldInput} cursor-pointer`}
                >
                  <option value="UG">Undergraduate (UG / Bachelors)</option>
                  <option value="Masters">Masters (M.Sc / M.E)</option>
                  <option value="PhD">Doctor of Philosophy (PhD)</option>
                </select>
              </div>

              <div>
                <label htmlFor="onboarding-roll" className={fieldLabel}>Roll number</label>
                <input
                  id="onboarding-roll"
                  type="text"
                  value={rollNumber}
                  onChange={(e) => setRollNumber(e.target.value.toUpperCase())}
                  className={`${fieldInput} tnum`}
                  placeholder="e.g. 080BCT083"
                />
                <p className="mt-1 text-xs text-ink-3">
                  {autoRollNumber
                    ? "Read from your campus address — correct it if it is wrong."
                    : "Could not be read from your address; please enter it."}
                </p>
              </div>
            </>
          ) : (
            <>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className={fieldLabel.replace("mb-1.5", "mb-0")}>
                    Select your name, as extracted from deposited reports
                  </span>

                  {isCustomName && (
                    <button
                      type="button"
                      onClick={() => setIsCustomName(false)}
                      className="text-sm text-primary hover:underline flex items-center gap-1 font-medium cursor-pointer"
                    >
                      <FontAwesomeIcon icon={faArrowLeft} className="text-[10px]" />
                      <span>Back to extracted list</span>
                    </button>
                  )}
                </div>

                {!isCustomName ? (
                  <div className="flex flex-col gap-2">
                    <div className="relative">
                      <FontAwesomeIcon
                        icon={faSearch}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 text-xs"
                      />
                      <input
                        id="faculty-search"
                        type="search"
                        value={facultySearch}
                        onChange={(e) => setFacultySearch(e.target.value)}
                        aria-label="Search extracted faculty records"
                        placeholder="Search by name, designation, or title"
                        className={`${fieldInput} pl-8`}
                      />
                    </div>

                    <div
                      role="group"
                      aria-label="Extracted faculty records"
                      className="border border-line rounded-sm max-h-44 overflow-y-auto divide-y divide-line-soft"
                    >
                      {loadingFaculty ? (
                        <div className="p-4 text-center text-sm text-ink-3 flex items-center justify-center gap-2">
                          <FontAwesomeIcon icon={faSpinner} className="animate-spin text-primary" />
                          <span>Loading extracted faculty records…</span>
                        </div>
                      ) : filteredFaculty.length > 0 ? (
                        filteredFaculty.map((fac) => {
                          const isSelected = selectedFaculty?.id === fac.id;
                          const cleanName = stripTitlePrefix(fac.full_name);
                          const subtitle = [fac.designation, formatTitle(fac.title)].filter(Boolean).join(" ");

                          return (
                            <button
                              key={fac.id}
                              type="button"
                              onClick={() => handleSelectFaculty(fac)}
                              aria-pressed={isSelected}
                              className={`w-full text-left p-2.5 flex items-center justify-between gap-3 text-sm cursor-pointer transition-colors ${
                                isSelected
                                  ? "bg-primary-050 border-l-2 border-l-primary text-ink"
                                  : "hover:bg-band text-ink-2"
                              }`}
                            >
                              <span className="flex flex-col gap-0.5 min-w-0">
                                <span className="text-base text-ink">{cleanName}</span>
                                {subtitle && (
                                  <span className="text-sm text-ink-3">{subtitle}</span>
                                )}
                              </span>
                              {isSelected && (
                                <FontAwesomeIcon
                                  icon={faUserCheck}
                                  className="text-primary h-3.5 w-3.5 shrink-0"
                                  aria-hidden="true"
                                />
                              )}
                            </button>
                          );
                        })
                      ) : (
                        <div className="p-4 text-center flex flex-col items-center gap-2">
                          <p className="text-sm text-ink-2">No faculty found matching "{facultySearch}"</p>
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={handleSwitchToCustom}
                      className="mt-1 py-2 px-3 border border-dashed border-line hover:border-primary rounded-sm text-sm text-primary hover:bg-primary-050 transition-colors flex items-center justify-center gap-1.5 cursor-pointer font-medium"
                    >
                      <FontAwesomeIcon icon={faPlus} className="text-[10px]" />
                      <span>My name is not in this list (enter manually)</span>
                    </button>
                  </div>
                ) : (
                  <div className="bg-band border border-line p-3 rounded-sm flex flex-col gap-3 pop-in">
                    <div>
                      <label htmlFor="faculty-custom-name" className="block text-xs font-semibold text-primary mb-1.5">
                        Full name, without a prefix title
                      </label>
                      <input
                        id="faculty-custom-name"
                        type="text"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(stripTitlePrefix(e.target.value))}
                        className={fieldInput}
                        placeholder="e.g. Ram Shrestha"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label htmlFor="faculty-department" className={fieldLabel}>Department</label>
                <select
                  id="faculty-department"
                  value={selectedDepartmentId}
                  onChange={(e) => setSelectedDepartmentId(e.target.value)}
                  className={`${fieldInput} cursor-pointer`}
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
                <label htmlFor="faculty-title-field" className={fieldLabel}>Title (optional)</label>
                <input
                  id="faculty-title-field"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className={fieldInput}
                  placeholder="e.g. Dr. / Er. / Prof. Dr."
                />
              </div>

              <div>
                <label htmlFor="faculty-designation-field" className={fieldLabel}>Designation (optional)</label>
                <input
                  id="faculty-designation-field"
                  type="text"
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                  className={fieldInput}
                  placeholder="e.g. Assistant Professor"
                />
              </div>
            </>
          )}

          <Button type="submit" variant="primary" size="lg" disabled={submitting} className="mt-3 w-full">
            {submitting ? (
              <>
                <FontAwesomeIcon icon={faSpinner} className="animate-spin" />
                <span>Saving…</span>
              </>
            ) : (
              <>
                <FontAwesomeIcon icon={faCheckCircle} />
                <span>Save and enter the repository</span>
              </>
            )}
          </Button>
        </form>
      </div>
    </Dialog>
  );
}
