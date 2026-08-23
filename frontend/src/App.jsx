import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import DashboardHome from "./pages/DashboardHome";
import ProjectDetails from "./pages/ProjectDetails";
import Profile from "./pages/Profile";
import AdminUpload from "./pages/AdminUpload";
import PendingApprovals from "./pages/PendingApprovals";
import IngestionWorkflow from "./pages/IngestionWorkflow";
import DashboardLayout from "./components/DashboardLayout";
import OnboardingModal from "./components/OnboardingModal";
import { useAuth } from "./context/AuthContext";

function RequireAuth({ children }) {
  const { status, user } = useAuth();

  if (status === "checking") {
    return (
      <div className="min-h-screen bg-surface-canvas flex items-center justify-center text-text-secondary font-mono text-xs">
        Verifying session...
      </div>
    );
  }

  // Block access to protected routes if user is not logged in or has not completed onboarding
  if (status === "anonymous" || status === "onboarding" || !user?.is_onboarded) {
    return <Navigate to="/" replace />;
  }

  return children;
}

function RequireAdmin({ children }) {
  const { status, user } = useAuth();

  if (status === "checking") {
    return (
      <div className="min-h-screen bg-surface-canvas flex items-center justify-center text-text-secondary font-mono text-xs">
        Verifying session...
      </div>
    );
  }

  if (status === "anonymous" || status === "onboarding" || !user?.is_onboarded) {
    return <Navigate to="/" replace />;
  }

  const isAdmin = user?.role === "admin" || user?.is_staff || user?.is_superuser || user?.is_department_admin;
  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

export default function App() {
  const { status } = useAuth();

  return (
    <>
      {status === "onboarding" && <OnboardingModal />}
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <DashboardLayout>
                <DashboardHome />
              </DashboardLayout>
            </RequireAuth>
          }
        />
        <Route
          path="/projects"
          element={
            <RequireAuth>
              <DashboardLayout>
                <Dashboard />
              </DashboardLayout>
            </RequireAuth>
          }
        />
        <Route
          path="/projects/:id"
          element={
            <RequireAuth>
              <DashboardLayout>
                <ProjectDetails />
              </DashboardLayout>
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth>
              <DashboardLayout>
                <Profile />
              </DashboardLayout>
            </RequireAuth>
          }
        />

        {/* Admin Ingestion & Workflow Routes */}
        <Route
          path="/admin/upload"
          element={
            <RequireAdmin>
              <DashboardLayout>
                <AdminUpload />
              </DashboardLayout>
            </RequireAdmin>
          }
        />
        <Route
          path="/admin/approvals"
          element={
            <RequireAdmin>
              <DashboardLayout>
                <PendingApprovals />
              </DashboardLayout>
            </RequireAdmin>
          }
        />
        <Route
          path="/admin/approvals/:id"
          element={
            <RequireAdmin>
              <DashboardLayout>
                <IngestionWorkflow />
              </DashboardLayout>
            </RequireAdmin>
          }
        />
        <Route
          path="/admin/jobs/:id"
          element={
            <RequireAdmin>
              <DashboardLayout>
                <IngestionWorkflow />
              </DashboardLayout>
            </RequireAdmin>
          }
        />

        {/* Fallback to landing */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}