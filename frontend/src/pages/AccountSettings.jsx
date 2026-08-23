import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { roleRequestsApi } from "../api/client";
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  CardHeader,
  Container,
  Crumb,
  Meta,
  PageHeading,
  Status,
} from "../components/ui";

/**
 * Account.
 *
 * Read-only, and honest about why. Everything shown comes from
 * GET /accounts/me/, whose serializer declares every field read-only —
 * the backend exposes no endpoint for a user to change their own name,
 * email, department or role after onboarding. So this page shows what is
 * on record and says where a change has to come from, rather than
 * offering disabled inputs beside a Save button that could never work.
 */

function accessLevel(user) {
  if (user?.is_superuser || user?.role === "admin" || user?.is_staff) {
    return {
      tone: "info",
      title: "Administrator",
      detail:
        "You can deposit reports, verify extracted metadata, publish records, and read full project reports.",
    };
  }
  if (user?.is_department_admin) {
    return {
      tone: "info",
      title: "Department administrator",
      detail:
        "You can deposit reports, verify extracted metadata and publish records for your department.",
    };
  }
  return {
    tone: "neutral",
    title: user?.role === "faculty" ? "Faculty" : "Student",
    detail:
      "You can search the catalogue and read project abstracts. Full reports can be requested from their authors.",
  };
}

const REQUESTED_ROLE_LABEL = { admin: "Administrator", faculty: "Faculty" };

export default function AccountSettings() {
  const { user } = useAuth();
  const profile = user?.profile || null;
  // Choosing faculty or administrator during onboarding files a request
  // rather than granting anything, so the applicant is told where that
  // request stands instead of being left wondering why nothing changed.
  const [roleRequest, setRoleRequest] = useState(null);

  useEffect(() => {
    let cancelled = false;
    roleRequestsApi
      .mine()
      .then((body) => {
        if (!cancelled) setRoleRequest(body?.data || null);
      })
      .catch(() => {
        // The rest of the page is still worth showing without it.
      });
    return () => {
      cancelled = true;
    };
  }, []);
  const access = accessLevel(user);
  const accountName = [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim();

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb last>Account</Crumb>
      </Breadcrumb>

      <Container width="normal" className="px-5 sm:px-8 py-8">
        <PageHeading
          title="Account"
          lead="What the repository holds about your account, and where each part of it comes from."
        />

        <div className="mt-7 grid grid-cols-1 gap-6 md:grid-cols-2 items-start">
          <Card>
            <CardHeader title="Sign-in account" />
            <dl className="divide-y divide-line px-4">
              <Meta label="Email address">{user?.email || "—"}</Meta>
              <Meta label="Name">{accountName || "Not provided"}</Meta>
            </dl>
            <p className="border-t border-line bg-band px-4 py-3 text-xs text-ink-2">
              Your email address and name come from the Google account you sign in with. Change
              them there and they will update here at your next sign-in.
            </p>
          </Card>

          <Card>
            <CardHeader title="Repository profile" />
            {profile ? (
              <>
                <dl className="divide-y divide-line px-4">
                  <Meta label="Full name">{profile.full_name || "—"}</Meta>
                  <Meta label="Department">{profile.department || "Not recorded"}</Meta>

                  {profile.kind === "student" && (
                    <>
                      <Meta label="Roll number">
                        <span className="tnum">{profile.roll_number || "Not recorded"}</span>
                      </Meta>
                      <Meta label="Academic level">{profile.academic_level || "Not recorded"}</Meta>
                    </>
                  )}

                  {profile.kind === "faculty" && (
                    <>
                      {profile.title && <Meta label="Title">{profile.title}</Meta>}
                      <Meta label="Designation">{profile.designation || "Not recorded"}</Meta>
                      {profile.research_group && (
                        <Meta label="Research group">{profile.research_group}</Meta>
                      )}
                    </>
                  )}
                </dl>
                <p className="border-t border-line bg-band px-4 py-3 text-xs text-ink-2">
                  Recorded when you completed onboarding, and used when your name appears on a
                  project record. The repository has no self-service editing for these details —
                  ask a department administrator to make a correction.
                </p>
              </>
            ) : (
              <p className="px-4 py-5 text-sm text-ink-2">
                No repository profile is linked to this account yet. One is created when you
                complete onboarding.
              </p>
            )}
          </Card>

          <Card>
            <CardHeader title="Access" />
            <div className="px-4 py-4">
              <Status tone={access.tone}>{access.title}</Status>
              <p className="mt-2.5 text-sm text-ink-2">{access.detail}</p>
              <p className="mt-2 text-xs text-ink-3">
                Access level is assigned by the department, not chosen here.
              </p>

              {roleRequest && roleRequest.status === "PENDING" && (
                <div className="mt-4 border-t border-line pt-3">
                  <Status tone="warn">Awaiting approval</Status>
                  <p className="mt-2 text-sm text-ink-2">
                    You asked to join as{" "}
                    {REQUESTED_ROLE_LABEL[roleRequest.requested_role] ||
                      roleRequest.requested_role}
                    . An administrator has to approve that before it takes effect. You will
                    get a notification when it is decided.
                  </p>
                </div>
              )}

              {roleRequest && roleRequest.status === "DECLINED" && (
                <div className="mt-4 border-t border-line pt-3">
                  <Status tone="bad">Declined</Status>
                  <p className="mt-2 text-sm text-ink-2">
                    Your request for{" "}
                    {REQUESTED_ROLE_LABEL[roleRequest.requested_role] ||
                      roleRequest.requested_role}{" "}
                    access was not approved. Contact your department if you think this is
                    wrong.
                  </p>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Notifications" />
            <div className="px-4 py-4">
              <p className="text-sm text-ink-2">
                You receive a notification when a report you deposited finishes processing, when
                a deposit is waiting for verification, when processing fails, and when a project
                is published.
              </p>
              <Button as={Link} to="/notifications" variant="secondary" size="sm" className="mt-3">
                View notifications
              </Button>
            </div>
          </Card>
        </div>

        <Alert tone="neutral" className="mt-6">
          Signing out is available from the account menu in the header.
        </Alert>
      </Container>
    </>
  );
}
