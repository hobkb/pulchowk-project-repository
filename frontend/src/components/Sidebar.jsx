import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { 
  faChartSimple, 
  faFolderTree, 
  faRobot, 
  faBookmark, 
  faUserCircle, 
  faGear, 
  faUpload, 
  faListCheck, 
  faDatabase, 
  faClock, 
  faCheckCircle, 
  faCircleXmark 
} from "@fortawesome/free-solid-svg-icons";

export default function Sidebar({ isCollapsed, pendingApprovalsCount = 0 }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const generalNavItems = [
    { name: "Dashboard", path: "/dashboard", icon: faChartSimple },
    { name: "Browse Projects", path: "/projects", icon: faFolderTree },
    { name: "AI Assistant", path: "/assistant", icon: faRobot, isAi: true },
    { name: "Bookmarks", path: "/bookmarks", icon: faBookmark, comingSoon: true },
    { name: "Profile", path: "/profile", icon: faUserCircle },
    { name: "Settings", path: "/settings", icon: faGear }
  ];

  const adminNavItems = [
    { name: "Dashboard", path: "/dashboard", icon: faChartSimple },
    { name: "Browse Projects", path: "/projects", icon: faFolderTree },
    { name: "Upload Project", path: "/admin/upload", icon: faUpload },
    {
      name: "Pending Approvals",
      path: "/admin/approvals",
      icon: faListCheck,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : null
    },
    { name: "Repository Management", path: "/admin/repository", icon: faDatabase },
    { name: "Profile", path: "/profile", icon: faUserCircle },
    { name: "Settings", path: "/settings", icon: faGear }
  ];

  const navItems = isAdmin ? adminNavItems : generalNavItems;

  const renderBadge = (count, isCollapsed) => {
    if (!count) return null;
    if (isCollapsed) {
      return <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-warning-amber" />;
    }
    return (
      <span className="bg-warning-amber/15 border border-warning-amber/20 text-warning-amber text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full leading-none">
        {count}
      </span>
    );
  };

  const renderStatusIcon = (status, size = "h-3 w-3") => {
    switch (status) {
      case "approved":
        return <FontAwesomeIcon icon={faCheckCircle} className={`${size} text-success-emerald`} />;
      case "pending":
        return <FontAwesomeIcon icon={faClock} className={`${size} text-warning-amber`} />;
      case "rejected":
        return <FontAwesomeIcon icon={faCircleXmark} className={`${size} text-error-red`} />;
      default:
        return <FontAwesomeIcon icon={faClock} className={`${size} text-warning-amber`} />;
    }
  };

  return (
    <aside className={`bg-surface-raised border-r border-border-subtle flex flex-col flex-shrink-0 transition-all duration-300 ${
      isCollapsed ? "w-[72px]" : "w-[260px]"
    } min-h-[calc(100vh-64px)]`}>
      <nav className="flex-1 py-4 flex flex-col gap-1 overflow-y-auto px-3">
        {navItems.map((item) => {
          if (item.comingSoon) {
            return (
              <div
                key={item.name}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-text-tertiary/50 cursor-not-allowed select-none ${
                  isCollapsed ? "justify-center" : ""
                }`}
                title={`${item.name} (Coming Soon)`}
              >
                <FontAwesomeIcon icon={item.icon} className="h-4 w-4 shrink-0" />
                {!isCollapsed && (
                  <div className="flex items-center justify-between flex-1">
                    <span className="text-sm font-medium">{item.name}</span>
                    <span className="text-[9px] font-mono border border-border-subtle px-1 rounded-sm text-text-tertiary/40">
                      Soon
                    </span>
                  </div>
                )}
              </div>
            );
          }

          return (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md font-medium text-sm transition-all duration-150 relative border-l-2 cursor-pointer ${
                  isCollapsed ? "justify-center" : ""
                } ${
                  isActive
                    ? "bg-surface-hover border-accent-primary text-text-primary"
                    : "border-transparent text-text-secondary hover:bg-surface-hover/50 hover:text-text-primary"
                }`
              }
            >
              <FontAwesomeIcon icon={item.icon} className={`h-4 w-4 shrink-0 ${item.isAi ? "text-accent-violet" : ""}`} />
              {!isCollapsed && <span className="flex-1">{item.name}</span>}

              {item.badge !== undefined && renderBadge(item.badge, isCollapsed)}
            </NavLink>
          );
        })}
      </nav>

      {/* Sidebar Footer - always visible when expanded */}
      {!isCollapsed && (
        <div className="p-4 border-t border-border-subtle">
          <span className="text-micro font-mono text-text-tertiary">
            v1.0.0 &middot; TU DOECE
          </span>
        </div>
      )}
    </aside>
  );
}