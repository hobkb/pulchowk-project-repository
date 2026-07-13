import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import tuLogo from "../assets/tu.png";

export default function Dashboard() {
  const { user, status, logout } = useAuth();
  const navigate = useNavigate();

  if (status === "anonymous") return <Navigate to="/" replace />;
  if (status === "checking") return null;

  return (
    <nav className="flex items-center justify-between bg-white border-b border-gray-200 px-8 py-4">
      <div className="flex items-center gap-3">
        <img src={tuLogo} alt="Tribhuvan University" className="h-8 w-8" />
        <span className="font-display font-semibold text-navy">Pulchowk Project Repository</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-600">{user?.name || user?.email}</span>
        <button
          onClick={async () => { await logout(); navigate("/"); }}
          className="bg-orange hover:bg-orange-dark text-white text-sm font-semibold px-4 py-2 rounded-full"
        >
          Log out
        </button>
      </div>
    </nav>
  );
}
