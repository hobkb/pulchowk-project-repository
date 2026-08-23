import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faArrowUpRightFromSquare,
  faBookmark as faBookmarkSolid,
  faCheck,
  faLockOpen,
  faLink,
  faSpinner,
  faTrash,
  faPenToSquare,
} from "@fortawesome/free-solid-svg-icons";
import { faBookmark as faBookmarkOutline } from "@fortawesome/free-regular-svg-icons";
import { accessRequestsApi, bookmarksApi, projectAdminApi, projectsApi } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { isAdminUser } from "../lib/nav";
import { RestrictedReport } from "../components/RestrictedReport";
import { academicLevelLabel, batchLabel } from "../lib/labels";
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  CardHeader,
  Container,
  Crumb,
  Dialog,
  ErrorNotice,
  Meta,
  SectionHeading,
  Status,
  Term,
  Textarea,
  Input,
  Select,
} from "../components/ui";

/**
 * A single project record.
 *
 * What a normal reader sees is the public catalogue record: title,
 * responsibility, classification, keywords and the abstract. The report's
 * own sections (Introduction, Methodology, Results, …) are confidential
 * and are neither rendered nor fetched — the API withholds them from
 * unprivileged callers, so this page could not display them even if it
 * tried. Reviewers additionally get the original PDF.
 */

/**
 * Asking the department for the full report.
 *
 * This replaced a `mailto:` link. An email could only ever start a
 * conversation; a request recorded here reaches every reviewer as a
 * notification, and an approval actually unlocks the PDF for the person
 * who asked — which is the thing they wanted.
 */
function ReportRequestDialog({ open, onClose, project, onSubmitted }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const body = await accessRequestsApi.request(project.id, reason);
      onSubmitted?.(body?.data?.status || "PENDING");
      onClose();
    } catch (err) {
      setError(err.message || "The request could not be sent.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Request the full report"
      description="Your request goes to the departmental administrators. You will be notified here as soon as it is decided."
      width="max-w-lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" form="access-request-form" variant="primary" disabled={submitting}>
            {submitting && (
              <FontAwesomeIcon icon={faSpinner} className="h-3.5 w-3.5 spin" aria-hidden="true" />
            )}
            {submitting ? "Sending…" : "Send request"}
          </Button>
        </>
      }
    >
      <form id="access-request-form" onSubmit={submit} className="flex flex-col gap-3">
        <Textarea
          id="access-reason"
          label="Why do you need this report? (optional)"
          rows={4}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="For example: background reading for a related final-year project."
          hint="A short reason helps the department decide faster."
        />
        {error && <ErrorNotice title="The request was not sent" detail={error} />}
      </form>
    </Dialog>
  );
}

/**
 * Reviewer-only editing of the catalogue record.
 *
 * Only the metadata a reviewer can reasonably correct after publication is
 * here. The extracted report body is deliberately not editable from this
 * page — correcting that belongs in the ingestion review workflow, where
 * the source PDF sits alongside it.
 */
function EditProjectDialog({ open, onClose, project, onSaved }) {
  const [form, setForm] = useState(null);
  const [choices, setChoices] = useState({ clusters: [], departments: [] });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setForm({
      title: project.title || "",
      abstract: project.abstract || "",
      academic_level: project.academic_level || "",
      project_type: project.project_type || "",
      batch: project.batch || "",
      cluster: project.cluster || "",
      department_name: project.department || "",
      keywords: (project.keywords || []).join(", "),
    });
    projectsApi
      .facets()
      .then((body) =>
        setChoices({
          clusters: body?.data?.cluster_choices || [],
          departments: body?.data?.department_choices || [],
        })
      )
      .catch(() => setChoices({ clusters: [], departments: [] }));
  }, [open, project]);

  async function save(event) {
    event.preventDefault();
    if (saving || !form) return;
    setSaving(true);
    setError(null);
    try {
      const body = await projectAdminApi.update(project.id, {
        ...form,
        keywords: form.keywords
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
      });
      onSaved?.(body.data);
      onClose();
    } catch (err) {
      setError(err.message || "The project could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  const set = (field) => (event) => setForm((f) => ({ ...f, [field]: event.target.value }));

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Edit project record"
      description="Changes apply to the public catalogue entry immediately."
      width="max-w-2xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="edit-project-form" variant="primary" disabled={saving}>
            {saving && (
              <FontAwesomeIcon icon={faSpinner} className="h-3.5 w-3.5 spin" aria-hidden="true" />
            )}
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </>
      }
    >
      {form && (
        <form id="edit-project-form" onSubmit={save} className="flex flex-col gap-4">
          <Input id="edit-title" label="Title" value={form.title} onChange={set("title")} required />
          <Textarea
            id="edit-abstract"
            label="Abstract"
            rows={6}
            value={form.abstract}
            onChange={set("abstract")}
          />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              id="edit-department"
              label="Department"
              value={form.department_name}
              onChange={set("department_name")}
            >
              <option value="">— None —</option>
              {choices.departments.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </Select>
            <Select id="edit-cluster" label="Cluster" value={form.cluster} onChange={set("cluster")}>
              <option value="">— None —</option>
              {choices.clusters.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </Select>
            <Select
              id="edit-level"
              label="Academic level"
              value={form.academic_level}
              onChange={set("academic_level")}
            >
              {["UG", "Masters", "PhD", "Faculty"].map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </Select>
            <Select
              id="edit-type"
              label="Project type"
              value={form.project_type}
              onChange={set("project_type")}
            >
              {["Major", "Minor", "Thesis", "Faculty Project", "Research"].map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </Select>
            <Input id="edit-batch" label="Batch" value={form.batch} onChange={set("batch")} />
          </div>
          <Input
            id="edit-keywords"
            label="Keywords"
            value={form.keywords}
            onChange={set("keywords")}
            hint="Comma separated."
          />
          {error && <ErrorNotice title="The project was not saved" detail={error} />}
        </form>
      )}
    </Dialog>
  );
}

/** Reviewer-only removal of a catalogue record. */
function DeleteProjectDialog({ open, onClose, project }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function remove() {
    if (deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await projectAdminApi.remove(project.id);
      navigate("/projects", { replace: true });
    } catch (err) {
      setError(err.message || "The project could not be deleted.");
      setDeleting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Delete this project?"
      description="It will be removed from the public catalogue."
      width="max-w-lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={remove} disabled={deleting}>
            {deleting && (
              <FontAwesomeIcon icon={faSpinner} className="h-3.5 w-3.5 spin" aria-hidden="true" />
            )}
            {deleting ? "Deleting…" : "Delete project"}
          </Button>
        </>
      }
    >
      <p className="text-sm text-ink">
        <span className="font-semibold">{project.title}</span> and its sections, keywords and
        access requests will be removed.
      </p>
      <p className="mt-3 text-sm text-ink-2">
        The original deposit and its PDF are kept, so this record can be published again from
        the ingestion queue if this was a mistake.
      </p>
      {error && <ErrorNotice title="The project was not deleted" detail={error} className="mt-4" />}
    </Dialog>
  );
}

export default function ProjectDetails() {
  const { id } = useParams();
  const { user, status: authStatus } = useAuth();
  const isReviewer = isAdminUser(user);
  const signedIn = authStatus === "authenticated";

  const [project, setProject] = useState(null);
  const [related, setRelated] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);
  const [rechecking, setRechecking] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [justGranted, setJustGranted] = useState(false);
  const [savePending, setSavePending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setProject(null);

    projectsApi
      .detail(id)
      .then((body) => {
        if (cancelled) return;
        const found = body.data;
        setProject(found);
        return projectsApi
          .list({ department: found.department, page_size: 5 })
          .then((listBody) => {
            if (cancelled) return;
            setRelated((listBody.data || []).filter((p) => p.id !== found.id).slice(0, 4));
          })
          .catch(() => {
            if (!cancelled) setRelated([]);
          });
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (!signedIn) return undefined;
    let cancelled = false;
    bookmarksApi
      .status(id)
      .then((body) => {
        if (!cancelled) setSaved(Boolean(body?.data?.bookmarked));
      })
      .catch(() => {
        if (!cancelled) setSaved(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, signedIn]);

  async function toggleSaved() {
    setSavePending(true);
    const next = !saved;
    setSaved(next);
    try {
      if (next) await bookmarksApi.add(id);
      else await bookmarksApi.remove(id);
    } catch {
      setSaved(!next);
    } finally {
      setSavePending(false);
    }
  }

  /** Re-reads the record so a decision made while this page was open is
   *  picked up without the reader having to reload the browser. */
  async function recheckAccess() {
    if (rechecking) return;
    setRechecking(true);
    try {
      const body = await projectsApi.detail(id);
      const wasGranted = body.data?.accessStatus === "granted";
      setProject(body.data);
      setJustGranted(wasGranted);
    } catch {
      // Leave the page as it is; the reader can try again.
    } finally {
      setRechecking(false);
    }
  }

  /** Withdraw a request that has not been decided yet. */
  async function cancelRequest() {
    if (cancelling) return;
    setCancelling(true);
    try {
      await accessRequestsApi.cancel(id);
      setProject((current) => (current ? { ...current, accessStatus: "none" } : current));
    } catch (err) {
      setActionError(err.message);
    } finally {
      setCancelling(false);
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  if (loading) {
    return (
      <Container width="wide" className="px-5 sm:px-8 py-10">
        <div className="skeleton h-8 w-3/4 rounded-sm" />
        <div className="skeleton mt-3 h-4 w-1/2 rounded-sm" />
        <div className="skeleton mt-8 h-40 rounded-md" />
      </Container>
    );
  }

  if (error || !project) {
    return (
      <Container width="reading" className="px-5 sm:px-8 py-10">
        <ErrorNotice
          title="This project could not be opened"
          detail={error || "No record was returned for this identifier."}
          action={
            <Button as={Link} to="/projects" variant="secondary" size="sm">
              Back to projects
            </Button>
          }
        />
      </Container>
    );
  }

  const authors = project.authors || [];
  const supervisors = (project.supervisors || []).filter(Boolean);
  const keywords = (project.keywords || project.technologies || []).filter(Boolean);
  // "granted" for a reviewer or an approved requester; otherwise the
  // state of this reader's own request.
  const accessStatus = project.accessStatus || "none";
  const hasReport = Boolean(project.pdfUrl);

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb>
          <Link to="/projects">Projects</Link>
        </Crumb>
        <Crumb last>{project.title}</Crumb>
      </Breadcrumb>

      <Container width="wide" className="px-5 sm:px-8 py-8">
        {justGranted && (
          <Alert tone="ok" title="Access approved" className="mb-6">
            Your request was approved — the full report is now available below.
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-x-12 gap-y-8 lg:grid-cols-[minmax(0,1fr)_18rem] items-start">
          <div className="min-w-0">
            <h1 className="text-hero">{project.title}</h1>

            <div className="mt-3 space-y-1">
              {authors.length > 0 && (
                <p className="text-base text-ink-2">
                  <span className="text-ink-3">Authors: </span>
                  {authors.map((author, index) => (
                    <span key={`${author.name}-${index}`}>
                      <span className="text-ink">{author.name}</span>
                      {author.rollNumber && (
                        <span className="text-ink-3 tnum"> ({author.rollNumber})</span>
                      )}
                      {index < authors.length - 1 ? "; " : ""}
                    </span>
                  ))}
                </p>
              )}
              <p className="text-base text-ink-2">
                <span className="text-ink-3">
                  {supervisors.length > 1 ? "Supervisors: " : "Supervisor: "}
                </span>
                {supervisors.length > 0 ? (
                  <span className="text-ink">{supervisors.join("; ")}</span>
                ) : (
                  <span className="italic text-ink-3">Not available</span>
                )}
              </p>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {accessStatus === "granted" && hasReport ? (
                <Button
                  as="a"
                  href={project.pdfUrl}
                  target="_blank"
                  rel="noreferrer"
                  variant="primary"
                  size="sm"
                >
                  <FontAwesomeIcon
                    icon={faArrowUpRightFromSquare}
                    className="h-3.5 w-3.5"
                    aria-hidden="true"
                  />
                  Open full report
                </Button>
              ) : accessStatus === "pending" ? (
                <>
                  <Status tone="warn">Access requested — awaiting a decision</Status>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={recheckAccess}
                    disabled={rechecking}
                  >
                    {rechecking && (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        className="h-3.5 w-3.5 spin"
                        aria-hidden="true"
                      />
                    )}
                    {rechecking ? "Checking…" : "Check for a decision"}
                  </Button>
                  <Button
                    variant="subtle"
                    size="sm"
                    onClick={cancelRequest}
                    disabled={cancelling}
                    title={actionError || undefined}
                  >
                    {cancelling && (
                      <FontAwesomeIcon
                        icon={faSpinner}
                        className="h-3.5 w-3.5 spin"
                        aria-hidden="true"
                      />
                    )}
                    Cancel request
                  </Button>
                </>
              ) : (
                <Button variant="primary" size="sm" onClick={() => setRequestOpen(true)}>
                  <FontAwesomeIcon icon={faLockOpen} className="h-3.5 w-3.5" aria-hidden="true" />
                  {accessStatus === "declined" ? "Request again" : "Request report"}
                </Button>
              )}

              {isReviewer && (
                <>
                  <Button variant="secondary" size="sm" onClick={() => setManageOpen(true)}>
                    <FontAwesomeIcon icon={faPenToSquare} className="h-3.5 w-3.5" aria-hidden="true" />
                    Edit
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
                    <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" aria-hidden="true" />
                    Delete
                  </Button>
                </>
              )}
              {signedIn && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={toggleSaved}
                  disabled={savePending}
                  aria-pressed={saved}
                >
                  <FontAwesomeIcon
                    icon={saved ? faBookmarkSolid : faBookmarkOutline}
                    className="h-3.5 w-3.5"
                    aria-hidden="true"
                  />
                  {saved ? "Saved" : "Save"}
                </Button>
              )}
              <Button variant="secondary" size="sm" onClick={copyLink}>
                <FontAwesomeIcon
                  icon={copied ? faCheck : faLink}
                  className="h-3.5 w-3.5"
                  aria-hidden="true"
                />
                {copied ? "Link copied" : "Copy link"}
              </Button>
            </div>

            {project.abstract && (
              <section className="mt-9">
                <SectionHeading title="Abstract" />
                <p className="whitespace-pre-line text-base text-ink measure">{project.abstract}</p>
              </section>
            )}

            <section className="mt-9">
              <SectionHeading title="Full report" />
              {accessStatus === "granted" && hasReport ? (
                <Card className="overflow-hidden">
                  <CardHeader
                    title="Original report (PDF)"
                    actions={
                      <>
                        <Status tone="ok">
                          {isReviewer ? "Reviewer access" : "Access granted"}
                        </Status>
                        <Button
                          as="a"
                          href={project.pdfUrl}
                          target="_blank"
                          rel="noreferrer"
                          variant="secondary"
                          size="sm"
                        >
                          <FontAwesomeIcon
                            icon={faArrowUpRightFromSquare}
                            className="h-3 w-3"
                            aria-hidden="true"
                          />
                          Open
                        </Button>
                      </>
                    }
                  />
                  <iframe
                    src={`${project.pdfUrl}#toolbar=1`}
                    title={`Report: ${project.title}`}
                    className="h-[70vh] min-h-[420px] w-full border-0 bg-band"
                  />
                </Card>
              ) : (
                <RestrictedReport
                  onRequest={() => setRequestOpen(true)}
                  canRequest={accessStatus !== "pending"}
                  status={accessStatus}
                />
              )}
            </section>

            {related.length > 0 && (
              <section className="mt-9">
                <SectionHeading
                  title="Other projects from this department"
                  actions={
                    <Link to={`/projects?department=${encodeURIComponent(project.department)}`}>
                      View all
                    </Link>
                  }
                />
                {/* Cards rather than a bare list: at a glance a reader is
                    deciding whether a neighbouring project is worth
                    opening, and a title alone does not answer that. The
                    first line of the abstract and the supervisor do. */}
                <ul className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {related.map((item) => {
                    // Already formatted by the serializer as
                    // "Asst. Prof. Dr. Ram Shrestha" -- rank included.
                    const supervisor = (item.supervisors || [])[0];
                    return (
                      <li key={item.id}>
                        <Link
                          to={`/projects/${item.id}`}
                          className="group flex h-full flex-col rounded-sm border border-line bg-white p-4 no-underline transition-colors hover:border-line-strong hover:bg-band"
                        >
                          <div className="flex flex-wrap items-center gap-1.5">
                            {item.academic_level && (
                              <Status tone="neutral">
                                {academicLevelLabel(item.academic_level)}
                              </Status>
                            )}
                            {item.batch && (
                              <span className="text-xs text-ink-3 tnum">
                                Batch {batchLabel(item.batch)}
                              </span>
                            )}
                            {item.cluster && (
                              <span className="text-xs text-ink-3">{item.cluster}</span>
                            )}
                          </div>

                          <p className="mt-2 text-sm font-semibold text-ink group-hover:text-primary">
                            {item.title}
                          </p>

                          {item.abstract && (
                            <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-ink-2">
                              {item.abstract}
                            </p>
                          )}

                          {supervisor && (
                            <p className="mt-auto pt-3 text-xs text-ink-3">{supervisor}</p>
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}
          </div>

          {/* Catalogue details — a plain definition list in the margin. */}
          <aside className="min-w-0">
            <Card>
              <CardHeader title="Project details" />
              <dl className="divide-y divide-line px-4">
                {project.department && <Meta label="Department">{project.department}</Meta>}
                {project.academic_level && (
                  <Meta label="Academic level">
                    {academicLevelLabel(project.academic_level)}
                  </Meta>
                )}
                {project.project_type && <Meta label="Project type">{project.project_type}</Meta>}
                {(project.batch || project.year) && (
                  <Meta label="Batch">
                    <span className="tnum">{project.batch || project.year}</span>
                  </Meta>
                )}
                {project.cluster && <Meta label="Research area">{project.cluster}</Meta>}
                {project.language && <Meta label="Language">{project.language}</Meta>}
                <Meta label="Record status">
                  <Status tone="ok">Verified</Status>
                </Meta>
              </dl>
            </Card>

            {keywords.length > 0 && (
              <div className="mt-5">
                <h2 className="mb-2 text-sm font-semibold text-ink">Keywords</h2>
                <div className="flex flex-wrap gap-1.5">
                  {keywords.map((keyword) => (
                    <Term
                      key={keyword}
                      as={Link}
                      to={`/projects?q=${encodeURIComponent(keyword)}`}
                      className="no-underline hover:no-underline"
                    >
                      {keyword}
                    </Term>
                  ))}
                </div>
              </div>
            )}

            <Alert tone="neutral" className="mt-5">
              Project reports are held confidentially by the department. Only the catalogue
              record and abstract are published.
            </Alert>
          </aside>
        </div>
      </Container>

      <ReportRequestDialog
        open={requestOpen}
        onClose={() => setRequestOpen(false)}
        project={project}
        onSubmitted={(status) =>
          setProject((current) =>
            current
              ? { ...current, accessStatus: status === "APPROVED" ? "granted" : "pending" }
              : current
          )
        }
      />

      {isReviewer && (
        <>
          <EditProjectDialog
            open={manageOpen}
            onClose={() => setManageOpen(false)}
            project={project}
            onSaved={(updated) => setProject(updated)}
          />
          <DeleteProjectDialog
            open={deleteOpen}
            onClose={() => setDeleteOpen(false)}
            project={project}
          />
        </>
      )}
    </>
  );
}
