import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import BrowseProjects from "./pages/BrowseProjects";
import SimilarWorkCheck from "./pages/SimilarWorkCheck";
import ProjectDetails from "./pages/ProjectDetails";
import Notifications from "./pages/Notifications";
import SavedProjects from "./pages/SavedProjects";
import AccountSettings from "./pages/AccountSettings";
import ResearchAssistant from "./pages/ResearchAssistant";
import NotFound from "./pages/NotFound";
import AdminUpload from "./pages/AdminUpload";
import PendingApprovals from "./pages/PendingApprovals";
import AccessRequests from "./pages/AccessRequests";
import RoleRequests from "./pages/RoleRequests";
import IngestionWorkflow from "./pages/IngestionWorkflow";
import DashboardLayout from "./components/DashboardLayout";
import OnboardingModal from "./components/OnboardingModal";
import { useAuth } from "./context/AuthContext";
import { faLock } from "@fortawesome/free-solid-svg-icons";
import { PageState } from "./components/ui";

function SessionCheck() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-white">
      <p className="text-sm text-ink-3">Verifying session…</p>
    </div>
  );
}

/**
 * Route guards. Both send an unauthenticated visitor to the landing page
 * remembering where they were headed, so signing in can return them there
 * rather than dumping everyone on the overview.
 */
function RequireAuth({ children }) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "checking") return <SessionCheck />;

  if (status === "anonymous" || status === "onboarding" || !user?.is_onboarded) {
    return <Navigate to="/" replace state={{ from: location }} />;
  }

  return children;
}

/**
 * Administration guard. A signed-in reader who reaches an admin route is
 * told they do not have access — the old behaviour silently redirected
 * them to the overview, which reads as the link being broken.
 */
function RequireAdmin({ children }) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "checking") return <SessionCheck />;

  if (status === "anonymous" || status === "onboarding" || !user?.is_onboarded) {
    return <Navigate to="/" replace state={{ from: location }} />;
  }

  const isAdmin =
    user?.role === "admin" || user?.is_staff || user?.is_superuser || user?.is_department_admin;

  if (!isAdmin) {
    return (
      <PageState
        tone="warn"
        icon={faLock}
        eyebrow="Restricted"
        title="This area is for department administrators"
        description="Depositing and verifying project reports is restricted to administrators. If you believe you should have access, contact your department."
      />
    );
  }

  return children;
}

/**
 * Every signed-in route shares the same shell. Admin routes additionally
 * pass through RequireAdmin *inside* the layout, so someone without
 * access sees the explanation with their navigation still around them
 * rather than being thrown out of the application.
 */
/**
 * Granting a role is strictly narrower than reviewing deposits: `is_staff`
 * makes a reviewer, so a reviewer must not be able to hand out roles. Only
 * a superuser passes here, matching the server-side IsSuperUser check.
 */
function RequireSuperUser({ children }) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "checking") return <SessionCheck />;

  if (status === "anonymous" || status === "onboarding" || !user?.is_onboarded) {
    return <Navigate to="/" replace state={{ from: location }} />;
  }

  if (!user?.is_superuser) {
    return (
      <PageState
        tone="warn"
        icon={faLock}
        eyebrow="Restricted"
        title="Only an administrator can grant roles"
        description="Approving faculty and administrator access is limited to campus administrators. If you need someone's role changed, ask one of them."
      />
    );
  }

  return children;
}

function Shell({ admin = false, superuser = false, children }) {
  let content = children;
  if (superuser) content = <RequireSuperUser>{content}</RequireSuperUser>;
  else if (admin) content = <RequireAdmin>{content}</RequireAdmin>;

  return (
    <RequireAuth>
      <DashboardLayout>{content}</DashboardLayout>
    </RequireAuth>
  );
}

function UnknownRoute() {
  const { status, user } = useAuth();

  if (status === "checking") return <SessionCheck />;

  if (status === "authenticated" && user?.is_onboarded) {
    return (
      <DashboardLayout>
        <NotFound />
      </DashboardLayout>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="identity-rule h-1" aria-hidden="true" />
      <NotFound />
    </div>
  );
}

export default function App() {
  const { status } = useAuth();

  return (
    <>
      {status === "onboarding" && <OnboardingModal />}

      <Routes>
        <Route path="/" element={<Landing />} />

        <Route path="/dashboard" element={<Shell><Dashboard /></Shell>} />
        <Route path="/projects" element={<Shell><BrowseProjects /></Shell>} />
        {/* Major and Minor are addressable categories, not filter state: the
            route fixes the type and the page keeps the rest of the search
            and filter behaviour. */}
        <Route
          path="/projects/major"
          element={<Shell><BrowseProjects projectType="Major" heading="Major projects" /></Shell>}
        />
        <Route
          path="/projects/minor"
          element={<Shell><BrowseProjects projectType="Minor" heading="Minor projects" /></Shell>}
        />
        <Route path="/similar-work-check" element={<Shell><SimilarWorkCheck /></Shell>} />
        <Route path="/projects/:id" element={<Shell><ProjectDetails /></Shell>} />
        <Route path="/bookmarks" element={<Shell><SavedProjects /></Shell>} />
        <Route path="/notifications" element={<Shell><Notifications /></Shell>} />
        <Route path="/settings" element={<Shell><AccountSettings /></Shell>} />
        <Route path="/assistant" element={<Shell><ResearchAssistant /></Shell>} />

        {/* Administration — deposit, verification and publishing. */}
        <Route path="/admin/upload" element={<Shell admin><AdminUpload /></Shell>} />
        <Route path="/admin/approvals" element={<Shell admin><PendingApprovals /></Shell>} />
        <Route path="/admin/access-requests" element={<Shell admin><AccessRequests /></Shell>} />
        <Route path="/admin/role-requests" element={<Shell superuser><RoleRequests /></Shell>} />
        <Route path="/admin/approvals/:id" element={<Shell admin><IngestionWorkflow /></Shell>} />
        <Route path="/admin/jobs/:id" element={<Shell admin><IngestionWorkflow /></Shell>} />

        {/* A real 404 — inside the shell for a signed-in reader so they
            keep their navigation, and standalone for everyone else. An
            unknown address is never silently redirected. */}
        <Route path="*" element={<UnknownRoute />} />
      </Routes>
    </>
  );
}
