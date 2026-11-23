import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faLock, faSpinner } from "@fortawesome/free-solid-svg-icons";
import { useAuth } from "../context/AuthContext";
import { authApi, profileApi, roleRequestsApi } from "../api/client";
import { ACADEMIC_LEVELS, academicLevelLabel } from "../lib/labels";
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  CardHeader,
  Container,
  Crumb,
  ErrorNotice,
  FieldLabel,
  Input,
  Meta,
  PageHeading,
  Select,
  Status,
} from "../components/ui";

/**
 * Account.
 *
 * The details a person owns are editable here. Identity is not: the email
 * address comes from Google, the role is granted by an administrator, and
 * a roll number carried by the campus address was issued by the campus.
 * Those are shown as facts, and the server rejects changes to them rather
 * than relying on the form to withhold them.
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
      "You can search the catalogue and read project abstracts. Access to a full report can be requested from the department.",
  };
}

const REQUESTED_ROLE_LABEL = { admin: "Administrator", faculty: "Faculty" };

export default function AccountSettings() {
  const { user, applyUser } = useAuth();
  const profile = user?.profile || null;
  // Choosing faculty or administrator during onboarding files a request
  // rather than granting anything, so the applicant is told where that
  // request stands instead of being left wondering why nothing changed.
  const [roleRequest, setRoleRequest] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    authApi
      .getDepartments()
      .then((body) => setDepartments(body?.data || body || []))
      .catch(() => setDepartments([]));
  }, []);

  function startEditing() {
    setDraft({
      full_name: profile?.full_name || "",
      department_id: profile?.department_id || "",
      academic_level: profile?.academic_level || "UG",
      roll_number: profile?.roll_number || "",
      title: profile?.title || "",
      designation: profile?.designation || "",
    });
    setSaveError(null);
    setSaved(false);
    setEditing(true);
  }

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      const payload = {
        full_name: draft.full_name,
        department_id: draft.department_id || null,
      };
      if (profile?.kind === "student") {
        payload.academic_level = draft.academic_level;
        // Only sent when the address does not already prove one; the
        // server ignores it otherwise, but there is no reason to send it.
        if (!profile.roll_number_locked) payload.roll_number = draft.roll_number;
      }
      if (profile?.kind === "faculty") {
        payload.title = draft.title;
        payload.designation = draft.designation;
      }
      const body = await profileApi.update(payload);
      applyUser(body.data);
      setEditing(false);
      setSaved(true);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

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
        <PageHeading title="Account" />

        <div className="mt-7 grid grid-cols-1 gap-6 md:grid-cols-2 items-start">
          <Card>
            <CardHeader title="Sign-in account" />
            <dl className="divide-y divide-line px-4">
              <Meta label="Email address">{user?.email || "—"}</Meta>
              <Meta label="Name">{accountName || "Not provided"}</Meta>
            </dl>
          </Card>

          <Card>
            <CardHeader
              title="Repository profile"
              action={
                profile && !editing ? (
                  <Button variant="secondary" size="sm" onClick={startEditing}>
                    Edit
                  </Button>
                ) : null
              }
            />
            {!profile ? (
              <p className="px-4 py-5 text-sm text-ink-2">
                No repository profile is linked to this account yet.
              </p>
            ) : editing ? (
              <form onSubmit={save} className="flex flex-col gap-4 px-4 py-4">
                {saveError && <ErrorNotice title="Could not save" detail={saveError} />}

                <div>
                  <FieldLabel htmlFor="profile-name">Full name</FieldLabel>
                  <Input
                    id="profile-name"
                    value={draft.full_name}
                    onChange={(e) => setDraft({ ...draft, full_name: e.target.value })}
                    required
                  />
                </div>

                <div>
                  <FieldLabel htmlFor="profile-department">Department</FieldLabel>
                  <Select
                    id="profile-department"
                    value={draft.department_id || ""}
                    onChange={(e) => setDraft({ ...draft, department_id: e.target.value })}
                  >
                    <option value="">Not recorded</option>
                    {departments.map((dept) => (
                      <option key={dept.id} value={dept.id}>
                        {dept.name}
                      </option>
                    ))}
                  </Select>
                </div>

                {profile.kind === "student" && (
                  <>
                    <div>
                      <FieldLabel htmlFor="profile-level">Academic level</FieldLabel>
                      <Select
                        id="profile-level"
                        value={draft.academic_level}
                        onChange={(e) => setDraft({ ...draft, academic_level: e.target.value })}
                      >
                        {ACADEMIC_LEVELS.map((level) => (
                          <option key={level.value} value={level.value}>
                            {level.label}
                          </option>
                        ))}
                      </Select>
                    </div>

                    <div>
                      <FieldLabel htmlFor="profile-roll">Roll number</FieldLabel>
                      {profile.roll_number_locked ? (
                        <p className="flex items-center gap-2 rounded-sm border border-line bg-band px-3 py-2 text-sm text-ink-2">
                          <FontAwesomeIcon icon={faLock} className="h-3 w-3 shrink-0" aria-hidden="true" />
                          <span className="tnum">{profile.roll_number}</span>
                          <span className="text-ink-3">issued with your campus address</span>
                        </p>
                      ) : (
                        <Input
                          id="profile-roll"
                          className="tnum"
                          value={draft.roll_number}
                          onChange={(e) => setDraft({ ...draft, roll_number: e.target.value.toUpperCase() })}
                        />
                      )}
                    </div>
                  </>
                )}

                {profile.kind === "faculty" && (
                  <>
                    <div>
                      <FieldLabel htmlFor="profile-title">Title</FieldLabel>
                      <Input
                        id="profile-title"
                        value={draft.title}
                        onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                        placeholder="e.g. Dr."
                      />
                    </div>
                    <div>
                      <FieldLabel htmlFor="profile-designation">Designation</FieldLabel>
                      <Input
                        id="profile-designation"
                        value={draft.designation}
                        onChange={(e) => setDraft({ ...draft, designation: e.target.value })}
                        placeholder="e.g. Assistant Professor"
                      />
                    </div>
                  </>
                )}

                <div className="flex gap-2">
                  <Button type="submit" variant="primary" size="sm" disabled={saving}>
                    {saving && (
                      <FontAwesomeIcon icon={faSpinner} className="h-3.5 w-3.5 spin" aria-hidden="true" />
                    )}
                    Save changes
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setEditing(false)}
                    disabled={saving}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <>
                {saved && (
                  <p className="mx-4 mt-4 rounded-sm border border-ok/40 bg-ok/10 px-3 py-2 text-sm text-ink">
                    Profile updated.
                  </p>
                )}
                <dl className="divide-y divide-line px-4">
                  <Meta label="Full name">{profile.full_name || "—"}</Meta>
                  <Meta label="Department">{profile.department || "Not recorded"}</Meta>

                  {profile.kind === "student" && (
                    <>
                      <Meta label="Roll number">
                        <span className="tnum">{profile.roll_number || "Not recorded"}</span>
                      </Meta>
                      <Meta label="Academic level">{academicLevelLabel(profile.academic_level)}</Meta>
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
              </>
            )}
          </Card>

          <Card>
            <CardHeader title="Access" />
            <div className="px-4 py-4">
              <Status tone={access.tone}>{access.title}</Status>
              <p className="mt-2.5 text-sm text-ink-2">{access.detail}</p>

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
              <Button as={Link} to="/notifications" variant="secondary" size="sm">
                View notifications
              </Button>
            </div>
          </Card>
        </div>

      </Container>
    </>
  );
}
