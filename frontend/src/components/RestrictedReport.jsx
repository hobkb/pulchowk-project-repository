import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faLock, faLockOpen } from "@fortawesome/free-solid-svg-icons";
import { Button, Card, Status } from "./ui";

/**
 * The locked report preview.
 *
 * IMPORTANT: the blurred page behind the lock is a drawn placeholder —
 * plain grey bars standing in for lines of text. No extracted report
 * content is rendered here, blurred or otherwise, so nothing can be
 * recovered by removing the CSS filter, selecting the text, or reading
 * the DOM. The API does not send the report body to unprivileged users
 * either (see ProjectDetailSerializer), so there is nothing to leak.
 */

/** Decorative page of "text" — bars, not words. */
function PlaceholderPage() {
  const lines = [
    96, 88, 92, 70, 0, 84, 94, 78, 90, 60, 0, 92, 86, 74,
  ];
  return (
    <div className="redacted select-none space-y-2 bg-white p-6" aria-hidden="true">
      <div className="mx-auto mb-4 h-3 w-1/2 rounded-sm bg-ink-3/50" />
      {lines.map((width, index) =>
        width === 0 ? (
          <div key={index} className="h-2" />
        ) : (
          <div
            key={index}
            className="h-2 rounded-sm bg-ink-3/30"
            style={{ width: `${width}%` }}
          />
        )
      )}
    </div>
  );
}

export function RestrictedReport({ onRequest, canRequest, status = "none" }) {
  const pending = status === "pending";
  const declined = status === "declined";
  return (
    <Card className="overflow-hidden">
      <div className="relative">
        <div className="max-h-64 overflow-hidden border-b border-line">
          <PlaceholderPage />
        </div>

        {/* The lock sits over the placeholder, stating the rule plainly. */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-white/70 px-6 text-center">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-line-strong bg-white text-ink-2">
            <FontAwesomeIcon icon={faLock} className="h-4 w-4" aria-hidden="true" />
          </span>
          <p className="text-item text-ink">Full report — restricted access</p>
          <p className="max-w-sm text-sm text-ink-2">
            {pending
              ? "You will get a notification when this is decided."
              : declined
                ? "Your previous request was declined. You can ask again with more detail."
                : "The complete project report is confidential and is not published in the repository."}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 bg-band px-4 py-3">
        <p className="text-sm text-ink-2">
          {pending ? "Awaiting a decision." : "Access is granted by the department."}
        </p>
        {pending ? (
          <Status tone="warn">Request pending</Status>
        ) : (
          <Button variant="primary" size="sm" onClick={onRequest} disabled={!canRequest}>
            <FontAwesomeIcon icon={faLockOpen} className="h-3.5 w-3.5" aria-hidden="true" />
            {declined ? "Request again" : "Request access"}
          </Button>
        )}
      </div>
    </Card>
  );
}
