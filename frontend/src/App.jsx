import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import ProjectDetails from "./pages/ProjectDetails";
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
        {/* Fallback to landing */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}