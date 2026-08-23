import { useCallback, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useNotifications } from "../context/NotificationsContext";
import Navbar from "./Navbar";
import { PRIMARY_NAV, adminNavFor, isAdminUser } from "../lib/nav";
import SiteFooter from "./SiteFooter";

/**
 * The application shell: header, page, footer — full width, no sidebar.
 *
 * A repository has few top-level sections, so they sit in the header and
 * the catalogue gets the whole page. Below `lg` the header's nav collapses
 * into a drawer that keeps the same labels and grouping rather than
 * shrinking them into icons.
 */
export default function DashboardLayout({ children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { user } = useAuth();
  const { unreadCount } = useNotifications();
  const isAdmin = isAdminUser(user);

  const closeMenu = useCallback(() => setMenuOpen(false), []);

  useEffect(() => {
    closeMenu();
  }, [location.pathname, closeMenu]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    function onKeyDown(event) {
      if (event.key === "Escape") closeMenu();
    }
    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [menuOpen, closeMenu]);

  const drawerLink = ({ isActive }) =>
    [
      "block border-l-[3px] px-5 py-2.5 text-sm no-underline hover:no-underline transition-colors",
      isActive
        ? "border-l-accent bg-primary-050 text-primary font-semibold"
        : "border-l-transparent text-ink-2 hover:bg-band hover:text-ink",
    ].join(" ");

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-sm focus:border focus:border-primary focus:bg-white focus:px-4 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>

      <Navbar onToggleMenu={() => setMenuOpen((open) => !open)} />

      {menuOpen && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <div className="absolute inset-0 bg-ink/40 pop-in" onClick={closeMenu} aria-hidden="true" />
          <nav
            aria-label="Sections"
            className="relative ml-auto flex h-full w-[17rem] max-w-[85vw] flex-col border-l border-line bg-white pop-in"
          >
            <div className="identity-rule h-1 shrink-0" aria-hidden="true" />
            <div className="flex-1 overflow-y-auto py-3">
              {PRIMARY_NAV.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={drawerLink}>
                  {item.label}
                </NavLink>
              ))}

              <p className="px-5 pb-1 pt-5 text-xs font-semibold text-ink-3">Your account</p>
              <NavLink to="/notifications" className={drawerLink}>
                Notifications{unreadCount > 0 ? ` (${unreadCount})` : ""}
              </NavLink>
              <NavLink to="/settings" className={drawerLink}>
                Account
              </NavLink>

              {isAdmin && (
                <>
                  <p className="px-5 pb-1 pt-5 text-xs font-semibold text-ink-3">Administration</p>
                  {adminNavFor(user).map((item) => (
                    <NavLink key={item.to} to={item.to} className={drawerLink}>
                      {item.label}
                    </NavLink>
                  ))}
                </>
              )}
            </div>
          </nav>
        </div>
      )}

      <main id="main" className="flex-1">
        {children}
      </main>

      <SiteFooter />
    </div>
  );
}
