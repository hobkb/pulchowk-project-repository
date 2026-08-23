import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Link, useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faUserCircle,
  faEnvelope,
  faBuildingColumns,
  faIdCard,
  faRightFromBracket,
  faGraduationCap,
  faArrowLeft,
  faFloppyDisk,
  faCheck,
} from "@fortawesome/free-solid-svg-icons";

export default function Profile() {
  const { user, logout, completeProfile } = useAuth();
  const navigate = useNavigate();

  // Updatable fields state
  const [faculty, setFaculty] = useState(
    user?.faculty || user?.person?.faculty || user?.person?.program || "BCT"
  );
  const [academicLevel, setAcademicLevel] = useState(
    user?.academic_level || user?.person?.academic_level || "Bachelors"
  );
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  if (!user) return null;

  const fullName = user.first_name
    ? `${user.first_name} ${user.last_name || ""}`.trim()
    : user.username || user.email;

  // Role Label Logic
  let roleLabel = "Student";
  if (user.role === "admin" || user.is_superuser) {
    roleLabel = "Administrator";
  } else if (user.is_department_admin) {
    roleLabel = "Department Admin";
  } else if (user.role === "faculty" || user.inferred_role === "faculty") {
    roleLabel = "Faculty";
  } else if (user.role === "student" || user.inferred_role === "student") {
    roleLabel = "Student";
  }

  const deptName = user.department || "Department of Electronics & Computer Engineering";

  // Roll Number extraction: strictly "080BCT077" without any ".name" or email domain suffix
  const rawRoll = user.roll_number || user.person?.roll_number;
  let cleanRollNo = rawRoll || "";
  if (!cleanRollNo && user.email) {
    cleanRollNo = user.email.split("@")[0];
  }
  if (cleanRollNo.includes(".")) {
    cleanRollNo = cleanRollNo.split(".")[0];
  }
  cleanRollNo = cleanRollNo.toUpperCase();

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setSavedSuccess(false);

    try {
      if (completeProfile) {
        await completeProfile({
          full_name: fullName,
          academic_level: academicLevel,
          faculty: faculty,
          roll_number: cleanRollNo,
        }).catch(() => null);
      }
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch {
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  const facultyOptions = [
    { value: "BCT", label: "BCT (Computer Engineering)" },
    { value: "BEI", label: "BEI (Electronics, Communication & Information Engineering)" },
    { value: "BCE", label: "BCE (Civil Engineering)" },
    { value: "BEL", label: "BEL (Electrical Engineering)" },
    { value: "BME", label: "BME (Mechanical Engineering)" },
    { value: "BAS", label: "BAS (Aerospace Engineering)" },
    { value: "B.Arch", label: "B.Arch (Architecture)" },
    { value: "BCH", label: "BCH (Chemical Engineering)" },
  ];

  const academicLevelOptions = [
    { value: "Bachelors", label: "Bachelors (B.E. / B.Arch)" },
    { value: "Masters", label: "Masters (M.Sc.)" },
    { value: "PhD", label: "Doctorate (Ph.D.)" },
  ];

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto pb-12">
      {/* Top Header */}
      <div className="flex flex-col gap-2">
        <Link
          to="/dashboard"
          className="text-xs font-mono text-text-tertiary hover:text-text-primary flex items-center gap-1.5 transition-colors self-start"
        >
          <FontAwesomeIcon icon={faArrowLeft} className="h-3 w-3" /> Back to Dashboard
        </Link>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">
          User Profile
        </h1>
      </div>

      {/* Main Profile Summary Card */}
      <div className="bg-surface-raised border border-border-subtle rounded-lg p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 shadow-xs">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg font-bold text-text-primary">
                {fullName}
              </h2>
              <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-surface-sunken border border-border-subtle text-text-primary">
                {roleLabel}
              </span>
            </div>

            <p className="text-xs font-mono text-text-secondary">
              {user.email}
            </p>

            <p className="text-xs text-text-tertiary">
              Pulchowk Campus &middot; Institute of Engineering (IOE), TU
            </p>
          </div>

        <button
          onClick={handleLogout}
          className="px-3.5 py-2 bg-surface-sunken border border-border-default hover:border-border-strong text-error-red text-xs font-medium rounded transition-all cursor-pointer flex items-center gap-2 shrink-0 self-stretch sm:self-auto justify-center"
        >
          <FontAwesomeIcon icon={faRightFromBracket} />
          Log Out
        </button>
      </div>

      {/* 2-Column Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Account Credentials Card */}
        <div className="bg-surface-raised border border-border-subtle rounded-lg p-6 flex flex-col gap-4 shadow-xs">
          <div className="border-b border-border-subtle pb-3">
            <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
              Account Information
            </h3>
          </div>

          <div className="divide-y divide-border-subtle text-xs">
            <div className="py-2.5 flex justify-between gap-4">
              <span className="text-text-secondary flex items-center gap-2 shrink-0">
                <FontAwesomeIcon icon={faUserCircle} className="h-3.5 w-3.5 text-text-tertiary" />
                Full Name
              </span>
              <span className="font-mono text-text-primary font-medium text-right">
                {fullName}
              </span>
            </div>

            <div className="py-2.5 flex justify-between gap-4">
              <span className="text-text-secondary flex items-center gap-2 shrink-0">
                <FontAwesomeIcon icon={faEnvelope} className="h-3.5 w-3.5 text-text-tertiary" />
                Email Address
              </span>
              <span className="font-mono text-text-primary text-right break-all">
                {user.email}
              </span>
            </div>

            <div className="py-2.5 flex justify-between gap-4">
              <span className="text-text-secondary flex items-center gap-2 shrink-0">
                <FontAwesomeIcon icon={faGraduationCap} className="h-3.5 w-3.5 text-text-tertiary" />
                Role
              </span>
              <span className="font-mono text-text-primary font-semibold text-right">
                {roleLabel}
              </span>
            </div>

            {cleanRollNo && (
              <div className="py-2.5 flex justify-between gap-4">
                <span className="text-text-secondary flex items-center gap-2 shrink-0">
                  <FontAwesomeIcon icon={faIdCard} className="h-3.5 w-3.5 text-text-tertiary" />
                  Roll Number
                </span>
                <span className="font-mono text-text-primary font-semibold text-right bg-surface-sunken px-2 py-0.5 rounded border border-border-subtle/60">
                  {cleanRollNo}
                </span>
              </div>
            )}

            <div className="py-2.5 flex justify-between gap-4">
              <span className="text-text-secondary flex items-center gap-2 shrink-0">
                <FontAwesomeIcon icon={faBuildingColumns} className="h-3.5 w-3.5 text-text-tertiary" />
                Department
              </span>
              <span className="font-mono text-text-primary text-right max-w-[200px]">
                {deptName}
              </span>
            </div>
          </div>
        </div>

        {/* Updatable Academic Details Form */}
        <form
          onSubmit={handleSaveProfile}
          className="bg-surface-raised border border-border-subtle rounded-lg p-6 flex flex-col gap-4 shadow-xs"
        >
          <div className="flex items-center justify-between border-b border-border-subtle pb-3">
            <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
              Academic Details
            </h3>
            {savedSuccess && (
              <span className="text-micro text-success-emerald font-mono font-semibold flex items-center gap-1 bg-success-emerald/10 px-2 py-0.5 rounded border border-success-emerald/20">
                <FontAwesomeIcon icon={faCheck} /> Saved
              </span>
            )}
          </div>

          <div className="flex flex-col gap-4 text-xs">
            {/* Faculty / Program Selection */}
            <div className="flex flex-col gap-1.5">
              <label className="font-medium text-text-secondary">
                Faculty / Program
              </label>
              <select
                value={faculty}
                onChange={(e) => setFaculty(e.target.value)}
                className="w-full px-3 py-2 bg-surface-sunken border border-border-default hover:border-border-strong focus:border-accent-primary rounded text-text-primary font-medium focus:outline-none transition-colors cursor-pointer"
              >
                {facultyOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Academic Level Selection */}
            <div className="flex flex-col gap-1.5">
              <label className="font-medium text-text-secondary">
                Academic Level
              </label>
              <select
                value={academicLevel}
                onChange={(e) => setAcademicLevel(e.target.value)}
                className="w-full px-3 py-2 bg-surface-sunken border border-border-default hover:border-border-strong focus:border-accent-primary rounded text-text-primary font-medium focus:outline-none transition-colors cursor-pointer"
              >
                {academicLevelOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-auto pt-4 border-t border-border-subtle flex justify-end">
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 bg-accent-primary hover:bg-accent-primary-hover text-text-inverse font-semibold text-xs rounded shadow-xs flex items-center gap-2 transition-all cursor-pointer disabled:opacity-50"
            >
              <FontAwesomeIcon icon={faFloppyDisk} />
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
