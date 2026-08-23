import { useState, useRef, useEffect } from "react";
import { useNavigate, NavLink, useSearchParams, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faRightFromBracket, faUserCircle, faBell, faChartSimple } from "@fortawesome/free-solid-svg-icons";
import tuLogo from "../assets/tu.png";
import SearchBar from "./SearchBar";
import UserProfileModal from "./UserProfileModal";

function UserMenu({ user, onLogout, onOpenProfile }) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target) && !triggerRef.current?.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fullName = user?.first_name ? `${user.first_name} ${user.last_name || ""}`.trim() : user?.username || user?.email;
  let roleLabel = "Student";
  if (user?.role === "admin" || user?.is_superuser) {
    roleLabel = "Administrator";
  } else if (user?.is_department_admin) {
    roleLabel = "Department Admin";
  } else if (user?.role === "faculty" || user?.inferred_role === "faculty") {
    roleLabel = "Faculty";
  } else if (user?.role === "student" || user?.inferred_role === "student") {
    roleLabel = "Student";
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 border-l border-border-subtle pl-4 pr-2 py-1.5 rounded-md hover:bg-surface-hover transition-colors cursor-pointer"
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <div className="hidden lg:flex flex-col text-right">
          <span className="text-body font-medium text-text-primary">{fullName}</span>
          <span className="text-body-sm font-mono text-text-tertiary">{user?.email}</span>
        </div>
        <FontAwesomeIcon icon={faUserCircle} className="h-5 w-5 text-text-secondary shrink-0" aria-hidden="true" />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-56 bg-surface-overlay border border-border-default rounded-lg shadow-lg py-1.5 z-50 animate-fade-in">
          <div className="px-3 py-2.5 border-b border-border-subtle">
            <p className="text-body font-medium text-text-primary">{fullName}</p>
            <p className="text-body-sm font-mono text-text-tertiary truncate">{user?.email}</p>
            <p className="text-micro font-semibold text-accent-primary mt-1">{roleLabel}</p>
          </div>
          
          <NavLink
            to="/profile"
            onClick={() => setIsOpen(false)}
            className="flex items-center gap-3 w-full px-3 py-2 text-body text-text-secondary hover:text-text-primary hover:bg-surface-hover cursor-pointer text-left"
          >
            <FontAwesomeIcon icon={faUserCircle} className="h-4 w-4 text-accent-primary" />
            View Profile
          </NavLink>

          <div className="border-t border-border-subtle my-1.5" />
          <button
            onClick={onLogout}
            className="flex items-center gap-3 w-full px-3 py-2 text-body text-error-red hover:bg-surface-hover cursor-pointer text-left"
          >
            <FontAwesomeIcon icon={faRightFromBracket} className="h-4 w-4" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Navbar({ onToggleSidebar }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);

  const isAdmin = user?.role === "admin" || user?.is_staff || user?.is_superuser || user?.is_department_admin;
  const searchQuery = searchParams.get("q") || "";

  const handleSearchChange = (val) => {
    const isSearchablePage = location.pathname === "/dashboard" || location.pathname === "/projects";
    if (!isSearchablePage) {
      navigate(`/dashboard?q=${encodeURIComponent(val)}`);
    } else {
      const newParams = new URLSearchParams(searchParams);
      if (val) {
        newParams.set("q", val);
      } else {
        newParams.delete("q");
      }
      setSearchParams(newParams, { replace: true });
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <>
      <nav className="h-16 sticky top-0 z-40 bg-surface-raised border-b border-border-subtle flex items-center px-6 gap-4">
        {/* Left: Brand Section */}
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-1.5 rounded-md hover:bg-surface-hover border border-border-subtle text-text-secondary hover:text-text-primary transition-colors"
            aria-label="Toggle menu"
          >
            <FontAwesomeIcon icon={faChartSimple} className="h-5 w-5" />
          </button>
          <NavLink to="/dashboard" className="flex items-center gap-2.5">
            <img src={tuLogo} alt="TU Logo" className="h-7 w-7 object-contain" />
            <span className="font-semibold text-text-primary text-sm tracking-tight hidden sm:inline">
              Pulchowk Project Repository
            </span>
          </NavLink>
        </div>

        {/* Center: Search Bar */}
        <div className="flex-1 flex justify-center min-w-0">
          <SearchBar
            variant="hero"
            placeholder="Search projects by topic, technology, title, or supervisor..."
            value={searchQuery}
            onChange={handleSearchChange}
            className="w-full max-w-[680px]"
          />
        </div>

        {/* Right: User Controls */}
        <div className="flex items-center gap-4 shrink-0">
          {/* Admin Notifications Bell */}
          {isAdmin && (
            <button className="relative p-1.5 rounded-md hover:bg-surface-hover text-text-secondary hover:text-text-primary transition-colors cursor-pointer">
              <FontAwesomeIcon icon={faBell} className="h-4 w-4" />
              <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-warning-amber" />
            </button>
          )}

          {/* User Menu */}
          <UserMenu
            user={user}
            onLogout={handleLogout}
            onOpenProfile={() => setIsProfileModalOpen(true)}
          />
        </div>
      </nav>

      {/* User Profile Modal */}
      {isProfileModalOpen && (
        <UserProfileModal
          user={user}
          onClose={() => setIsProfileModalOpen(false)}
          onLogout={handleLogout}
        />
      )}
    </>
  );
}