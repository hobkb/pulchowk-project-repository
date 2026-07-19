import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import ProjectDetails from "./pages/ProjectDetails";
import DashboardLayout from "./components/DashboardLayout";
import { useAuth } from "./context/AuthContext";

function RequireAuth({ children }) {
  const { status } = useAuth();

  if (status === "checking") {
    return (
      <div className="min-h-screen bg-surface-canvas flex items-center justify-center text-text-secondary font-mono text-xs">
        Verifying session...
      </div>
    );
  }

  if (status === "anonymous" || status === "select_role") {
    return <Navigate to="/" replace />;
  }

  return children;
}

export default function App() {
  return (
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
  );
}