import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../api/client";
import tuLogo from "../assets/tu.png";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCheckCircle, faSpinner, faLock } from "@fortawesome/free-solid-svg-icons";

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

  // Form states
  const [fullName, setFullName] = useState(prefill.full_name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim());
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
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      let payload = { 
        full_name: fullName,
        department_id: selectedDepartmentId ? parseInt(selectedDepartmentId, 10) : null
      };

      if (role === "student") {
        payload.academic_level = academicLevel;
        payload.roll_number = autoRollNumber;
      } else {
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
      <div className="bg-surface-raised border border-border-subtle rounded-lg max-w-lg w-full p-8 shadow-2xl relative overflow-hidden">
        {/* Institutional Gold Bar at Top */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-accent-gold" />

        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <img src={tuLogo} alt="TU Logo" className="h-10 w-10 object-contain" />
          <div>
            <h2 className="text-xl font-bold text-text-primary tracking-tight">Complete Your Profile</h2>
            <p className="text-xs text-text-secondary">Please confirm your academic details to activate your account</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-error-red/10 border border-error-red/30 rounded text-error-red text-xs">
            {error}
          </div>
        )}

        {/* Form based on account role */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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

          {role === "student" ? (
            <>
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
                  className="w-full px-3 py-2 bg-surface-sunken/60 border border-border-subtle rounded text-sm text-text-secondary font-mono text-sm cursor-not-allowed select-none"
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-secondary mb-1">
                  Title (Optional)
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-sunken border border-border-default rounded text-sm text-text-primary focus:outline-none focus:border-accent-gold"
                  placeholder="e.g. Dr. / Er. / Prof."
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
            className="mt-4 w-full py-3 bg-accent-gold hover:bg-accent-gold/90 text-surface-canvas font-semibold text-sm rounded transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
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
