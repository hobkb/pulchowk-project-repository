import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faBars,
  faChevronDown,
  faRightFromBracket,
} from "@fortawesome/free-solid-svg-icons";
import { useAuth } from "../context/AuthContext";
import tuLogo from "../assets/tu.png";
import NotificationBell from "./NotificationBell";
import {
  ACCOUNT_NAV,
  ADMIN_PRIMARY_NAV,
  PRIMARY_NAV,
  adminSecondaryFor,
  isAdminUser,
} from "../lib/nav";

/**
 * The repository header.
 *
 * A single white bar carrying the crest and wordmark on the left, the
 * primary sections in the middle, and account controls on the right —
 * closed by the institutional rule (accent over primary). This is the
 * masthead pattern academic repositories use, but the identity, the
 * wordmark lockup and the section names are Pulchowk's own.
 *
 * Primary navigation lives here rather than in a left sidebar: a
 * repository has few top-level sections, and putting them across the top
 * gives the catalogue the full width of the page.
 */

function roleTitle(user) {
  if (user?.is_superuser || user?.role === "admin" || user?.is_staff) return "Administrator";
  if (user?.is_department_admin) return "Department administrator";
  if (user?.role === "faculty") return "Faculty";
  if (user?.role === "student") return "Student";
  return "Reader";
}

function displayName(user) {
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim();
  if (name) return name;
  return user?.profile?.full_name || user?.email || "Account";
}

/**
 * A top-level section that has sub-sections.
 *
 * Opened on hover and on keyboard focus rather than on click, so it needs no
 * open/closed state and stays reachable by tab. The parent remains a real
 * link: "Projects" still goes to the whole catalogue, and the panel only
 * offers the narrower routes beneath it.
 */
function TopLinkGroup({ to, label, end, children, onNavigate }) {
  return (
    <div className="relative flex items-stretch group">
      <TopLink to={to} label={label} end={end} onNavigate={onNavigate} />
      <div className="pointer-events-none absolute left-0 top-full z-30 hidden min-w-[13rem] border border-line bg-white py-1 opacity-0 shadow-sm transition-opacity group-hover:pointer-events-auto group-hover:block group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:block group-focus-within:opacity-100">
        {children.map((child) => (
          <NavLink
            key={child.to}
            to={child.to}
            end={child.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              [
                "block whitespace-nowrap px-4 py-2 text-sm no-underline transition-colors hover:no-underline",
                isActive ? "bg-band font-semibold text-ink" : "text-ink-2 hover:bg-band hover:text-ink",
              ].join(" ")
            }
          >
            {child.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

function TopLink({ to, label, end, onNavigate }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        [
          // The current section is marked by an accent underline, not a
          // filled pill — restrained, and it keeps the bar quiet.
          "relative whitespace-nowrap px-3 py-4 text-sm font-bold transition-colors no-underline hover:no-underline",
          isActive
            ? "text-nav after:absolute after:inset-x-2 after:bottom-0 after:h-[3px] after:bg-accent"
            : "text-nav/70 hover:text-nav",
        ].join(" ")
      }
    >
      {label}
    </NavLink>
  );
}

const MENU_ITEM =
  "block px-4 py-2 text-sm text-ink-2 no-underline hover:bg-band hover:text-ink hover:no-underline";

/**
 * Account, saved work, and -- for a reviewer -- the administrative queues.
 *
 * The queues are periodic work rather than places a reader navigates to, so
 * they sit here instead of competing with the catalogue for space in the bar.
 */
function AccountMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const adminLinks = adminSecondaryFor(user);

  useEffect(() => {
    if (!open) return undefined;
    function onPointerDown(event) {
      if (!wrapRef.current?.contains(event.target)) setOpen(false);
    }
    function onKeyDown(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-ink-2 hover:bg-band hover:text-ink transition-colors cursor-pointer"
      >
        <span
          aria-hidden="true"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-primary text-xs font-bold text-white"
        >
          {displayName(user).slice(0, 1).toUpperCase()}
        </span>
        <span className="hidden lg:inline max-w-[10rem] truncate">{displayName(user)}</span>
        <FontAwesomeIcon icon={faChevronDown} className="h-3 w-3 shrink-0" aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-1 w-60 rounded-md border border-line bg-white shadow-pop pop-in"
        >
          <div className="border-b border-line bg-band px-4 py-3 rounded-t-md">
            <p className="text-sm font-semibold text-ink truncate">{displayName(user)}</p>
            <p className="text-xs text-ink-2 truncate">{user?.email}</p>
            <p className="text-xs text-ink-3 mt-1">{roleTitle(user)}</p>
          </div>
          {ACCOUNT_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              role="menuitem"
              onClick={() => setOpen(false)}
              className={MENU_ITEM}
            >
              {item.label}
            </NavLink>
          ))}

          {adminLinks.length > 0 && (
            <>
              <p className="border-t border-line px-4 pt-2 pb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">
                Administration
              </p>
              {adminLinks.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className={MENU_ITEM}
                >
                  {item.label}
                </NavLink>
              ))}
            </>
          )}

          <button
            type="button"
            role="menuitem"
            onClick={onLogout}
            className="flex w-full items-center gap-2 border-t border-line px-4 py-2 text-sm text-err hover:bg-err-bg transition-colors cursor-pointer rounded-b-md"
          >
            <FontAwesomeIcon icon={faRightFromBracket} className="h-3.5 w-3.5" aria-hidden="true" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Navbar({ onToggleMenu }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = isAdminUser(user);

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <header className="sticky top-0 z-40 bg-white">
      <div className="mx-auto flex max-w-[1180px] items-stretch gap-2 px-5 sm:px-8">
        <NavLink
          to="/dashboard"
          className="flex items-center gap-3 py-3 shrink-0 no-underline hover:no-underline"
        >
          <img src={tuLogo} alt="" aria-hidden="true" className="h-10 w-10 shrink-0 object-contain" />
          <span className="min-w-0 leading-tight">
            <span className="block text-base font-bold text-nav">Pulchowk Project Repository</span>
            <span className="hidden text-xs font-bold text-accent sm:block">
              Institute of Engineering, Tribhuvan University
            </span>
          </span>
        </NavLink>

        <nav aria-label="Primary" className="ml-5 hidden items-stretch xl:flex">
          {PRIMARY_NAV.map((item) =>
            item.children ? (
              <TopLinkGroup key={item.to} {...item} />
            ) : (
              <TopLink key={item.to} {...item} />
            )
          )}
          {isAdmin &&
            ADMIN_PRIMARY_NAV.map((item) => <TopLink key={item.to} {...item} />)}
        </nav>

        <div className="ml-auto flex items-center gap-1 shrink-0">
          <NotificationBell />
          <AccountMenu user={user} onLogout={handleLogout} />
          <button
            type="button"
            onClick={onToggleMenu}
            aria-label="Open menu"
            className="ml-1 rounded-sm p-2 text-ink-2 transition-colors hover:bg-band hover:text-ink cursor-pointer xl:hidden"
          >
            <FontAwesomeIcon icon={faBars} className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* The institutional rule: accent over primary. Used once, here. */}
      <div className="identity-rule h-1" aria-hidden="true" />
    </header>
  );
}
