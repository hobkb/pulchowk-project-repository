import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import GoogleLoginButton from "../components/GoogleLoginButton";
import SiteFooter from "../components/SiteFooter";
import { Card, Container, ErrorNotice } from "../components/ui";
import tuLogo from "../assets/tu.png";

/**
 * The sign-in page.
 *
 * Presented as a repository front door: the institutional lockup, a plain
 * statement of what the collection is, and the sign-in panel. No hero
 * image, no feature bullets, no split marketing panel.
 */
export default function Landing() {
  const { status } = useAuth();
  const location = useLocation();
  const [error, setError] = useState(null);

  if (status === "authenticated") {
    // Return the reader to wherever they were headed before being asked to
    // sign in, rather than always the home page.
    const intended = location.state?.from;
    return (
      <Navigate
        to={intended ? `${intended.pathname}${intended.search || ""}` : "/dashboard"}
        replace
      />
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="bg-white">
        <Container width="wide" className="flex items-center gap-3 px-5 sm:px-8 py-3">
          <img src={tuLogo} alt="" aria-hidden="true" className="h-10 w-10 shrink-0 object-contain" />
          <span className="leading-tight">
            <span className="block text-base font-bold text-nav">
              Pulchowk Project Repository
            </span>
            <span className="block text-xs font-bold text-accent">
              Institute of Engineering, Tribhuvan University
            </span>
          </span>
        </Container>
        <div className="identity-rule h-1" aria-hidden="true" />
      </header>

      <main className="flex-1">
        <Container width="normal" className="px-5 sm:px-8 py-12 sm:py-16">
          <div className="grid grid-cols-1 gap-10 md:grid-cols-2 items-start">
            <div>
              <h1 className="text-hero">Engineering project repository</h1>
              <p className="mt-4 text-base text-ink-2">
                A catalogue of student and faculty project reports submitted at Pulchowk Campus.
                Each record lists its authors, supervisor, department and abstract.
              </p>
              <p className="mt-3 text-base text-ink-2">
                Full project reports are held confidentially by the department and are not
                published here; a copy can be requested from a project&rsquo;s authors.
              </p>
            </div>

            <Card>
              <div className="border-b border-line bg-band px-5 py-3 rounded-t-md">
                <h2 className="text-section">Sign in</h2>
              </div>
              <div className="px-5 py-5">
                <p className="mb-4 text-sm text-ink-2">
                  Use the Google account issued to you by the campus.
                </p>

                <GoogleLoginButton onError={(err) => setError(err)} />

                {error && (
                  <ErrorNotice
                    title="Sign-in was refused"
                    detail={
                      error.message ||
                      "This repository is open to institutional accounts only."
                    }
                    className="mt-4"
                  />
                )}

                {/* States the rule the backend actually enforces:
                    GoogleService.verify_id_token rejects any address that
                    does not end in @pcampus.edu.np. */}
                <p className="mt-4 border-t border-line pt-3 text-xs text-ink-3">
                  Access is restricted to <span className="tnum">@pcampus.edu.np</span> accounts.
                </p>
              </div>
            </Card>
          </div>
        </Container>
      </main>

      <SiteFooter />
    </div>
  );
}
