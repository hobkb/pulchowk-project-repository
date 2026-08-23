/**
 * The Pulchowk repository component vocabulary.
 *
 * Every primitive follows the same house rules (see index.css): one font
 * family, sentence case, 3–4px radii, 1px borders instead of shadows, and
 * primary for action / accent for identity. Nothing here uses uppercase
 * transforms, letter-spaced micro-labels, gradients, or pills.
 */

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faCircleCheck,
  faCircleExclamation,
  faCircleInfo,
  faTriangleExclamation,
} from "@fortawesome/free-solid-svg-icons";

/* ------------------------------------------------------------------ *
 * Buttons
 * ------------------------------------------------------------------ */

const BTN_BASE =
  "inline-flex items-center justify-center gap-2 rounded-sm border font-semibold " +
  "transition-colors duration-150 cursor-pointer whitespace-nowrap align-middle " +
  "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none";

const BTN_VARIANTS = {
  /** The one main action on a view. Solid primary. */
  primary: "bg-primary border-primary text-white hover:bg-primary-600 hover:border-primary-600 active:bg-primary-700",
  /** The default button. Outlined, ink on white — most buttons are this. */
  secondary: "bg-white border-line-strong text-ink hover:bg-band hover:border-ink-3",
  /** A tertiary action with no chrome until hovered. */
  subtle: "bg-transparent border-transparent text-link hover:bg-band hover:text-link-hover",
  /** Destructive. Outlined, never a solid red block. */
  danger: "bg-white border-err text-err hover:bg-err-050",
};

const BTN_SIZES = {
  sm: "text-xs px-2.5 py-1",
  md: "text-sm px-3.5 py-1.5",
  lg: "text-base px-5 py-2",
};

// The ingestion workflow still names two older variants; map them rather
// than let them fall through to `primary`, which would turn every Back
// button into a solid primary one.
const VARIANT_ALIASES = { ghost: "subtle", quiet: "subtle", gold: "primary" };

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  as: As = "button",
  ...props
}) {
  const resolved = VARIANT_ALIASES[variant] || variant;
  return (
    <As
      className={`${BTN_BASE} ${BTN_VARIANTS[resolved] || BTN_VARIANTS.secondary} ${
        BTN_SIZES[size] || BTN_SIZES.md
      } ${className}`}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------ *
 * Form controls
 * ------------------------------------------------------------------ */

const CONTROL =
  "w-full bg-white border border-line-strong rounded-sm px-3 py-1.5 text-sm text-ink " +
  "placeholder:text-ink-3 transition-colors hover:border-ink-3 " +
  "disabled:bg-band disabled:text-ink-3 disabled:cursor-not-allowed";

/** Field labels are sentence case, small and medium weight — readable,
 *  not shouted. */
export function FieldLabel({ htmlFor, children, required, className = "" }) {
  return (
    <label htmlFor={htmlFor} className={`block text-xs font-semibold text-ink-2 mb-1 ${className}`}>
      {children}
      {required && <span className="text-err"> *</span>}
    </label>
  );
}

function Field({ label, id, hint, required, children }) {
  if (!label) return children;
  return (
    <div>
      <FieldLabel htmlFor={id} required={required}>
        {label}
      </FieldLabel>
      {children}
      {hint && <p className="text-xs text-ink-3 mt-1">{hint}</p>}
    </div>
  );
}

export function Input({ label, id, hint, required, className = "", ...props }) {
  return (
    <Field label={label} id={id} hint={hint} required={required}>
      <input id={id} className={`${CONTROL} ${className}`} {...props} />
    </Field>
  );
}

export function Textarea({ label, id, hint, required, className = "", ...props }) {
  return (
    <Field label={label} id={id} hint={hint} required={required}>
      <textarea id={id} className={`${CONTROL} resize-y py-2 ${className}`} {...props} />
    </Field>
  );
}

export function Select({ label, id, hint, required, className = "", children, ...props }) {
  return (
    <Field label={label} id={id} hint={hint} required={required}>
      <select id={id} className={`${CONTROL} cursor-pointer ${className}`} {...props}>
        {children}
      </select>
    </Field>
  );
}

/**
 * The repository search control: a field with the submit button attached
 * to its trailing edge as one unit — the pattern academic catalogues use,
 * rather than a floating rounded search pill.
 */
export function SearchField({
  value,
  onChange,
  onSubmit,
  placeholder = "Search projects",
  label = "Search projects",
  buttonLabel = "Search",
  size = "md",
  className = "",
  autoFocus = false,
  id = "repository-search",
}) {
  const tall = size === "lg";
  return (
    <form
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit?.(value);
      }}
      className={`flex w-full ${className}`}
    >
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        type="search"
        value={value}
        autoFocus={autoFocus}
        onChange={(event) => onChange?.(event.target.value)}
        placeholder={placeholder}
        className={`flex-1 min-w-0 bg-white border border-line-strong border-r-0 rounded-l-sm text-ink
          placeholder:text-ink-3 hover:border-ink-3 focus:border-primary transition-colors
          ${tall ? "px-4 py-2.5 text-base" : "px-3 py-1.5 text-sm"}`}
      />
      <button
        type="submit"
        className={`shrink-0 inline-flex items-center gap-2 bg-primary border border-primary text-white
          font-semibold rounded-r-sm hover:bg-primary-600 hover:border-primary-600 transition-colors cursor-pointer
          ${tall ? "px-5 py-2.5 text-base" : "px-3.5 py-1.5 text-sm"}`}
      >
        {buttonLabel}
      </button>
    </form>
  );
}

/* ------------------------------------------------------------------ *
 * Surfaces
 * ------------------------------------------------------------------ */

/**
 * A bordered panel. Flat: 1px border, small radius, no shadow. Reach for
 * it when content genuinely groups; ordinary page content should use
 * headings, rules and lists instead.
 */
export function Card({ tone = "plain", className = "", as: As = "div", children, ...props }) {
  const tones = {
    plain: "bg-white border-line",
    well: "bg-band border-line",
  };
  return (
    <As
      className={`border rounded-md ${tones[tone] || tones.plain} ${className}`}
      {...props}
    >
      {children}
    </As>
  );
}

/** A card's header strip — a light band with a title, the way repository
 *  panels label themselves. */
export function CardHeader({ title, actions, className = "" }) {
  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 border-b border-line bg-band px-4 py-2.5 rounded-t-md ${className}`}
    >
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** A page-level section heading with a rule beneath it. */
export function SectionHeading({ title, actions, id, level = 2, className = "" }) {
  const Tag = `h${Math.min(Math.max(level, 2), 4)}`;
  return (
    <div
      className={`flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-line pb-2 mb-4 ${className}`}
    >
      <Tag id={id} className="text-section">
        {title}
      </Tag>
      {actions && <div className="text-sm text-ink-2">{actions}</div>}
    </div>
  );
}

/** Page width. Each route picks the measure its content needs. */
const WIDTHS = {
  wide: "max-w-[1180px]",
  normal: "max-w-[1000px]",
  reading: "max-w-[820px]",
  narrow: "max-w-[560px]",
};

export function Container({ width = "normal", className = "", children }) {
  return (
    <div className={`mx-auto w-full ${WIDTHS[width] || WIDTHS.normal} ${className}`}>
      {children}
    </div>
  );
}

/** The heading block each page opens with. */
export function PageHeading({ title, lead, actions, className = "" }) {
  return (
    <div className={`flex flex-wrap items-start justify-between gap-x-8 gap-y-3 ${className}`}>
      <div className="min-w-0">
        <h1 className="text-title">{title}</h1>
        {lead && <p className="text-sm text-ink-2 mt-1.5 measure">{lead}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Status, counts and metadata
 * ------------------------------------------------------------------ */

const TONE_DEFS = {
  // Solid fill + white text. No translucent tints and no alpha-blended
  // borders anywhere in the status vocabulary -- a half-transparent chip
  // reads as a placeholder rather than as a designed state.
  ok:      { solid: "bg-ok text-white",      text: "text-ok",      soft: "bg-ok-050",      icon: faCircleCheck },
  warn:    { solid: "bg-warn text-white",    text: "text-warn",    soft: "bg-warn-050",    icon: faTriangleExclamation },
  err:     { solid: "bg-err text-white",     text: "text-err",     soft: "bg-err-050",     icon: faCircleExclamation },
  info:    { solid: "bg-info text-white",    text: "text-info",    soft: "bg-info-050",    icon: faCircleInfo },
  neutral: { solid: "bg-neutral text-white", text: "text-neutral", soft: "bg-band",      icon: faCircleInfo },
};

/** Tone lookup that also understands the success/warning/error names the
 *  ingestion pages use, so a failed job never renders as neutral grey. */
export const TONE = new Proxy(
  {
    ...TONE_DEFS,
    success: TONE_DEFS.ok,
    warning: TONE_DEFS.warn,
    error: TONE_DEFS.err,
    bad: TONE_DEFS.err,
    wait: TONE_DEFS.warn,
  },
  { get: (target, key) => target[key] ?? TONE_DEFS.neutral }
);

/**
 * A status label. A solid coloured chip with white text — the treatment a
 * shipped product uses for "Verified" or "Awaiting verification", rather
 * than tinted text on a washed-out background.
 */
export function Status({ tone = "neutral", pulse = false, children, className = "" }) {
  const t = TONE[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm px-2 py-[3px] text-xs font-semibold leading-tight ${t.solid} ${className}`}
    >
      {pulse && (
        <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-white/90" aria-hidden="true" />
      )}
      {children}
    </span>
  );
}

/** Left border accent for a table row, keyed to the same tones. */
export function statusRowAccent(tone = "neutral") {
  return (
    {
      ok: "border-l-ok", success: "border-l-ok",
      warn: "border-l-warn", warning: "border-l-warn", wait: "border-l-warn",
      err: "border-l-err", error: "border-l-err", bad: "border-l-err",
      info: "border-l-info",
      neutral: "border-l-transparent",
    }[tone] || "border-l-transparent"
  );
}

/** A small count beside a link or heading. */
export function Count({ children, className = "" }) {
  return (
    <span
      className={`inline-flex items-center justify-center min-w-[1.375rem] rounded-sm bg-band border border-line
        px-1.5 py-0.5 text-xs font-semibold text-ink-2 tnum ${className}`}
    >
      {children}
    </span>
  );
}

/** A keyword / subject term. Restrained: a bordered chip, not a coloured
 *  badge, and never a pill. */
export function Term({ children, className = "", as: As = "span", ...props }) {
  return (
    <As
      className={`inline-block rounded-sm border border-line bg-band px-2 py-0.5 text-xs text-ink-2
        hover:border-ink-3 hover:text-ink transition-colors ${className}`}
      {...props}
    >
      {children}
    </As>
  );
}

/** One row of a metadata list: label above value, or side-by-side. */
export function Meta({ label, children, inline = false, className = "" }) {
  if (inline) {
    return (
      <div className={`flex items-baseline justify-between gap-4 py-2 ${className}`}>
        <dt className="text-xs font-semibold text-ink-3 shrink-0">{label}</dt>
        <dd className="text-sm text-ink text-right break-words">{children}</dd>
      </div>
    );
  }
  return (
    <div className={`py-2.5 ${className}`}>
      <dt className="text-xs font-semibold text-ink-3">{label}</dt>
      <dd className="text-sm text-ink mt-0.5 break-words">{children}</dd>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Feedback: alerts, empty, loading
 * ------------------------------------------------------------------ */

/**
 * A message band — the repository idiom for an error or notice: a tinted
 * strip with a 1px border and a small leading icon, full width of its
 * container. Not a large coloured card.
 */
export function Alert({ tone = "info", title, children, action, className = "" }) {
  const t = TONE[tone];
  const bar = {
    ok: "bg-ok", warn: "bg-warn", err: "bg-err", info: "bg-info", neutral: "bg-neutral",
  }[tone] || "bg-neutral";
  return (
    <div
      role={tone === "err" || tone === "error" ? "alert" : "status"}
      className={`flex overflow-hidden rounded-md border border-line bg-white ${className}`}
    >
      {/* A solid colour bar carries the tone; the panel itself stays white
          so the message reads as part of the page, not as a coloured wash. */}
      <span className={`w-1 shrink-0 ${bar}`} aria-hidden="true" />
      <div className="flex flex-1 items-start gap-3 px-4 py-3">
        <FontAwesomeIcon icon={t.icon} className={`mt-0.5 h-4 w-4 shrink-0 ${t.text}`} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          {title && <p className="text-sm font-semibold text-ink">{title}</p>}
          {children && <div className="mt-0.5 break-words text-sm text-ink-2">{children}</div>}
          {action && <div className="mt-2.5">{action}</div>}
        </div>
      </div>
    </div>
  );
}

/** Convenience wrapper used wherever a request fails. */
export function ErrorNotice({ title = "Something went wrong", detail, action, className = "" }) {
  return (
    <Alert tone="err" title={title} action={action} className={className}>
      {detail}
    </Alert>
  );
}

/** A "nothing here" state — bordered, centred, quiet. */
export function EmptyState({ icon, title, description, action, className = "" }) {
  return (
    <div
      className={`border border-line rounded-md bg-band px-6 py-12 text-center flex flex-col items-center gap-2 ${className}`}
    >
      {icon && <FontAwesomeIcon icon={icon} className="h-6 w-6 text-ink-3 mb-1" aria-hidden="true" />}
      {title && <h3 className="text-item">{title}</h3>}
      {description && <p className="text-sm text-ink-2 max-w-md">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

/** A full-page state: not found, restricted, processing, coming soon. */
export function PageState({ tone = "neutral", icon, eyebrow, title, description, actions, children }) {
  const t = TONE[tone];
  return (
    <div className="mx-auto max-w-lg py-16 text-center flex flex-col items-center gap-4">
      {icon && (
        <span
          className={`inline-flex h-12 w-12 items-center justify-center rounded-md border border-line bg-band ${t.text}`}
        >
          <FontAwesomeIcon icon={icon} className="h-5 w-5" aria-hidden="true" />
        </span>
      )}
      {eyebrow && <Status tone={tone}>{eyebrow}</Status>}
      <h1 className="text-title">{title}</h1>
      {description && <p className="text-sm text-ink-2">{description}</p>}
      {actions && <div className="flex flex-wrap items-center justify-center gap-2 pt-1">{actions}</div>}
      {children}
    </div>
  );
}

/** Skeleton rows for a list of results. */
export function LoadingRows({ rows = 4, className = "" }) {
  return (
    <div className={`divide-y divide-line ${className}`} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="py-4 flex flex-col gap-2">
          <div className="skeleton h-4 rounded-sm" style={{ width: `${72 - (i % 3) * 12}%` }} />
          <div className="skeleton h-3 w-1/3 rounded-sm" />
          <div className="skeleton h-3 w-2/3 rounded-sm" />
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Navigation helpers
 * ------------------------------------------------------------------ */

/** The light band under the header carrying the trail. */
export function Breadcrumb({ children }) {
  return (
    <nav aria-label="Breadcrumb" className="border-b border-line bg-band">
      <div className="mx-auto max-w-[1180px] px-5 sm:px-8 py-2">
        <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2">{children}</ol>
      </div>
    </nav>
  );
}

export function Crumb({ children, last = false }) {
  return (
    <>
      <li className={last ? "text-ink font-semibold min-w-0 truncate" : "min-w-0"}>{children}</li>
      {!last && (
        <li aria-hidden="true" className="text-ink-3">
          /
        </li>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ *
 * Tables
 * ------------------------------------------------------------------ */

export function Table({ children, className = "" }) {
  return (
    <div className="overflow-x-auto border border-line rounded-md">
      <table className={`w-full min-w-[640px] text-sm border-collapse ${className}`}>{children}</table>
    </div>
  );
}

export function TableHead({ children }) {
  return (
    <thead>
      <tr className="bg-band border-b border-line">{children}</tr>
    </thead>
  );
}

export function Th({ children, hide, align = "left", className = "" }) {
  const hideClass = hide === "sm" ? "hidden sm:table-cell" : hide === "md" ? "hidden md:table-cell" : "";
  const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  return (
    <th
      scope="col"
      className={`px-4 py-2.5 text-xs font-semibold text-ink-2 ${alignClass} ${hideClass} ${className}`}
    >
      {children}
    </th>
  );
}

export function TableBody({ children }) {
  return <tbody className="divide-y divide-line">{children}</tbody>;
}

export function Tr({ children, accentClass = "border-l-transparent", className = "" }) {
  return (
    <tr className={`border-l-2 ${accentClass} hover:bg-band transition-colors ${className}`}>
      {children}
    </tr>
  );
}

export function Td({ children, hide, align = "left", className = "" }) {
  const hideClass = hide === "sm" ? "hidden sm:table-cell" : hide === "md" ? "hidden md:table-cell" : "";
  const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  return <td className={`px-4 py-3 align-top ${alignClass} ${hideClass} ${className}`}>{children}</td>;
}

/* ------------------------------------------------------------------ *
 * Compatibility shims for the ingestion pages
 * ------------------------------------------------------------------ */

/** Older name for `Status`. */
export const StatusTag = Status;
export const StatusMark = Status;

/** Older name for a small caption. Deliberately no longer uppercase. */
export function Eyebrow({ children, className = "", as: As = "span", ...props }) {
  return (
    <As className={`text-xs font-semibold text-ink-3 ${className}`} {...props}>
      {children}
    </As>
  );
}

/** Older full-page state name. */
export const StatusSplash = PageState;
export const EmptyNotice = EmptyState;
export const LoadingLines = LoadingRows;
export const MetaEntry = Meta;
export const IndexTerm = Term;
export const PageColumn = Container;
export const Sheet = Card;

/** Older masthead name used by admin pages. */
export function PageMasthead({ eyebrow, title, standfirst, actions, className = "" }) {
  return (
    <div className={className}>
      {eyebrow && <p className="mb-1 text-xs font-bold text-accent">{eyebrow}</p>}
      <PageHeading title={title} lead={standfirst} actions={actions} />
    </div>
  );
}

export const SectionHead = ({ number, title, aside, ...rest }) => (
  <SectionHeading title={number != null ? `${number}. ${title}` : title} actions={aside} {...rest} />
);

export function Prose({ children, className = "" }) {
  return <div className={`text-base text-ink-2 measure ${className}`}>{children}</div>;
}
