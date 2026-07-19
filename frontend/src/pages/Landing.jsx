import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import GoogleLoginButton from "../components/GoogleLoginButton";
import tuLogo from "../assets/tu.png";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faUserCircle, faShield, faSearch, faMagic } from "@fortawesome/free-solid-svg-icons";

export default function Landing() {
  const { status, selectRole } = useAuth();
  const [error, setError] = useState(null);

  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-canvas text-text-primary selection:bg-accent-primary/20 selection:text-accent-primary">
      {/* Institutional Branding Header */}
      <header className="flex items-center gap-3 px-6 md:px-8 py-5 border-b border-border-subtle bg-surface-raised/60 sticky top-0 z-50">
        <img src={tuLogo} alt="Tribhuvan University Logo" className="h-9 w-9 object-contain" />
        <div className="leading-tight">
          <p className="font-mono text-xs uppercase tracking-wider text-accent-gold font-semibold">DOECE</p>
          <p className="text-xs text-text-secondary">Pulchowk Campus · IOE · Tribhuvan University</p>
        </div>
      </header>

      {/* Main Login Screen */}
      <main className="flex-1 flex items-center justify-center px-4 py-12 md:py-24">
        <div className="w-full max-w-md flex flex-col gap-6">
          
          {/* Main Card */}
          <div className="bg-surface-raised border border-border-subtle rounded-lg p-8 flex flex-col gap-6 relative overflow-hidden transition-all duration-300">
            {/* Institutional accent line at top - 2px gold per §2.1 */}
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-accent-gold" />

            {/* Wordmark and Intro */}
            <div className="text-center flex flex-col items-center gap-3">
              <div className="h-16 w-16 rounded-full bg-surface-sunken border border-border-default flex items-center justify-center mb-1">
                <img src={tuLogo} alt="TU Logo" className="h-10 w-10 object-contain" />
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-text-primary">
                Pulchowk Project Repository
              </h1>
              <p className="text-body text-text-secondary leading-relaxed">
                Sign in with your Google account to access the Pulchowk Project Discovery and Knowledge Retrieval Platform.
              </p>
            </div>

            {status === "select_role" ? (
              <div className="flex flex-col gap-4 animate-fade-in">
                <div className="text-center mb-2">
                  <p className="text-[11px] font-mono uppercase tracking-wider text-accent-gold font-semibold">
                    Choose Development Role
                  </p>
                  <p className="text-body-sm text-text-secondary mt-1">
                    Select a role for this browser session:
                  </p>
                </div>
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => selectRole("student")}
                    className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-surface-sunken hover:bg-surface-hover border border-border-default hover:border-border-strong text-text-primary text-sm font-semibold rounded-md transition-all cursor-pointer"
                  >
                    <FontAwesomeIcon icon={faUserCircle} className="h-5 w-5 text-accent-primary" />
                    <span>General User / Student</span>
                  </button>
                  <button
                    onClick={() => selectRole("admin")}
                    className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-surface-sunken hover:bg-surface-hover border border-border-default hover:border-border-strong text-text-primary text-sm font-semibold rounded-md transition-all cursor-pointer"
                  >
                    <FontAwesomeIcon icon={faUserCircle} className="h-5 w-5 text-accent-gold" />
                    <span>Administrator</span>
                  </button>
                </div>
              </div>
            ) : (
              <>
                {/* Google OAuth Login Area */}
                <div className="flex flex-col items-center gap-4 py-2">
                  <GoogleLoginButton onError={(err) => setError(err)} />
                </div>

                {/* Domain-Rejection Alert State */}
                {error && (
                  <div className="bg-error-red/10 border border-error-red/20 text-error-red text-body-sm rounded-md p-4 flex flex-col gap-1 transition-opacity duration-300 animate-fade-in">
                    <p className="font-semibold flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-error-red" /> Access Restricted
                    </p>
                    <p className="text-text-secondary leading-normal">
                      This repository is only available to institutional accounts. Please sign in with your college-issued email.
                    </p>
                  </div>
                )}
                
                {/* Domain info note */}
                <div className="border-t border-border-subtle pt-4 text-center">
                  <span className="text-micro font-mono uppercase tracking-wider text-text-tertiary">
                    Restricted to @*.ioe.edu.np domains
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-body-sm text-text-tertiary py-6 border-t border-border-subtle bg-surface-sunken/30">
        <p>© {new Date().getFullYear()} Department of Electronics & Computer Engineering, Pulchowk Campus</p>
        <p className="text-micro mt-1 text-text-tertiary/70">Institute of Engineering, Tribhuvan University</p>
      </footer>
    </div>
  );
}