import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../api/client";
import tuLogo from "../assets/tu.png";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCheckCircle, faSpinner, faLock } from "@fortawesome/free-solid-svg-icons";
import { Button, Dialog, ErrorNotice, Eyebrow } from "./ui";

// Helper to strip embedded prefix titles like "Er. ", "Dr. ", "Prof. Dr. " from full names
const stripTitlePrefix = (name) => {
  if (!name) return "";
  return name.replace(/^(Prof\.\s*Dr\.|Dr\.|Er\.|Prof\.)\s+/i, "").trim();
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

  // Extract roll number from institutional email (e.g. 080bct001.ram@pcampus.edu.np -> 080BCT001)
  const autoRollNumber = (() => {
    if (prefill.roll_number) return prefill.roll_number;
    if (!user?.email) return "";
    const username = user.email.split("@")[0];
    const roll = username.includes(".") ? username.split(".")[0] : username;
    // A campus roll is three digits, letters, then digits (080BCT102).
    // Anything else -- a personal address, a name -- is not a roll number
    // and must not be pre-filled as one.
    return /^\d{3}[a-zA-Z]{2,5}\d{2,4}$/.test(roll) ? roll.toUpperCase() : "";
  })();

  const [rollNumber, setRollNumber] = useState(autoRollNumber);

  // A roll number carried by the campus address is issued by the campus,
  // not chosen here. Leaving it editable let anyone type a classmate's roll
  // number and be matched to that classmate's record, so the field is
  // locked whenever the address proves one. The server enforces this too;
  // disabling the input is only so the rule is visible.
  const rollNumberLocked = Boolean(autoRollNumber);

  // Departments list
  const [departments, setDepartments] = useState([]);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState(prefill.department_id || "");

  // Why they are asking for faculty access. Shown to the administrator
  // who decides the request.
  const [roleReason, setRoleReason] = useState("");

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

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);


  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

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
        payload.title = title.trim();
        payload.designation = designation.trim();
        payload.role_reason = roleReason.trim();
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
            </select>
            <p className="mt-1 text-xs text-ink-3">
              {role === "student"
                ? "You can search the catalogue and request full reports."
                : "Depositing and reviewing reports. An administrator reviews this request — until it is approved your account is an ordinary reader."}
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
                  placeholder="e.g. Ram Bahadur Thapa"
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
                  <option value="UG">Undergraduate</option>
                  <option value="Masters">Masters</option>
                  <option value="PhD">Doctor of Philosophy</option>
                </select>
              </div>

              <div>
                <label htmlFor="onboarding-roll" className={fieldLabel}>Roll number</label>
                <div className="relative">
                  <input
                    id="onboarding-roll"
                    type="text"
                    value={rollNumber}
                    readOnly={rollNumberLocked}
                    aria-readonly={rollNumberLocked}
                    onChange={(e) =>
                      !rollNumberLocked && setRollNumber(e.target.value.toUpperCase())
                    }
                    className={`${fieldInput} tnum ${
                      rollNumberLocked ? "bg-band pr-9 text-ink-2 cursor-not-allowed" : ""
                    }`}
                    placeholder="e.g. 080BCT102"
                  />
                  {rollNumberLocked && (
                    <FontAwesomeIcon
                      icon={faLock}
                      className="absolute right-3 top-1/2 h-3 w-3 -translate-y-1/2 text-ink-3"
                      aria-hidden="true"
                    />
                  )}
                </div>
                <p className="mt-1 text-xs text-ink-3">
                  {rollNumberLocked
                    ? "Taken from your campus address, which the campus issued — it cannot be changed here. Contact your department if it is wrong."
                    : "Your address does not contain a roll number, so enter it."}
                </p>
              </div>
            </>
          ) : (
            <>
              <div>
                <label htmlFor="faculty-fullname" className={fieldLabel}>Full name</label>
                <input
                  id="faculty-fullname"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(stripTitlePrefix(e.target.value))}
                  className={fieldInput}
                  placeholder="e.g. Ram Shrestha"
                />
                <p className="mt-1 text-xs text-ink-3">
                  Without a prefix title — put “Dr.” or “Prof.” in the title field below.
                </p>
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

              <div>
                <label htmlFor="faculty-reason" className={fieldLabel}>
                  Note for the administrator (optional)
                </label>
                <textarea
                  id="faculty-reason"
                  rows={3}
                  value={roleReason}
                  onChange={(e) => setRoleReason(e.target.value)}
                  className={`${fieldInput} resize-y`}
                  placeholder="Anything that helps them confirm who you are."
                />
              </div>
            </>
          )}

          <Button type="submit" variant="primary" size="lg" disabled={submitting} className="mt-3 w-full">
            {submitting ? (
              <>
                <FontAwesomeIcon icon={faSpinner} className="spin" />
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
