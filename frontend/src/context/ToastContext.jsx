import { createContext, useCallback, useContext, useRef, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
import { TONE } from "../components/ui/primitives";

/**
 * Brief confirmation messages ("Project updated.") that appear once and
 * clear themselves -- distinct from the Notifications bell, which is a
 * standing record of things that happened while the reader was elsewhere.
 * A toast is only ever a reaction to something the reader just did.
 */

const ToastContext = createContext(null);
const DEFAULT_DURATION_MS = 3500;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message, { tone = "ok", duration = DEFAULT_DURATION_MS } = {}) => {
      const id = ++nextId.current;
      setToasts((current) => [...current, { id, message, tone }]);
      if (duration) {
        setTimeout(() => dismiss(id), duration);
      }
      return id;
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ showToast, dismiss }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-5 z-[70] flex flex-col items-center gap-2 px-4"
      >
        {toasts.map((t) => {
          const tone = TONE[t.tone];
          return (
            <div
              key={t.id}
              role="status"
              className={`pop-in pointer-events-auto flex max-w-md items-center gap-3 rounded-md px-4 py-2.5 text-sm font-medium shadow-lg ${tone.solid}`}
            >
              <span className="min-w-0">{t.message}</span>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                className="shrink-0 cursor-pointer rounded-sm p-0.5 text-white/80 hover:text-white"
              >
                <FontAwesomeIcon icon={faXmark} className="h-3 w-3" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used inside a ToastProvider");
  }
  return ctx;
}
