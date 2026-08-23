import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faUserCircle,
  faXmark,
  faEnvelope,
  faBuildingColumns,
  faShieldHalved,
  faIdCard,
  faRightFromBracket,
  faCheckCircle,
} from "@fortawesome/free-solid-svg-icons";

export default function UserProfileModal({ user, onClose, onLogout }) {
  if (!user) return null;

  const fullName = user.first_name
    ? `${user.first_name} ${user.last_name || ""}`.trim()
    : user.username || user.email;

  const roleLabel =
    user.role === "admin" || user.is_superuser
      ? "Institutional Administrator"
      : user.is_department_admin
      ? "Department Administrator"
      : "Faculty / Researcher";

  const deptName = user.department || "Department of Electronics & Computer Engineering";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-canvas/80 backdrop-blur-sm p-4 animate-fade-in">
      <div
        className="bg-surface-raised border border-border-strong rounded-xl w-full max-w-md shadow-2xl relative overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Accent Strip */}
        <div className="h-1.5 bg-gradient-to-r from-accent-primary via-accent-violet to-accent-primary"></div>

        {/* Modal Header */}
        <div className="px-6 pt-5 pb-4 flex items-center justify-between border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <FontAwesomeIcon icon={faUserCircle} className="h-5 w-5 text-accent-primary" />
            <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
              User Profile
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-text-tertiary hover:text-text-primary p-1 rounded-md hover:bg-surface-hover transition-colors cursor-pointer"
          >
            <FontAwesomeIcon icon={faXmark} className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 flex flex-col gap-6">
          {/* User Profile Card Banner */}
          <div className="bg-surface-sunken border border-border-subtle rounded-lg p-4 flex items-center gap-4">
            <div className="h-14 w-14 rounded-full bg-accent-primary/10 border border-accent-primary/30 flex items-center justify-center text-accent-primary text-xl font-bold font-mono shrink-0">
              {fullName.charAt(0).toUpperCase()}
            </div>
            <div className="flex flex-col min-w-0">
              <h4 className="text-body font-bold text-text-primary truncate">
                {fullName}
              </h4>
              <span className="text-xs font-mono text-accent-primary font-medium mt-0.5">
                {roleLabel}
              </span>
              <span className="text-micro text-text-tertiary truncate mt-1">
                Pulchowk Campus &middot; IOE
              </span>
            </div>
          </div>

          {/* Profile Details List */}
          <div className="divide-y divide-border-subtle text-xs">
            {/* Email */}
            <div className="py-3 flex items-center justify-between gap-3">
              <span className="text-text-secondary flex items-center gap-2">
                <FontAwesomeIcon icon={faEnvelope} className="h-3.5 w-3.5 text-text-tertiary" />
                Email Address
              </span>
              <span className="font-mono text-text-primary font-medium truncate max-w-[220px]">
                {user.email}
              </span>
            </div>

            {/* Department */}
            <div className="py-3 flex items-center justify-between gap-3">
              <span className="text-text-secondary flex items-center gap-2">
                <FontAwesomeIcon icon={faBuildingColumns} className="h-3.5 w-3.5 text-text-tertiary" />
                Department
              </span>
              <span className="font-mono text-text-primary font-medium text-right truncate max-w-[200px]">
                {deptName}
              </span>
            </div>

            {/* Role / Access Level */}
            <div className="py-3 flex items-center justify-between gap-3">
              <span className="text-text-secondary flex items-center gap-2">
                <FontAwesomeIcon icon={faShieldHalved} className="h-3.5 w-3.5 text-text-tertiary" />
                Access Level
              </span>
              <span className="bg-accent-primary/10 border border-accent-primary/20 text-accent-primary px-2 py-0.5 rounded font-mono font-semibold text-[10px]">
                {user.role === "admin" || user.is_superuser ? "SUPERADMIN" : "INSTITUTIONAL USER"}
              </span>
            </div>

            {/* Account Status */}
            <div className="py-3 flex items-center justify-between gap-3">
              <span className="text-text-secondary flex items-center gap-2">
                <FontAwesomeIcon icon={faCheckCircle} className="h-3.5 w-3.5 text-success-emerald" />
                Account Status
              </span>
              <span className="text-success-emerald font-mono font-semibold text-[10px] bg-success-emerald/10 border border-success-emerald/20 px-2 py-0.5 rounded">
                Verified Active
              </span>
            </div>

            {/* Roll / Staff ID if available */}
            {user.roll_number && (
              <div className="py-3 flex items-center justify-between gap-3">
                <span className="text-text-secondary flex items-center gap-2">
                  <FontAwesomeIcon icon={faIdCard} className="h-3.5 w-3.5 text-text-tertiary" />
                  Institutional ID
                </span>
                <span className="font-mono text-text-primary font-medium">
                  {user.roll_number}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-surface-sunken/50 border-t border-border-subtle flex items-center justify-between gap-3">
          <button
            onClick={onLogout}
            className="flex items-center gap-2 px-4 py-2 bg-error-red/10 border border-error-red/30 hover:bg-error-red/20 text-error-red text-xs font-semibold rounded-md transition-all cursor-pointer"
          >
            <FontAwesomeIcon icon={faRightFromBracket} className="h-3.5 w-3.5" />
            Log Out
          </button>

          <button
            onClick={onClose}
            className="px-4 py-2 bg-surface-raised border border-border-default hover:border-border-strong text-text-primary text-xs font-semibold rounded-md transition-all cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
