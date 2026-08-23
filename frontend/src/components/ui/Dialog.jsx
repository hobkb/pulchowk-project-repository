import { useCallback, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faXmark } from "@fortawesome/free-solid-svg-icons";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), ' +
  'select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * The dialog primitive. Rendered through a portal so it never inherits an
 * ancestor's stacking or overflow context, and it does the accessibility
 * work a hand-rolled `fixed inset-0` overlay does not: real dialog
 * semantics, a labelled title, Escape to dismiss, focus moved in on open
 * and restored to the trigger on close, and Tab cycling trapped inside
 * the panel.
 *
 * Visually it obeys the same house rules as everything else: a small
 * radius, a 1px border, a light header band and sentence-case text. On
 * small screens it anchors to the bottom of the viewport (where a thumb
 * is) and fills the width, rather than being a shrunken desktop box.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  footer,
  children,
  width = "max-w-xl",
  // A mandatory gate (onboarding) must not be dismissible: no close
  // button, no Escape, no backdrop click. It still gets full dialog
  // semantics and the focus trap, which is the part that matters.
  dismissible = true,
}) {
  const panelRef = useRef(null);
  const triggerRef = useRef(null);
  const titleId = useId();
  const descId = useId();

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === "Escape") {
        if (!dismissible) return;
        event.stopPropagation();
        onClose?.();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (!panel) return;
      const items = Array.from(panel.querySelectorAll(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose, dismissible]
  );

  // Focus and scroll-lock run ONCE per open, keyed on `open` alone.
  //
  // These used to share an effect with the keydown listener, which depends
  // on `handleKeyDown` -- and that changes identity on every render because
  // callers pass an inline arrow for `onClose`. So the effect tore down and
  // re-ran on every keystroke: it re-focused the first focusable element
  // (the close button, which comes first in the DOM) after each character,
  // making it impossible to type more than one letter into a field. The
  // cleanup's focus-restore compounded it by then treating the close button
  // as the element to return to.
  useEffect(() => {
    if (!open) return undefined;

    triggerRef.current = document.activeElement;
    const panel = panelRef.current;
    // Prefer the first control in the dialog BODY over the header's close
    // button, so opening a form dialog puts the caret where typing starts.
    const body = panel?.querySelector("[data-dialog-body]");
    const firstFocusable =
      body?.querySelector(FOCUSABLE) || panel?.querySelector(FOCUSABLE);
    (firstFocusable || panel)?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
      // Returning focus to whatever opened the dialog is what lets a
      // keyboard user carry on from where they were instead of being
      // dropped back at the top of the document.
      triggerRef.current?.focus?.();
    };
  }, [open]);

  // The key handler is registered separately: re-attaching a listener when
  // its identity changes is harmless, unlike re-running the focus logic.
  useEffect(() => {
    if (!open) return undefined;
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [open, handleKeyDown]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4">
      <div
        className="absolute inset-0 bg-ink/40 pop-in"
        onClick={dismissible ? onClose : undefined}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={`relative w-full ${width} max-h-[92vh] sm:max-h-[88vh] flex flex-col
          bg-white border border-line-strong rounded-t-md sm:rounded-md shadow-pop pop-in`}
      >
        {title && (
          <div className="flex items-start justify-between gap-4 px-5 py-3.5 border-b border-line bg-band rounded-t-md shrink-0">
            <div className="min-w-0">
              <h2 id={titleId} className="text-section">
                {title}
              </h2>
              {description && (
                <p id={descId} className="text-sm text-ink-2 mt-1">
                  {description}
                </p>
              )}
            </div>
            {dismissible && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close dialog"
                className="shrink-0 -mt-1 -mr-1.5 p-2 text-ink-3 hover:text-ink hover:bg-white rounded-sm transition-colors cursor-pointer"
              >
                <FontAwesomeIcon icon={faXmark} className="h-4 w-4" />
              </button>
            )}
          </div>
        )}

        <div data-dialog-body className="overflow-y-auto px-5 py-4 min-h-0">
          {children}
        </div>

        {footer && (
          <div className="border-t border-line bg-band px-5 py-3 rounded-b-md flex flex-col-reverse sm:flex-row sm:justify-end gap-2 shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
