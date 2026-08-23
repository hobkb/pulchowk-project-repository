import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCloudArrowUp, faFilePdf, faSpinner } from "@fortawesome/free-solid-svg-icons";
import { ingestionApi } from "../api/client";
import { Link } from "react-router-dom";
import {
  Breadcrumb,
  Button,
  Card,
  CardHeader,
  Container,
  Crumb,
  ErrorNotice,
  PageHeading,
  SectionHeading,
  Status,
} from "../components/ui";

/**
 * Deposit — hands a project report PDF to the ingestion pipeline.
 *
 * The upload behaviour is unchanged (validate as PDF, POST as multipart,
 * follow the created job into the review workflow). The drop target is
 * now a plainly-ruled area rather than a dashed card with a circular
 * icon badge, and it is properly operable from the keyboard: the file
 * input is a real labelled control rather than a transparent overlay
 * that a keyboard user could never reach.
 */

const ACCEPTED = ".pdf,application/pdf";

function isPdf(candidate) {
  return (
    candidate.type === "application/pdf" || candidate.name.toLowerCase().endsWith(".pdf")
  );
}

// The real stages of a deposit. `phase` is driven entirely by the async
// request, so the loader can never be shown when nothing is happening and
// can never stay behind once the request settles.
const IDLE = "idle";
const UPLOADING = "uploading";
const PROCESSING = "processing";
const DONE = "done";

export default function AdminUpload() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [phase, setPhase] = useState(IDLE);
  const [error, setError] = useState(null);
  // Real bytes-sent percentage from the browser's upload progress events.
  const [percent, setPercent] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  const busy = phase === UPLOADING || phase === PROCESSING || phase === DONE;

  function accept(candidate) {
    if (!candidate) return;
    if (!isPdf(candidate)) {
      setError("Only PDF files can be deposited. The pipeline reads the report's own layout, which requires the original PDF.");
      setFile(null);
      return;
    }
    setError(null);
    setFile(candidate);
  }

  function clearSelection() {
    setFile(null);
    setError(null);
    // Reset the input too, or re-picking the same file fires no change
    // event and the selection appears to be ignored.
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    // A second submit while one is in flight would create a duplicate job.
    if (busy) return;
    if (!file) {
      setError("Choose a project report PDF to deposit.");
      return;
    }

    setPhase(UPLOADING);
    setPercent(0);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await ingestionApi.uploadJob(formData, {
        onProgress: setPercent,
      });

      // The upload itself has finished; the server now queues extraction.
      setPhase(PROCESSING);
      const jobId = res?.data?.id;
      if (!jobId) throw new Error("The server accepted the file but returned no job reference.");

      setPhase(DONE);
      // Stay in the DONE state through the navigation so the button cannot
      // be pressed again during the transition.
      navigate(`/admin/jobs/${jobId}`, { replace: true });
    } catch (err) {
      setError(err.message || "The report could not be deposited.");
      setPhase(IDLE);
      setPercent(0);
    }
  }

  return (
    <>
      <Breadcrumb>
        <Crumb>
          <Link to="/dashboard">Home</Link>
        </Crumb>
        <Crumb>Administration</Crumb>
        <Crumb last>Deposit report</Crumb>
      </Breadcrumb>

      <Container width="reading" className="px-5 sm:px-8 py-8">
      <PageHeading
        title="Deposit a report"
        lead="Hand a project report to the extraction pipeline. It reads the front matter, people and section structure, then returns it to you for verification before anything is published."
      />

      <form onSubmit={handleSubmit} className="mt-7 flex flex-col gap-6">
        <div>
          <label htmlFor="report-file" className="block text-xs font-semibold text-ink-2">
            Project report (PDF)
          </label>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setIsDragging(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              accept(event.dataTransfer.files?.[0]);
            }}
            className={`mt-2 flex flex-col items-center gap-4 rounded-md border px-6 py-10 text-center transition-colors ${
              isDragging
                ? "border-primary bg-primary-050"
                : file
                  ? "border-ok bg-ok-bg"
                  : "border-dashed border-line-strong bg-band"
            }`}
          >
            <FontAwesomeIcon
              icon={file ? faFilePdf : faCloudArrowUp}
              className={`h-6 w-6 ${file ? "text-ok" : "text-ink-3"}`}
              aria-hidden="true"
            />

            {file ? (
              <div className="flex flex-col items-center gap-2">
                <p className="text-item break-all">{file.name}</p>
                <p className="text-sm text-ink-3 tnum">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB · PDF
                </p>
                <Status tone="ok">Ready to deposit</Status>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-1.5">
                <p className="text-item">Drop the report here, or choose a file</p>
                <p className="text-sm text-ink-2">
                  Undergraduate, master&rsquo;s and doctoral project reports, as originally submitted.
                </p>
              </div>
            )}

            <input
              ref={inputRef}
              id="report-file"
              name="report-file"
              type="file"
              accept={ACCEPTED}
              disabled={busy}
              onChange={(event) => accept(event.target.files?.[0])}
              className="cursor-pointer text-sm text-ink-2 file:mr-3 file:cursor-pointer file:rounded-sm file:border file:border-line-strong file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-ink hover:file:bg-band disabled:cursor-not-allowed"
            />
          </div>
        </div>

        {error && <ErrorNotice title="The report could not be uploaded" detail={error} />}

        {busy && (
          <div className="flex flex-col gap-2" role="status" aria-live="polite">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-ink-2">
                {phase === UPLOADING
                  ? "Uploading the report…"
                  : phase === PROCESSING
                    ? "Queued for extraction. Taking you to the review screen…"
                    : "Opening the review screen…"}
              </p>
              {phase === UPLOADING && (
                <span className="text-sm text-ink-2 tnum">{percent}%</span>
              )}
            </div>

            {/* While bytes are moving this is a real determinate bar driven
                by the browser's upload events. Once the server has the file
                there is no progress information to report, so it becomes an
                indeterminate sweep rather than a fabricated percentage. */}
            <div
              className="h-1.5 w-full overflow-hidden rounded-sm bg-band"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={phase === UPLOADING ? percent : undefined}
            >
              {phase === UPLOADING ? (
                <div
                  className="h-full bg-primary transition-[width] duration-150 ease-out"
                  style={{ width: `${percent}%` }}
                />
              ) : (
                <div className="indeterminate-bar h-full w-1/3 bg-primary" />
              )}
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
          <Button
            type="button"
            variant="subtle"
            onClick={clearSelection}
            disabled={!file || busy}
          >
            Clear selection
          </Button>

          <Button type="submit" variant="primary" size="lg" disabled={!file || busy}>
            {busy ? (
              <>
                <FontAwesomeIcon
                  icon={faSpinner}
                  className="h-3.5 w-3.5 animate-spin"
                  aria-hidden="true"
                />
                {phase === UPLOADING
                  ? "Uploading…"
                  : phase === PROCESSING
                    ? "Processing…"
                    : "Opening review…"}
              </>
            ) : (
              <>
                <FontAwesomeIcon icon={faCloudArrowUp} className="h-4 w-4" aria-hidden="true" />
                Upload project
              </>
            )}
          </Button>
        </div>
      </form>

      <section className="mt-10">
        <SectionHeading title="What happens next" />
        <ol className="divide-y divide-line border-t border-line">
          {[
            ["Extraction", "The pipeline reads the PDF's layout: front matter, authors and roll numbers, supervisors, and the full nested section structure."],
            ["Verification", "You review what was extracted, correct anything the document made ambiguous, and reorder or edit sections as needed."],
            ["Publication", "On approval the record joins the public catalogue, and the depositor receives a notice."],
          ].map(([title, body], index) => (
            <li key={title} className="flex gap-4 py-4">
              <span className="shrink-0 text-sm font-semibold text-accent tnum">{index + 1}.</span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{title}</p>
                <p className="mt-0.5 text-sm text-ink-2 measure">{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      </Container>
    </>
  );
}
