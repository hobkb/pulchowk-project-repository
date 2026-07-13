import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import GoogleLoginButton from "../components/GoogleLoginButton";
import tuLogo from "../assets/tu.png";

export default function Landing() {
  const { status } = useAuth();
  if (status === "authenticated") return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen flex flex-col bg-white text-ink">
      <header className="flex items-center gap-3 px-8 bg-blue-950 py-5 border-b border-gray-200">
        <img src={tuLogo} alt="Tribhuvan University" className="h-9 w-9" />
        <div className="leading-tight">
          <p className="font-display font-semibold text-blue-200">DOECE</p>
          <p className="text-xs text-gray-100">Pulchowk Campus · IOE · Tribhuvan University</p>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 text-center">
        <div className="max-w-lg">
          <p className="text-orange-600 text-sm font-semibold uppercase tracking-wide mb-3">
            Department of Electronics &amp; Computer Engineering
          </p>
          <h1 className="font-display text-4xl md:text-5xl text-navy mb-4">
            Pulchowk Project Repository
          </h1>
          <p className="text-gray-600 mb-10">
            Search, revisit, and build on undergraduate projects from the department.
          </p>
          <div className="inline-flex flex-col items-center gap-4 border border-gray-200 rounded-xl shadow-sm p-7">
            <p className="text-sm text-gray-500">Sign in with your Google account</p>
            <GoogleLoginButton />
          </div>
        </div>
      </main>

      <footer className="text-center text-xs text-gray-400 py-4 border-t border-gray-200">
        Institute of Engineering, Tribhuvan University
      </footer>
    </div>
  );
}