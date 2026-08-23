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

export const PRIMARY_NAV = [
  { to: "/dashboard", label: "Home", end: true },
  { to: "/projects", label: "Projects" },
  { to: "/bookmarks", label: "Saved" },
  { to: "/assistant", label: "Research assistant" },
];

export const ADMIN_NAV = [
  { to: "/admin/upload", label: "Deposit report" },
  { to: "/admin/approvals", label: "Verification queue" },
  { to: "/admin/access-requests", label: "Access requests" },
  // Granting a role is superuser-only, so a staff reviewer is not shown a
  // link to a page that would only refuse them.
  { to: "/admin/role-requests", label: "Role requests", superuserOnly: true },
];

/** The administration links this particular user can actually use. */
export function adminNavFor(user) {
  return ADMIN_NAV.filter((item) => !item.superuserOnly || user?.is_superuser);
}
