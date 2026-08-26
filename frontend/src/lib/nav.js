/**
 * Shared navigation facts, kept out of the Navbar component file so both
 * the header and the mobile drawer can import them without pulling in a
 * component (and so fast refresh stays intact).
 *
 * Every entry resolves to a route that exists in App.jsx. Nothing is
 * listed here that has no page behind it.
 */

export function isAdminUser(user) {
  return Boolean(
    user?.role === "admin" ||
      user?.is_staff ||
      user?.is_superuser ||
      user?.is_department_admin
  );
}

/**
 * The bar carries what a reader navigates by. Everything that is a task
 * rather than a destination -- saved work, and the administrative queues --
 * lives in the account menu instead. A header with ten links in it stops
 * being navigation and becomes a list.
 */
export const PRIMARY_NAV = [
  { to: "/dashboard", label: "Home", end: true },
  {
    to: "/projects",
    label: "Projects",
    end: true,
    // Major and Minor are real routes, not filter state buried in the
    // catalogue page: they are how the department talks about its own work,
    // so they get addresses that can be linked and bookmarked.
    children: [
      { to: "/projects", label: "All projects", end: true },
      { to: "/projects/major", label: "Major projects" },
      { to: "/projects/minor", label: "Minor projects" },
    ],
  },
  { to: "/similar-work-check", label: "Similar work check" },
  { to: "/assistant", label: "Research assistant" },
];

/** Depositing a report is the administrative task with a reason to be one
 *  click away; the queues below it are periodic work, not navigation. */
export const ADMIN_PRIMARY_NAV = [
  { to: "/admin/upload", label: "Deposit report" },
];

/** Reviewed periodically rather than navigated to, so these sit in the
 *  account menu. Granting a role is superuser-only, so a staff reviewer is
 *  not shown a link to a page that would only refuse them. */
export const ADMIN_SECONDARY_NAV = [
  { to: "/admin/approvals", label: "Verification queue" },
  { to: "/admin/access-requests", label: "Access requests" },
  { to: "/admin/role-requests", label: "Role requests", superuserOnly: true },
];

/** Personal, and the same for every signed-in reader. */
export const ACCOUNT_NAV = [
  { to: "/bookmarks", label: "Saved projects" },
  { to: "/notifications", label: "Notifications" },
  { to: "/settings", label: "Account" },
];

export function adminSecondaryFor(user) {
  if (!isAdminUser(user)) return [];
  return ADMIN_SECONDARY_NAV.filter(
    (item) => !item.superuserOnly || user?.is_superuser
  );
}

/** Every administration link this user can actually use, in one list, for
 *  the mobile drawer where there is room to show them all. */
export function adminNavFor(user) {
  if (!isAdminUser(user)) return [];
  return [...ADMIN_PRIMARY_NAV, ...adminSecondaryFor(user)];
}
