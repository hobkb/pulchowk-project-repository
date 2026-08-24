import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ingestionApi,
  metadataApi,
  organizationApi,
  accountsApi,
  projectsApi,
} from "../api/client";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faSpinner,
  faCheckCircle,
  faCircleExclamation,
  faChevronLeft,
  faChevronRight,
  faChevronDown,
  faPlus,
  faTrash,
  faArrowUp,
  faArrowDown,
  faUserPlus,
  faFileLines,
  faGraduationCap,
  faEye,
  faCodeBranch,
  faSearch,
  faFilePdf,
  faColumns,
  faXmark,
  faClock,
} from "@fortawesome/free-solid-svg-icons";
import {
  StatusTag,
  Eyebrow,
  Button,
  StatusSplash,
  Card,
  Dialog,
  ErrorNotice,
} from "../components/ui";

const CANONICAL_SECTIONS = [
  "Introduction",
  "Background",
  "Literature Review",
  "Methodology",
  "Implementation",
  "Results",
  "Discussion",
  "Conclusion",
  "Future Work",
  "Evaluation",
  "Recommendations",
  "Appendix",
  "References",
];

function autoCanonicalizeHeading(title) {
  if (!title) return "Introduction";
  const cleaned = title.replace(/^\d+(?:\.\d+)*\s*/, "").trim();
  if (!cleaned) return "Introduction";

  const lower = cleaned.toLowerCase();
  for (const candidate of CANONICAL_SECTIONS) {
    const candLower = candidate.toLowerCase();
    if (lower.includes(candLower) || candLower.includes(lower)) {
      return candidate;
    }
  }

  if (lower.includes("intro")) return "Introduction";
  if (lower.includes("lit") || lower.includes("review")) return "Literature Review";
  if (lower.includes("method") || lower.includes("approach") || lower.includes("design")) return "Methodology";
  if (lower.includes("implement") || lower.includes("system")) return "Implementation";
  if (lower.includes("result") || lower.includes("experiment") || lower.includes("output")) return "Results";
  if (lower.includes("discuss")) return "Discussion";
  if (lower.includes("conclus")) return "Conclusion";
  if (lower.includes("future")) return "Future Work";
  if (lower.includes("evalu")) return "Evaluation";
  if (lower.includes("recommend")) return "Recommendations";
  if (lower.includes("appendix") || lower.includes("annex")) return "Appendix";
  if (lower.includes("ref") || lower.includes("biblio")) return "References";

  return cleaned;
}

// ---------------------------------------------------------------
// Section tree helpers. Sections extracted by the ingestion pipeline
// are a real nested tree (each node may carry a `children` array of
// subsections), not a flat list -- these operate on that tree via a
// `path` (an array of child-indices from the root, e.g. [1, 0] means
// "root[1].children[0]") so add/move/delete/update work at any depth
// without flattening the structure, and so a "Save & Validate" never
// has a reason to drop `children` when it rebuilds the payload.
// ---------------------------------------------------------------

/** The numbering a heading carries in the document itself: "1.",
 *  "2.3", "1.1.1)". Returns the depth it implies (1, 2, 3 …) or null. */
function numberingDepth(heading) {
  const match = /^\s*(\d+(?:\.\d+)*)\s*[.)]?\s+\S/.exec(heading || "");
  return match ? match[1].split(".").length : null;
}

/**
 * Normalises whatever the job payload holds into one node per heading,
 * nested so that ONLY top-level sections sit at the root.
 *
 * The document's own numbering is the authority when it is present:
 * "1. Introduction" is depth 1, "1.1 Background" and "1.2 Problem
 * Statement" are depth 2, "1.1.1" is depth 3. Grouping by that is what
 * puts every subsection inside its parent's card instead of giving each
 * detected heading a card of its own.
 *
 * Numbering is preferred over the stored `heading_level` because the
 * extractor derives that level from font size, which regularly promotes a
 * subsection to the top level. When a document's headings carry no numbers
 * at all (many do not), the stored level is used instead, and a payload
 * that already nests keeps its shape.
 *
 * A level that would leave an impossible gap is clamped rather than
 * dropped, so no extracted heading can disappear from the editor.
 */
function normalizeSectionTree(nodes) {
  const flat = [];

  // Walk whatever shape arrived — flat list or existing tree — into
  // document order, remembering the depth each node was stored at.
  const collect = (items, depth) => {
    (Array.isArray(items) ? items : []).forEach((node) => {
      if (!node || typeof node !== "object") return;
      flat.push({ node, storedDepth: depth });
      collect(node.children, depth + 1);
    });
  };
  collect(nodes, 1);
  if (flat.length === 0) return [];

  const numbered = flat.filter(({ node }) => numberingDepth(node.heading) !== null);
  // Only trust numbering when the document actually uses it; a single
  // stray "2024 in review" heading must not restructure everything.
  const useNumbering = numbered.length >= Math.max(2, flat.length * 0.4);

  const root = [];
  const stack = []; // [{ level, node }], shallowest first

  flat.forEach(({ node, storedDepth }) => {
    let level = null;
    if (useNumbering) level = numberingDepth(node.heading);
    if (level === null) {
      level = Number.isInteger(node.heading_level) ? node.heading_level : storedDepth;
    }
    if (!Number.isInteger(level) || level < 1) level = 1;

    const maxAllowed = stack.length ? stack[stack.length - 1].level + 1 : 1;
    if (level > maxAllowed) level = maxAllowed;

    const built = {
      ...node,
      heading_level: level,
      canonical_section: node.canonical_section || autoCanonicalizeHeading(node.heading),
      children: [],
    };

    while (stack.length && stack[stack.length - 1].level >= level) stack.pop();
    if (stack.length) stack[stack.length - 1].node.children.push(built);
    else root.push(built);
    stack.push({ level, node: built });
  });

  const renumberDeep = (items) =>
    renumber(items).map((n) => ({ ...n, children: renumberDeep(n.children || []) }));
  return renumberDeep(root);
}

/** The one loading indicator on this page: small, inline, and only ever
 *  rendered while a real request is in flight. */
function Spinner({ className = "" }) {
  return (
    <FontAwesomeIcon
      icon={faSpinner}
      className={`h-3.5 w-3.5 spin ${className}`}
      aria-hidden="true"
    />
  );
}

let sectionClientIdCounter = 0;

/** A client-only id, never sent to the server, used purely to find the
 *  card just added and scroll to it -- the tree has no other stable
 *  identity to key off, since ids only exist once the server has assigned
 *  one and a freshly added section has not been saved yet. */
function nextSectionClientId() {
  sectionClientIdCounter += 1;
  return `new-${sectionClientIdCounter}`;
}

function newSectionNode(overrides = {}) {
  return {
    heading: "New Section",
    canonical_section: "Introduction",
    heading_level: 1,
    display_order: 1,
    content: "",
    page_start: 1,
    page_end: 1,
    word_count: 0,
    children: [],
    _clientId: nextSectionClientId(),
    ...overrides,
  };
}

function renumber(nodes) {
  return nodes.map((n, i) => ({ ...n, display_order: i + 1 }));
}

function updateTreeAtPath(tree, path, updater) {
  if (path.length === 1) {
    return renumber(
      tree.map((node, i) => (i === path[0] ? updater(node) : node))
    );
  }
  const [head, ...rest] = path;
  return tree.map((node, i) =>
    i === head
      ? { ...node, children: updateTreeAtPath(node.children || [], rest, updater) }
      : node
  );
}

function deleteAtPath(tree, path) {
  if (path.length === 1) {
    return renumber(tree.filter((_, i) => i !== path[0]));
  }
  const [head, ...rest] = path;
  return tree.map((node, i) =>
    i === head
      ? { ...node, children: deleteAtPath(node.children || [], rest) }
      : node
  );
}

function moveAtPath(tree, path, direction) {
  if (path.length === 1) {
    const idx = path[0];
    const targetIdx = direction === "up" ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= tree.length) return tree;
    const updated = [...tree];
    [updated[idx], updated[targetIdx]] = [updated[targetIdx], updated[idx]];
    return renumber(updated);
  }
  const [head, ...rest] = path;
  return tree.map((node, i) =>
    i === head
      ? { ...node, children: moveAtPath(node.children || [], rest, direction) }
      : node
  );
}

function addChildAtPath(tree, path) {
  // path === null means "add a new root-level section".
  if (path == null) {
    const created = newSectionNode({ display_order: tree.length + 1 });
    return [renumber([...tree, created]), created._clientId];
  }
  if (path.length === 1) {
    let newId = null;
    const next = tree.map((node, i) => {
      if (i !== path[0]) return node;
      const children = node.children || [];
      const created = newSectionNode({ heading_level: (node.heading_level || 1) + 1 });
      newId = created._clientId;
      return { ...node, children: renumber([...children, created]) };
    });
    return [next, newId];
  }
  const [head, ...rest] = path;
  let newId = null;
  const next = tree.map((node, i) => {
    if (i !== head) return node;
    const [children, id] = addChildAtPath(node.children || [], rest);
    newId = id;
    return { ...node, children };
  });
  return [next, newId];
}

/** Flattens the tree into a display list for the review-step summary,
 * keeping each node's numbering/depth so the summary honestly reflects
 * every subsection, not just the top level. */
function flattenForSummary(tree, path = []) {
  return tree.flatMap((node, i) => {
    const nodePath = [...path, i];
    return [
      { heading: node.heading, canonical_section: node.canonical_section, depth: path.length, numbering: nodePath.map((n) => n + 1).join(".") },
      ...flattenForSummary(node.children || [], nodePath),
    ];
  });
}

/** Recursively serializes the tree for the PATCH payload -- the fix for
 * the actual bug: every node keeps its own `children`, computed
 * word_count, and re-derived display_order, instead of being flattened
 * to a childless top-level list. */
function serializeSectionTree(nodes) {
  return nodes.map((node, idx) => ({
    heading: node.heading,
    numbering: node.numbering || null,
    canonical_section: node.canonical_section || autoCanonicalizeHeading(node.heading),
    heading_level: parseInt(node.heading_level) || 1,
    display_order: idx + 1,
    content: node.content || "",
    page_start: node.page_start ? parseInt(node.page_start) : null,
    page_end: node.page_end ? parseInt(node.page_end) : null,
    word_count: node.content ? (node.content.match(/\w+/g) || []).length : node.word_count || 0,
    children: serializeSectionTree(node.children || []),
  }));
}

/**
 * One section and everything beneath it.
 *
 * A TOP-LEVEL section is a single card, and its subsections are rendered
 * INSIDE that card, indented against a rule down the left. They are not
 * separate sibling cards: "1.1 Background" belongs to "1 Introduction"
 * and has to look like it does, especially in the common case where the
 * chapter heading itself carries no text because the first subsection
 * begins immediately after it.
 *
 * The same add/move/delete/edit controls work identically at every depth;
 * only the chrome differs.
 */
function SectionEditorRow({ node, path, isFirst, isLast, depth, onChange, onMove, onDelete, onAddChild, jobId }) {
  // The document's own section number, where extraction captured one.
  // Falling back to the card's position was actively misleading: a
  // subsection the report numbers 5.3 showed as "5.2" purely because 5.2
  // was not present in this document, so the label disagreed with both the
  // report and its table of contents.
  const numbering = node.numbering || path.map((i) => i + 1).join(".");
  const childCount = (node.children || []).length;
  const [collapsed, setCollapsed] = useState(false);
  // "Find page" -- looks up which real PDF page this heading starts on,
  // for a section added by hand rather than extracted (where the page is
  // already known). Local to this row: two sections locating at once must
  // not share one loading/result state.
  const [locating, setLocating] = useState(false);
  const [locateNote, setLocateNote] = useState(null);

  const handleLocatePage = async () => {
    if (locating || !jobId || !(node.heading || "").trim()) return;
    setLocating(true);
    setLocateNote(null);
    try {
      const body = await ingestionApi.locateHeading(jobId, node.heading);
      const page = body?.data?.page;
      if (page) {
        onChange(path, "page_start", page);
        // A single located line only proves a start page, not a range --
        // page_end is left as whatever the reviewer already set, or
        // defaulted to the same page as a starting point to widen.
        if (!node.page_end || node.page_end === node.page_start) {
          onChange(path, "page_end", page);
        }
      } else {
        setLocateNote("No confident match found");
      }
    } catch (err) {
      setLocateNote(err.message || "Could not check the PDF");
    } finally {
      setLocating(false);
      setTimeout(() => setLocateNote(null), 3000);
    }
  };
  // Most extracted headings already carry their own number ("2 Literature
  // Review"). Showing the derived position beside one of those printed it
  // twice, so the position marker is only rendered when the heading does
  // not already begin with a number of its own.
  const headingIsNumbered = /^\s*\d+(\.\d+)*[.)]?\s/.test(node.heading || "");
  const isRoot = depth === 0;
  const wordCount =
    node.word_count || (node.content ? (node.content.match(/\w+/g) || []).length : 0);
  const isEmptyParent = childCount > 0 && !(node.content || "").trim();

  return (
    // Root: a card. Nested: no card at all — just the indent and the rule,
    // so the subtree stays visually inside its parent.
    <div
      data-section-id={node._clientId}
      className={
        isRoot
          ? "shrink-0 overflow-hidden rounded-md border border-line-strong bg-white"
          : "border-l-2 border-line-strong pl-3 sm:pl-4"
      }
    >
      <div
        className={
          isRoot
            ? `flex flex-col gap-4 px-4 pt-4 ${childCount > 0 && !collapsed ? "pb-2" : "pb-4"}`
            : "flex flex-col gap-3 py-4"
        }
      >
        <div className={`flex items-center justify-between gap-4 ${isRoot ? "border-b border-line pb-3" : ""}`}>
          <div className="flex min-w-0 flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              aria-expanded={!collapsed}
              title={collapsed ? "Expand section" : "Collapse section"}
              className="shrink-0 cursor-pointer rounded-sm p-1 text-ink-3 hover:bg-band hover:text-ink transition-colors"
            >
              <FontAwesomeIcon
                icon={collapsed ? faChevronRight : faChevronDown}
                className="h-3 w-3"
              />
            </button>
            {!headingIsNumbered && (
              <span
                className={`tnum shrink-0 font-semibold ${
                  depth === 0 ? "text-base text-primary" : "text-sm text-ink-2"
                }`}
              >
                {numbering}
              </span>
            )}
            <span className={`min-w-0 truncate ${depth === 0 ? "text-item" : "text-sm font-semibold text-ink"}`}>
              {node.heading || "Untitled section"}
            </span>
            {childCount > 0 && (
              <span className="shrink-0 rounded-sm border border-line bg-band px-1.5 py-0.5 text-xs text-ink-2 tnum">
                {childCount} {childCount === 1 ? "subsection" : "subsections"}
              </span>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => onAddChild(path)}
              className="p-1.5 rounded-sm hover:bg-band text-ink-2 hover:text-ink cursor-pointer transition-colors"
              title="Add subsection"
            >
              <FontAwesomeIcon icon={faPlus} className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onMove(path, "up")}
              disabled={isFirst}
              className="p-1.5 rounded-sm hover:bg-band text-ink-2 hover:text-ink disabled:opacity-30 cursor-pointer transition-colors"
              title="Move Up"
            >
              <FontAwesomeIcon icon={faArrowUp} className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onMove(path, "down")}
              disabled={isLast}
              className="p-1.5 rounded-sm hover:bg-band text-ink-2 hover:text-ink disabled:opacity-30 cursor-pointer transition-colors"
              title="Move Down"
            >
              <FontAwesomeIcon icon={faArrowDown} className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onDelete(path)}
              className="p-1.5 rounded-sm hover:bg-err-050 text-ink-3 hover:text-err cursor-pointer ml-1 transition-colors"
              title="Delete Section"
            >
              <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {!collapsed && !isRoot && (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={node.heading}
                onChange={(e) => onChange(path, "heading", e.target.value)}
                aria-label={`Subsection ${numbering} heading`}
                className={`${FIELD_INPUT} min-w-[14rem] flex-1 font-semibold`}
                placeholder="Subsection heading"
              />
              <span className="flex items-center gap-1 text-xs text-ink-3">
                <span>p.</span>
                <input
                  type="number"
                  value={node.page_start || ""}
                  onChange={(e) => onChange(path, "page_start", e.target.value)}
                  aria-label={`Subsection ${numbering} page start`}
                  className={`${FIELD_INPUT} tnum w-16 px-2 py-1`}
                />
                <span>–</span>
                <input
                  type="number"
                  value={node.page_end || ""}
                  onChange={(e) => onChange(path, "page_end", e.target.value)}
                  aria-label={`Subsection ${numbering} page end`}
                  className={`${FIELD_INPUT} tnum w-16 px-2 py-1`}
                />
                {jobId && (
                  <button
                    type="button"
                    onClick={handleLocatePage}
                    disabled={locating || !(node.heading || "").trim()}
                    title="Find this heading in the source PDF"
                    className="flex items-center gap-1 rounded-sm border border-line px-1.5 py-1 text-ink-3 hover:border-primary hover:text-primary disabled:opacity-40 disabled:hover:border-line disabled:hover:text-ink-3 cursor-pointer transition-colors"
                  >
                    <FontAwesomeIcon
                      icon={locating ? faSpinner : faSearch}
                      className={`h-3 w-3 ${locating ? "spin" : ""}`}
                    />
                  </button>
                )}
                {locateNote && <span className="text-ink-3">{locateNote}</span>}
              </span>
              <span className="tnum text-xs text-ink-3">{wordCount} words</span>
            </div>
            <textarea
              rows={4}
              value={node.content || ""}
              onChange={(e) => onChange(path, "content", e.target.value)}
              aria-label={`Subsection ${numbering} content`}
              className={`${FIELD_INPUT} min-h-[96px] resize-y leading-relaxed`}
              placeholder="Subsection text content…"
            />
          </div>
        )}

        {!collapsed && isRoot && (
        <>
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-4 items-end">
          <div className="sm:col-span-5 flex flex-col gap-1.5">
            <label className="tnum text-xs text-ink-2">
              Heading title <span className="text-err">*</span>
            </label>
            <input
              type="text"
              value={node.heading}
              onChange={(e) => onChange(path, "heading", e.target.value)}
              className={FIELD_INPUT}
              placeholder="e.g. 1. Introduction"
            />
          </div>

          <div className="sm:col-span-2 flex flex-col gap-1.5">
            <label className="tnum text-xs text-ink-2">Level</label>
            <select
              value={node.heading_level || 1}
              onChange={(e) => onChange(path, "heading_level", e.target.value)}
              className={`${FIELD_INPUT} cursor-pointer`}
            >
              {[1, 2, 3, 4, 5, 6].map((l) => (
                <option key={l} value={l}>H{l}</option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2 flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-ink-2">Page start</label>
            <input
              type="number"
              value={node.page_start || ""}
              onChange={(e) => onChange(path, "page_start", e.target.value)}
              className={`${FIELD_INPUT} tnum`}
              placeholder="1"
            />
          </div>

          <div className="sm:col-span-2 flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-ink-2">Page end</label>
            <input
              type="number"
              value={node.page_end || ""}
              onChange={(e) => onChange(path, "page_end", e.target.value)}
              className={`${FIELD_INPUT} tnum`}
              placeholder="5"
            />
          </div>

          {jobId && (
            <div className="sm:col-span-1 flex flex-col gap-1.5">
              <span className="text-xs font-semibold text-transparent select-none">Find</span>
              <button
                type="button"
                onClick={handleLocatePage}
                disabled={locating || !(node.heading || "").trim()}
                title="Find this heading in the source PDF and fill the page numbers"
                aria-label="Find this heading in the source PDF and fill the page numbers"
                className={`${FIELD_INPUT} flex items-center justify-center text-ink-2 hover:border-primary hover:text-primary disabled:opacity-40 disabled:hover:border-line disabled:hover:text-ink-2 cursor-pointer transition-colors`}
              >
                <FontAwesomeIcon
                  icon={locating ? faSpinner : faSearch}
                  className={`h-3.5 w-3.5 ${locating ? "spin" : ""}`}
                />
              </button>
            </div>
          )}
        </div>
        {locateNote && (
          <p className="-mt-2 text-xs text-ink-3">{locateNote}</p>
        )}

        <div className="flex flex-col gap-2 pt-1">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-ink-2">Section content</label>
            <span className="tnum text-xs text-ink-3">{wordCount} words</span>
          </div>
          {/* A chapter heading followed immediately by its first subsection
              genuinely has no text of its own. Saying so is more useful than
              handing the reviewer a tall empty box to wonder about. */}
          {isEmptyParent && (
            <p className="text-xs text-ink-3">
              No text between this heading and its first subsection. That is normal — the
              content lives in the subsections below.
            </p>
          )}
          <textarea
            rows={isEmptyParent ? 2 : depth > 0 ? 4 : 7}
            value={node.content || ""}
            onChange={(e) => onChange(path, "content", e.target.value)}
            className={`${FIELD_INPUT} resize-y leading-relaxed ${
              isEmptyParent ? "min-h-[52px]" : depth > 0 ? "min-h-[96px]" : "min-h-[150px]"
            }`}
            placeholder={isEmptyParent ? "Add introductory text (optional)…" : "Section text content…"}
          />
        </div>
        </>
        )}
      </div>

      {!collapsed && childCount > 0 && (
        // Inside the SAME card body as the parent -- one card per
        // top-level section, with its subsections flowing beneath the
        // parent's own content rather than in boxes of their own.
        <div className={isRoot ? "px-4 pb-4" : ""}>
          <div className="divide-y divide-line border-t border-line">
            {node.children.map((child, i) => (
              <SectionEditorRow
                key={i}
                node={child}
                path={[...path, i]}
                isFirst={i === 0}
                isLast={i === node.children.length - 1}
                depth={depth + 1}
                onChange={onChange}
                onMove={onMove}
                onDelete={onDelete}
                onAddChild={onAddChild}
                jobId={jobId}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Shared field chrome for this page's dense multi-step form.
const FIELD_INPUT =
  "px-3.5 py-2.5 rounded-sm bg-band border border-line text-ink font-medium text-sm focus:outline-none focus:border-primary focus:bg-white transition-colors";
const FIELD_LABEL = "text-sm font-bold text-ink";

export default function IngestionWorkflow() {
  const { id } = useParams();
  const navigate = useNavigate();

  // Workflow job & metadata state
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [logs, setLogs] = useState([]);
  const [showLogs, setShowLogs] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState(null);

  // Side-by-side PDF preview toggle
  const [showPdf, setShowPdf] = useState(true);

  // Stepper step: 1 (Info), 2 (Abstract), 3 (Keywords), 4 (Sections), 5 (Review)
  const [currentStep, setCurrentStep] = useState(1);
  // editingSections: true when admin clicks "Add Section Content Now" from SECTIONS_PENDING screen
  const [editingSections, setEditingSections] = useState(false);

  // Metadata dropdown choices
  const [choices, setChoices] = useState(null);
  const [clusterChoices, setClusterChoices] = useState([]);
  const [departmentChoices, setDepartmentChoices] = useState([]);
  // True when the pipeline read a department off the report that matched
  // one of the real departments, so the field can say whether the value
  // was identified or still needs choosing.
  const [detectedDepartment, setDetectedDepartment] = useState(false);
  const [departments, setDepartments] = useState([]);
  const [campuses, setCampuses] = useState([]);
  const [researchGroups, setResearchGroups] = useState([]);
  const [facultyList, setFacultyList] = useState([]);

  // Faculty search filter
  const [facultySearch, setFacultySearch] = useState("");

  // Form State (copied from extracted_payload)
  const [projectFields, setProjectFields] = useState({
    title: "",
    project_type: "Major",
    academic_level: "UG",
    batch: "078",
    department_name: "",
    campus_name: "",
    research_group_name: "",
    cluster: "",
    repository_url: "",
    abstract: "",
  });

  const [departmentId, setDepartmentId] = useState("");
  const [campusId, setCampusId] = useState("");
  const [researchGroupId, setResearchGroupId] = useState("");

  const [selectedSupervisors, setSelectedSupervisors] = useState([]);
  const [authors, setAuthors] = useState([]);
  const [keywords, setKeywords] = useState([]);
  const [sections, setSections] = useState([]);
  // The id of a section just added, so the page can scroll to it once it
  // renders. A long report can have dozens of sections and subsections;
  // without this, adding one appended it to the bottom of a tree the
  // reviewer had to scroll all the way down to find every time.
  const [pendingScrollId, setPendingScrollId] = useState(null);

  useEffect(() => {
    if (!pendingScrollId) return;
    const frame = requestAnimationFrame(() => {
      const el = document.querySelector(`[data-section-id="${pendingScrollId}"]`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.querySelector("input, textarea")?.focus({ preventScroll: true });
      }
      setPendingScrollId(null);
    });
    return () => cancelAnimationFrame(frame);
  }, [pendingScrollId, sections]);
  const [skipSections, setSkipSections] = useState(false);

  // Add Faculty Modal State
  const [showAddFacultyModal, setShowAddFacultyModal] = useState(false);
  const [newFaculty, setNewFaculty] = useState({
    full_name: "",
    title: "Dr.",
    designation: "Assistant Professor",
    department: "",
  });
  const [creatingFaculty, setCreatingFaculty] = useState(false);

  // Verification & Publication state
  const [verifying, setVerifying] = useState(false);
  const [verifiedSuccess, setVerifiedSuccess] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});
  // The one place the save/publish flow reports failure. Previously these
  // used window.alert(), so nothing on the page changed and the button
  // stayed clickable.
  const [submitError, setSubmitError] = useState(null);

  // 1. Fetch Job detail
  const fetchJob = useCallback(async () => {
    try {
      const res = await ingestionApi.getJob(id);
      const j = res.data;
      setJob(j);

      // Populate form states when payload exists
      if (j.extracted_payload) {
        const payload = j.extracted_payload;
        const pf = payload.project_fields || {};

        setProjectFields({
          title: pf.title || "",
          project_type: pf.project_type || "Major",
          academic_level: pf.academic_level || "UG",
          batch: pf.batch || "078",
          department_name: pf.department_name || "",
          campus_name: pf.campus_name || "",
          research_group_name: pf.research_group_name || "",
          cluster: pf.cluster || "",
          repository_url: pf.repository_url || pf.github_url || "",
          abstract: pf.abstract || "",
        });

        // Supervisors — start empty for manual selection by admin
        if (Array.isArray(pf.supervisors) && payload._verified_by_admin) {
          setSelectedSupervisors(
            pf.supervisors.map((s) => {
              if (typeof s === "string") return { full_name: s.trim(), title: "", designation: "" };
              return {
                full_name: (s?.full_name || s?.name || "").trim(),
                title: (s?.title || "").trim(),
                designation: (s?.designation || "").trim(),
              };
            }).filter((s) => s.full_name)
          );
        } else {
          setSelectedSupervisors([]);
        }

        // Parse Authors from people_and_roles
        const people = payload.people_and_roles || [];
        const authorList = people
          .filter((p) => (p.role || "").toLowerCase() === "author")
          .map((p, idx) => ({
            id: idx + 1,
            full_name: p.full_name || "",
            roll_number: p.roll_number || "",
            academic_level: p.academic_level || pf.academic_level || "UG",
            display_order: p.display_order || idx + 1,
            matchedStudent: null,
          }));
        setAuthors(authorList.length > 0 ? authorList : [{ id: 1, full_name: "", roll_number: "", academic_level: "UG", display_order: 1 }]);

        // Keywords
        setKeywords(payload.keywords || []);

        // Sections. Normalised into a real tree before they reach the
        // editor -- see normalizeSectionTree.
        setSections(normalizeSectionTree(payload.project_sections || []));
      }
    } catch (err) {
      setError(err.message || "Failed to load job details.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  // Auto-polling when status is PENDING or PROCESSING
  useEffect(() => {
    if (!job) return;
    if (job.status === "PENDING" || job.status === "PROCESSING") {
      const timer = setInterval(() => {
        fetchJob();
      }, 2500);
      return () => clearInterval(timer);
    }
  }, [job, fetchJob]);

  // Load choices and database entities (parse res.data || res.results || res)
  useEffect(() => {
    metadataApi.getChoices().then((res) => setChoices(res.data)).catch(() => { });
    projectsApi
      .facets()
      .then((res) => {
        setClusterChoices(res?.data?.cluster_choices || []);
        setDepartmentChoices(res?.data?.department_choices || []);
      })
      .catch(() => {
        setClusterChoices([]);
        setDepartmentChoices([]);
      });

    organizationApi.getDepartments().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setDepartments(list);
    }).catch(() => { });

    organizationApi.getCampuses().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setCampuses(list);
    }).catch(() => { });

    organizationApi.getResearchGroups().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setResearchGroups(list);
    }).catch(() => { });

    accountsApi.getFacultyList().then((res) => {
      const list = res.data || res.results || (Array.isArray(res) ? res : []);
      setFacultyList(list);
    }).catch(() => { });
  }, []);

  // Pre-select database records by extracted names
  useEffect(() => {
    if (departmentChoices.length === 0) return;
    setProjectFields((previous) => {
      const current = (previous.department_name || "").trim();
      if (!current) {
        setDetectedDepartment(false);
        return previous;
      }
      const match = departmentChoices.find(
        (d) => d.toLowerCase() === current.toLowerCase()
      );
      setDetectedDepartment(Boolean(match));
      if (match && match !== current) return { ...previous, department_name: match };
      if (!match) return { ...previous, department_name: "" };
      return previous;
    });
  }, [departmentChoices]);

  useEffect(() => {
    if (departments.length > 0 && projectFields.department_name) {
      const match = departments.find(
        (d) => d.name.toLowerCase() === projectFields.department_name.toLowerCase()
      );
      if (match) setDepartmentId(match.id);
    }
  }, [departments, projectFields.department_name]);

  useEffect(() => {
    if (campuses.length > 0 && projectFields.campus_name) {
      const match = campuses.find(
        (c) => c.name.toLowerCase() === projectFields.campus_name.toLowerCase()
      );
      if (match) setCampusId(match.id);
    }
  }, [campuses, projectFields.campus_name]);

  useEffect(() => {
    if (researchGroups.length > 0 && projectFields.research_group_name) {
      const match = researchGroups.find(
        (rg) => rg.name.toLowerCase() === projectFields.research_group_name.toLowerCase()
      );
      if (match) setResearchGroupId(match.id);
    }
  }, [researchGroups, projectFields.research_group_name]);

  // Filter Faculty Supervisors by Department
  const filteredFacultyList = useMemo(() => {
    if (!departmentId) return facultyList;
    return facultyList.filter((f) => String(f.department_id) === String(departmentId));
  }, [facultyList, departmentId]);

  const searchedFaculty = useMemo(() => {
    const q = facultySearch.trim().toLowerCase();

    // With nothing typed, the department's own faculty are the useful
    // default. As soon as anything is typed the search covers EVERY
    // registered supervisor: restricting it to one department hid people
    // who genuinely exist, and the reviewer then added them again by hand
    // -- which is how the same supervisor ended up in the directory twice.
    if (!q) {
      return filteredFacultyList.length > 0 ? filteredFacultyList : facultyList;
    }

    return facultyList.filter((f) =>
      [f.full_name, f.designation, f.title]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(q))
    );
  }, [filteredFacultyList, facultyList, facultySearch]);

  // Fetch logs on demand, and toggle the panel shut on a second click.
  //
  // A failure used to go to console.error and nowhere else, so a request
  // that 403'd or timed out was indistinguishable from a dead button. The
  // outcome is now always visible: a spinner while it runs, the entries if
  // it worked, and the reason if it did not.
  const handleFetchLogs = async () => {
    if (showLogs) {
      setShowLogs(false);
      return;
    }
    if (logsLoading) return;

    setLogsLoading(true);
    setLogsError(null);
    setShowLogs(true);
    try {
      const res = await ingestionApi.getJobLogs(id);
      setLogs(res.data || []);
    } catch (err) {
      setLogsError(err.message || "The processing log could not be loaded.");
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  // Author Management
  const handleAddAuthor = () => {
    setAuthors((prev) => [
      ...prev,
      {
        id: Date.now(),
        full_name: "",
        roll_number: "",
        academic_level: projectFields.academic_level || "UG",
        display_order: prev.length + 1,
        matchedStudent: null,
      },
    ]);
  };

  const handleRemoveAuthor = (idx) => {
    setAuthors((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleAuthorChange = (idx, field, value) => {
    setAuthors((prev) => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], [field]: value };
      return updated;
    });
  };

  const handleMatchStudentByRoll = async (idx, rollNumber) => {
    if (!rollNumber || !rollNumber.trim()) return;
    try {
      const res = await accountsApi.getStudents({ roll_number: rollNumber.trim() });
      const matched = res.data?.[0];
      setAuthors((prev) => {
        const updated = [...prev];
        updated[idx] = {
          ...updated[idx],
          matchedStudent: matched || null,
          full_name: matched ? matched.full_name : updated[idx].full_name,
        };
        return updated;
      });
    } catch (err) {
      console.error(err);
    }
  };

  // Inline Faculty Creation
  const handleCreateFaculty = async (e) => {
    e.preventDefault();
    if (!newFaculty.full_name) return;
    setCreatingFaculty(true);
    try {
      const res = await accountsApi.createFaculty({
        ...newFaculty,
        department: departmentId || departments[0]?.id || null,
      });
      const created = res.data;
      setFacultyList((prev) => [...prev, created]);
      setSelectedSupervisors((prev) => [
        ...prev,
        {
          full_name: created.full_name,
          title: created.title || "",
          designation: created.designation || "",
        },
      ]);
      setShowAddFacultyModal(false);
      setNewFaculty({ full_name: "", title: "Dr.", designation: "Assistant Professor", department: "" });
    } catch (err) {
      alert("Failed to create faculty member: " + err.message);
    } finally {
      setCreatingFaculty(false);
    }
  };

  // Keyword Chip Management
  const [newKeywordInput, setNewKeywordInput] = useState("");
  const handleAddKeyword = () => {
    const val = newKeywordInput.trim();
    if (val && !keywords.includes(val)) {
      setKeywords((prev) => [...prev, val]);
      setNewKeywordInput("");
    }
  };

  const handleRemoveKeyword = (idx) => {
    setKeywords((prev) => prev.filter((_, i) => i !== idx));
  };

  // Section Editor Management (with Automatic Canonicalization). Every
  // handler operates on a `path` (array of child-indices from the root)
  // so subsections at any depth get the exact same add/move/delete/edit
  // capability as top-level sections -- see the tree helpers above.
  const handleAddSection = () => {
    setSections((prev) => {
      const [next, newId] = addChildAtPath(prev, null);
      setPendingScrollId(newId);
      return next;
    });
  };

  const handleAddSubsection = (path) => {
    setSections((prev) => {
      const [next, newId] = addChildAtPath(prev, path);
      setPendingScrollId(newId);
      return next;
    });
  };

  const handleSectionChange = (path, field, value) => {
    setSections((prev) =>
      updateTreeAtPath(prev, path, (node) => {
        const sec = { ...node, [field]: value };
        if (field === "heading") {
          sec.canonical_section = autoCanonicalizeHeading(value);
        }
        if (field === "content") {
          sec.word_count = (value.match(/\w+/g) || []).length;
        }
        return sec;
      })
    );
  };

  const handleMoveSection = (path, direction) => {
    setSections((prev) => moveAtPath(prev, path, direction));
  };

  const handleDeleteSection = (path) => {
    setSections((prev) => deleteAtPath(prev, path));
  };

  // Validation
  const validateForm = () => {
    const errors = {};
    if (!projectFields.title.trim()) errors.title = "Title is required.";
    if (!projectFields.batch || !/^\d{3}$/.test(projectFields.batch)) {
      errors.batch = "Batch must be exactly 3 digits (e.g. 078).";
    }
    if (!projectFields.department_name) errors.department_name = "Select a department.";

    const validAuthors = authors.filter((a) => a.full_name.trim());
    if (validAuthors.length === 0) errors.authors = "At least one author full name is required.";

    const authorNames = validAuthors.map((a) => a.full_name.trim().toLowerCase());
    const duplicates = authorNames.filter((item, index) => authorNames.indexOf(item) !== index);
    if (duplicates.length > 0) errors.authors = `Duplicate author names found: ${duplicates.join(", ")}`;

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Verify / Patch Payload
  const handleVerifyMetadata = async () => {
    // Guard against a second click landing while the first is still in
    // flight (the button is disabled too, but this closes the race).
    if (verifying || publishing) return;
    setSubmitError(null);
    if (!validateForm()) {
      setCurrentStep(1);
      return;
    }
    setVerifying(true);
    setVerifiedSuccess(false);

    try {
      const selectedDept = departments.find((d) => String(d.id) === String(departmentId));
      const selectedCamp = campuses.find((c) => String(c.id) === String(campusId));
      const selectedRG = researchGroups.find((rg) => String(rg.id) === String(researchGroupId));

      const updatedAuthors = authors
        .filter((a) => a.full_name.trim())
        .map((a, idx) => ({
          full_name: a.full_name.trim(),
          role: "Author",
          roll_number: a.roll_number.trim(),
          academic_level: a.academic_level || projectFields.academic_level,
          designation: "",
          display_order: idx + 1,
        }));

      const updatedSupervisors = selectedSupervisors
        .filter((s) => (typeof s === "string" ? s.trim() : s?.full_name?.trim()))
        .map((sObj, idx) => {
          const isObj = typeof sObj === "object" && sObj !== null;
          const name = isObj ? (sObj.full_name || "").trim() : sObj.trim();
          const title = isObj ? (sObj.title || "").trim() : "";
          const designation = isObj ? (sObj.designation || "").trim() : "";
          const matchedFac = facultyList.find((f) => f.full_name.toLowerCase() === name.toLowerCase());

          return {
            full_name: name,
            title: title || matchedFac?.title || "",
            designation: designation || matchedFac?.designation || "",
            role: "Supervisor",
            academic_level: "Faculty",
            display_order: updatedAuthors.length + idx + 1,
          };
        });

      // Exclude existing authors AND supervisors/co-supervisors so deleted supervisors are removed!
      const MANAGED_ROLES = new Set(["author", "supervisor", "co-supervisor", "co supervisor"]);
      const existingOtherPeople = (job.extracted_payload?.people_and_roles || []).filter(
        (p) => !MANAGED_ROLES.has((p.role || "").toLowerCase().trim())
      );

      const people_and_roles = [...updatedAuthors, ...updatedSupervisors, ...existingOtherPeople];

      const patchData = {
        _verified_by_admin: true,
        project_fields: {
          title: projectFields.title.trim(),
          project_type: projectFields.project_type,
          academic_level: projectFields.academic_level,
          batch: projectFields.batch,
          department_name: selectedDept ? selectedDept.name : projectFields.department_name,
          campus_name: selectedCamp ? selectedCamp.name : projectFields.campus_name,
          research_group_name: selectedRG ? selectedRG.name : projectFields.research_group_name,
          cluster: projectFields.cluster || null,
          supervisors: selectedSupervisors.map((s) =>
            typeof s === "string"
              ? s
              : { full_name: s.full_name, title: s.title || "", designation: s.designation || "" }
          ),
          repository_url: projectFields.repository_url.trim(),
          abstract: projectFields.abstract.trim(),
        },
        people_and_roles,
        keywords,
      };

      if (!skipSections) {
        patchData.project_sections = serializeSectionTree(sections);
      }

      // Tell the backend whether sections were skipped so it can set SECTIONS_PENDING
      patchData._sections_skipped = skipSections;

      await ingestionApi.patchJobPayload(id, patchData);
      await fetchJob();
      setVerifiedSuccess(true);
    } catch (err) {
      // Entered form data is untouched, so the admin can correct and retry.
      setSubmitError(err.message || "Saving the project failed.");
      setVerifiedSuccess(false);
    } finally {
      setVerifying(false);
    }
  };

  // Publish Project
  const handlePublishProject = async () => {
    if (publishing || verifying) return;
    setSubmitError(null);
    setPublishing(true);
    try {
      const res = await ingestionApi.publishJob(id);
      const publishedId = res.data?.project_id;
      // Land the admin on the published record rather than leaving them on
      // a form they have already submitted.
      if (publishedId) {
        navigate(`/projects/${publishedId}`, { replace: true });
        return;
      }
      await fetchJob();
      navigate("/admin/approvals", { replace: true });
    } catch (err) {
      setSubmitError(err.message || "Publishing the project failed.");
      setPublishing(false);
    }
  };

  const logPanel = showLogs && (
    <div className="w-full text-left border border-line-soft rounded-sm p-4 tnum text-xs max-h-64 overflow-y-auto bg-band">
      <p className="mb-2 text-xs font-semibold text-ink-3">Processing log</p>
      {logsLoading ? (
        <p className="flex items-center gap-2 text-ink-3">
          <FontAwesomeIcon icon={faSpinner} className="spin h-3 w-3" aria-hidden="true" />
          Loading the processing log…
        </p>
      ) : logsError ? (
        <p className="text-err">{logsError}</p>
      ) : logs.length === 0 ? (
        <p className="text-ink-3">No processing log entries yet.</p>
      ) : (
        logs.map((l) => (
          <div key={l.id} className="py-0.5 border-b border-line-soft/50 text-ink-2">
            <span className="text-primary">[{l.level}]</span> {l.message}
          </div>
        ))
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <FontAwesomeIcon icon={faSpinner} className="spin h-6 w-6 text-ink-3" />
        <p className="tnum text-sm text-ink-2">Loading submission details…</p>
      </div>
    );
  }

  if (error || !job) {
    return (
      <StatusSplash
        tone="error"
        icon={faCircleExclamation}
        eyebrow={`Submission #${id}`}
        title="Failed to load submission"
        description={error || "Submission not found."}
        actions={
          <Button as={Link} to="/admin/approvals" variant="secondary" size="md">
            Return to Submissions
          </Button>
        }
      />
    );
  }

  // State 1: PENDING or PROCESSING
  if (job.status === "PENDING" || job.status === "PROCESSING") {
    return (
      <StatusSplash
        tone="warning"
        icon={faSpinner}
        spin
        eyebrow={`Submission #${job.id} · ${job.status}`}
        title="Processing document text & structure"
        description={
          <>The repository system is processing <span className="font-semibold text-ink">{job.original_filename}</span>, organizing author details, and cataloging section text.</>
        }
        actions={
          <Button variant="secondary" size="md" onClick={handleFetchLogs}>
            {showLogs ? "Hide processing details" : "View processing details"}
          </Button>
        }
      >
        {logPanel}
      </StatusSplash>
    );
  }

  // State 2: FAILED
  if (job.status === "FAILED") {
    return (
      <StatusSplash
        tone="error"
        icon={faCircleExclamation}
        eyebrow={`Submission #${job.id} · Processing Error`}
        title="Document processing encountered an error"
        description={job.error_message || "Unable to extract content from the PDF file."}
        actions={
          <>
            <Button variant="secondary" size="md" onClick={handleFetchLogs}>
              {showLogs ? "Hide logs" : "View logs"}
            </Button>
            <Button as={Link} to="/admin/upload" variant="primary" size="md">Retry Upload</Button>
          </>
        }
      >
        {logPanel}
      </StatusSplash>
    );
  }

  // State 3: VERIFIED / Published — fully complete
  if (job.status === "VERIFIED" && job.published_project) {
    return (
      <StatusSplash
        tone="success"
        icon={faCheckCircle}
        eyebrow={`Submission #${job.id} · Published`}
        title="Project report published to repository catalog"
        description="This project has been verified and published into the academic repository catalog."
        actions={
          <Button as={Link} to={`/projects/${job.published_project}`} variant="primary" size="lg">
            <FontAwesomeIcon icon={faEye} /> View Published Project Page
          </Button>
        }
      />
    );
  }

  // State 3b: SECTIONS_PENDING — published but sections not yet added
  if (job.status === "SECTIONS_PENDING" && job.published_project && !editingSections) {
    return (
      <StatusSplash
        tone="warning"
        icon={faFileLines}
        eyebrow={`Submission #${job.id} · Sections Incomplete`}
        title="Project is live — section content pending"
        description={
          <><span className="font-semibold text-ink">{job.original_filename}</span> has been published to the repository catalog, but its section content has not yet been added. Add sections now to complete the record.</>
        }
        actions={
          <>
            <Button as={Link} to={`/projects/${job.published_project}`} variant="secondary" size="md">
              <FontAwesomeIcon icon={faEye} /> View Published Project
            </Button>
            <Button variant="gold" size="lg" onClick={() => { setEditingSections(true); setCurrentStep(4); }}>
              <FontAwesomeIcon icon={faFileLines} /> Add section content now
            </Button>
          </>
        }
      />
    );
  }

  // State 4: EXTRACTED — Guided 5-Step Form Stepper (with optional PDF Split View)
  const batchOptions = choices?.batch?.options || [
    "065", "066", "067", "068", "069", "070", "071", "072", "073", "074", "075", "076", "077", "078", "079", "080", "081", "082"
  ];
  const academicLevelChoices = choices?.academic_levels || [
    { value: "UG", label: "Undergraduate" },
    { value: "Masters", label: "Masters" },
    { value: "PhD", label: "Doctor of Philosophy" },
    { value: "Faculty", label: "Faculty" },
  ];
  const projectTypeChoices = choices?.project_types || [
    { value: "Major", label: "Major" },
    { value: "Minor", label: "Minor" },
    { value: "Thesis", label: "Thesis" },
    { value: "Faculty Project", label: "Faculty Project" },
    { value: "Research", label: "Research" },
  ];

  const STEPS = [
    { step: 1, label: "Details" },
    { step: 2, label: "Abstract" },
    { step: 3, label: "Keywords" },
    { step: 4, label: "Sections" },
    { step: 5, label: "Publish" },
  ];

  return (
    <div className="max-w-[1600px] mx-auto flex flex-col gap-6 py-2">
      {/* Header */}
      <div className="bg-white border border-line rounded-sm p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-3 flex-wrap">
            <StatusTag tone={job.status === "SECTIONS_PENDING" ? "warning" : "info"}>
              {job.status === "SECTIONS_PENDING" ? "Sections incomplete" : "Document verification"}
            </StatusTag>
            <span className="text-xs font-semibold text-ink-3">Submission <span className="tnum">#{job.id}</span></span>
          </div>
          <h2 className="text-section leading-tight">{job.original_filename}</h2>
          <p className="tnum text-xs font-medium text-ink-2 mt-0.5">
            Uploaded by {job.uploaded_by_email || "Admin"} · {new Date(job.created_at).toLocaleDateString()}
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {job.file && (
            <button
              type="button"
              onClick={() => setShowPdf(!showPdf)}
              className={`px-3 py-2 rounded-sm border text-sm font-semibold transition-colors flex items-center gap-2 cursor-pointer ${
                showPdf ? "border-primary text-primary bg-primary-050" : "border-line text-ink-2 hover:text-ink hover:border-line-strong"
              }`}
            >
              <FontAwesomeIcon icon={faColumns} className="h-3.5 w-3.5" />
              {showPdf ? "Hide PDF" : "Show PDF"}
            </button>
          )}
          <Button variant="secondary" size="sm" onClick={handleFetchLogs}>
            <FontAwesomeIcon icon={faClock} className="h-3.5 w-3.5" />
            {showLogs ? "Hide logs" : "Logs"}
          </Button>
        </div>
      </div>

      {logPanel}

      {/* Stepper — numbered index + label, the current step marked by a
          primary line beneath it and a recessed white ground. */}
      <div className="flex items-stretch bg-white border border-line rounded-sm overflow-hidden">
        {STEPS.map((s) => (
          <button
            key={s.step}
            onClick={() => setCurrentStep(s.step)}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-3.5 border-b-[3px] transition-colors cursor-pointer ${
              currentStep === s.step
                ? "border-b-primary bg-band text-ink"
                : "border-b-transparent text-ink-2 hover:bg-band hover:text-ink"
            }`}
          >
            <span className={`tnum text-xs font-bold shrink-0 ${currentStep === s.step ? "text-primary" : "text-ink-3"}`}>
              {String(s.step).padStart(2, "0")}
            </span>
            <span className={`text-sm truncate ${currentStep === s.step ? "font-bold" : "font-semibold"}`}>{s.label}</span>
          </button>
        ))}
      </div>

      {/* Main split-screen / full-width container */}
      <div className={`grid grid-cols-1 ${showPdf && job.file ? "lg:grid-cols-12" : ""} gap-6 items-start`}>
        {showPdf && job.file && (
          <div className="lg:col-span-6 sticky top-[88px] bg-white border border-line rounded-sm overflow-hidden h-[calc(100vh-140px)] flex flex-col">
            <div className="bg-band px-4 py-2.5 border-b border-line flex items-center justify-between">
              <span className="flex items-center gap-2 text-xs font-semibold text-ink-2">
                <FontAwesomeIcon icon={faFilePdf} className="text-err h-3.5 w-3.5" />
                Original Document
              </span>
              <a href={job.file} target="_blank" rel="noreferrer" className="tnum text-xs font-bold text-primary hover:underline">
                Open in Full Window ↗
              </a>
            </div>
            <iframe src={job.file} className="w-full h-full border-0" title="PDF Document Viewer" />
          </div>
        )}

        <div className={showPdf && job.file ? "lg:col-span-6 flex flex-col gap-6 lg:overflow-y-auto lg:max-h-[calc(100vh-140px)] lg:pr-1" : "flex flex-col gap-6 max-w-4xl mx-auto w-full"}>
          {/* Step 1: Project Information */}
          {currentStep === 1 && (
            <div className="bg-white border border-line rounded-sm p-6 flex flex-col gap-6">
              <div className="flex items-baseline gap-3 border-b border-line-soft pb-3">
                <span className="tnum text-sm font-semibold text-primary tabular-nums">01</span>
                <h3 className="text-item">General information</h3>
              </div>

              {/* Title is the primary identifier of this record — it
                  gets its own row and real typographic weight, distinct
                  from the secondary metadata fields below it. */}
              <div className="flex flex-col gap-2">
                <label className={FIELD_LABEL}>
                  Project Title <span className="text-err">*</span>
                </label>
                <input
                  type="text"
                  value={projectFields.title}
                  onChange={(e) => setProjectFields({ ...projectFields, title: e.target.value })}
                  className="px-0 py-2 bg-transparent border-0 border-b-2 border-line text-ink font-bold text-item focus:outline-none focus:border-primary transition-colors"
                  placeholder="Enter complete project thesis title"
                />
                {validationErrors.title && <span className="tnum text-xs text-err">{validationErrors.title}</span>}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="flex flex-col gap-2">
                  <label className={FIELD_LABEL}>Project Category</label>
                  <select
                    value={projectFields.project_type}
                    onChange={(e) => setProjectFields({ ...projectFields, project_type: e.target.value })}
                    className={`${FIELD_INPUT} cursor-pointer`}
                  >
                    {projectTypeChoices.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-2">
                  <label className={FIELD_LABEL}>Academic Level</label>
                  <select
                    value={projectFields.academic_level}
                    onChange={(e) => setProjectFields({ ...projectFields, academic_level: e.target.value })}
                    className={`${FIELD_INPUT} cursor-pointer`}
                  >
                    {academicLevelChoices.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-2">
                  <label className={FIELD_LABEL}>Academic Batch</label>
                  <select
                    value={projectFields.batch}
                    onChange={(e) => setProjectFields({ ...projectFields, batch: e.target.value })}
                    className={`${FIELD_INPUT} cursor-pointer`}
                  >
                    {batchOptions.map((b) => (
                      <option key={b} value={b}>Batch {b}</option>
                    ))}
                  </select>
                  {validationErrors.batch && <span className="tnum text-xs text-err">{validationErrors.batch}</span>}
                </div>

                <div className="flex flex-col gap-2 md:col-span-2">
                  <label className={FIELD_LABEL}>
                    Department <span className="text-err">*</span>
                  </label>
                  <select
                    value={projectFields.department_name}
                    onChange={(e) =>
                      setProjectFields({ ...projectFields, department_name: e.target.value })
                    }
                    className={`${FIELD_INPUT} cursor-pointer`}
                  >
                    <option value="">— Select department —</option>
                    {departmentChoices.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                  {validationErrors.department_name ? (
                    <span className="text-xs text-err">{validationErrors.department_name}</span>
                  ) : (
                    <span className="text-xs text-ink-3">
                      {detectedDepartment
                        ? "Identified from the uploaded report — change it if that is wrong."
                        : "Could not be identified from the report; please select it."}
                    </span>
                  )}
                </div>

                <div className="flex flex-col gap-2">
                  <label className={FIELD_LABEL}>
                    Cluster <span className="font-normal text-ink-3">(optional)</span>
                  </label>
                  <select
                    value={projectFields.cluster}
                    onChange={(e) => setProjectFields({ ...projectFields, cluster: e.target.value })}
                    className={`${FIELD_INPUT} cursor-pointer`}
                  >
                    <option value="">Not specified</option>
                    {clusterChoices.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  {validationErrors.cluster && (
                    <span className="text-xs text-err">{validationErrors.cluster}</span>
                  )}
                </div>

                <div className="md:col-span-2 flex flex-col gap-2">
                  <label className={`${FIELD_LABEL} flex items-center gap-2`}>
                    <FontAwesomeIcon icon={faCodeBranch} className="h-3.5 w-3.5 text-ink-3" />
                    Repository URL
                  </label>
                  <input
                    type="url"
                    value={projectFields.repository_url}
                    onChange={(e) => setProjectFields({ ...projectFields, repository_url: e.target.value })}
                    className={`${FIELD_INPUT} tnum`}
                    placeholder="https://github.com/organization/repo"
                  />
                </div>
              </div>

              {/* Faculty Supervisors */}
              <div className="border-t border-line-soft pt-6 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <label className="text-base font-semibold text-ink flex items-center gap-2">
                    <FontAwesomeIcon icon={faGraduationCap} className="text-ink-3 h-4 w-4" />
                    Faculty Supervisors
                  </label>
                  <Button variant="secondary" size="sm" onClick={() => setShowAddFacultyModal(true)}>
                    <FontAwesomeIcon icon={faUserPlus} className="h-3.5 w-3.5" /> Add Faculty
                  </Button>
                </div>

                <div className="flex flex-wrap gap-2">
                  {selectedSupervisors.map((s, sIdx) => {
                    const isObj = typeof s === "object" && s !== null;
                    const name = isObj ? s.full_name : s;
                    const title = isObj && s.title ? `${s.title} ` : "";
                    const desig = isObj && s.designation ? ` (${s.designation})` : "";
                    const label = `${title}${name}${desig}`;

                    return (
                      <span
                        key={sIdx}
                        className="flex items-center gap-2 rounded-sm border border-line-strong bg-band px-3 py-1.5 text-sm text-ink"
                      >
                        <span>{label}</span>
                        <button
                          type="button"
                          onClick={() => setSelectedSupervisors(selectedSupervisors.filter((_, i) => i !== sIdx))}
                          className="text-ink-3 hover:text-err transition-colors cursor-pointer"
                        >
                          <FontAwesomeIcon icon={faXmark} className="h-3 w-3" />
                        </button>
                      </span>
                    );
                  })}
                  {selectedSupervisors.length === 0 && <p className="text-sm text-ink-3">No supervisors assigned yet.</p>}
                </div>

                <div className="flex flex-col gap-2 bg-band border border-line rounded-sm p-3">
                  <div className="relative">
                    <FontAwesomeIcon icon={faSearch} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3 text-xs" />
                    <input
                      type="text"
                      placeholder="Search faculty directory by name"
                      value={facultySearch}
                      onChange={(e) => setFacultySearch(e.target.value)}
                      className={`${FIELD_INPUT} w-full pl-8 py-1.5`}
                    />
                  </div>

                  <div className="max-h-40 overflow-y-auto flex flex-col gap-0.5 pr-1">
                    {searchedFaculty.map((f) => {
                      const isSel = selectedSupervisors.some((s) => {
                        const name = typeof s === "string" ? s : (s?.full_name || "");
                        return name.toLowerCase().trim() === f.full_name.toLowerCase().trim();
                      });

                      return (
                        <div
                          key={f.id}
                          onClick={() => {
                            if (isSel) {
                              setSelectedSupervisors(
                                selectedSupervisors.filter((s) => {
                                  const name = typeof s === "string" ? s : (s?.full_name || "");
                                  return name.toLowerCase().trim() !== f.full_name.toLowerCase().trim();
                                })
                              );
                            } else {
                              setSelectedSupervisors([
                                ...selectedSupervisors,
                                { full_name: f.full_name, title: f.title || "", designation: f.designation || "" },
                              ]);
                            }
                          }}
                          className={`px-2.5 py-1.5 rounded-sm text-sm cursor-pointer flex items-center justify-between transition-colors ${
                            isSel ? "bg-band text-ink font-medium" : "hover:bg-band text-ink-2"
                          }`}
                        >
                          <span>
                            {f.title ? `${f.title} ` : ""}{f.full_name}{" "}
                            <span className="text-xs text-ink-3 tnum">({f.designation || "Faculty"})</span>
                          </span>
                          {isSel && <FontAwesomeIcon icon={faCheckCircle} className="h-3.5 w-3.5 text-ink" />}
                        </div>
                      );
                    })}
                    {searchedFaculty.length === 0 && (
                      <p className="p-2 text-xs text-ink-3">
                        {facultySearch.trim()
                          ? `Nothing found for “${facultySearch.trim()}”. Use “Add Faculty” to register them.`
                          : "No faculty registered yet. Use “Add Faculty” to register one."}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Authors */}
              <div className="border-t border-line-soft pt-6 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <label className="text-base font-semibold text-ink flex items-center gap-2">
                    <FontAwesomeIcon icon={faGraduationCap} className="text-ink-3 h-4 w-4" />
                    Authors / Student Members <span className="text-err">*</span>
                  </label>
                  <Button variant="secondary" size="sm" onClick={handleAddAuthor}>
                    <FontAwesomeIcon icon={faPlus} className="h-3.5 w-3.5" /> Add Author
                  </Button>
                </div>

                {validationErrors.authors && <span className="tnum text-xs text-err">{validationErrors.authors}</span>}

                <div className="flex flex-col gap-2.5">
                  {authors.map((author, idx) => (
                    <div key={author.id || idx} className="bg-band border border-line rounded-sm p-3 flex flex-col sm:flex-row items-start sm:items-center gap-3">
                      <span className="tnum text-xs text-ink-3 w-6 shrink-0">#{idx + 1}</span>

                      <input
                        type="text"
                        placeholder="Full Name"
                        value={author.full_name}
                        onChange={(e) => handleAuthorChange(idx, "full_name", e.target.value)}
                        className={`${FIELD_INPUT} flex-1 py-1.5`}
                      />

                      <div className="flex items-center gap-2 w-full sm:w-auto">
                        <input
                          type="text"
                          placeholder="Roll (e.g. 075BCT001)"
                          value={author.roll_number}
                          onChange={(e) => handleAuthorChange(idx, "roll_number", e.target.value)}
                          className={`${FIELD_INPUT} w-36 py-1.5 tnum`}
                        />
                        <button
                          type="button"
                          title="Match Student DB"
                          onClick={() => handleMatchStudentByRoll(idx, author.roll_number)}
                          className="p-2 rounded-sm border border-line text-ink-2 hover:text-ink hover:border-line-strong transition-colors shrink-0 cursor-pointer"
                        >
                          <FontAwesomeIcon icon={faSearch} className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {author.matchedStudent && <StatusTag tone="success" className="shrink-0">DB Matched</StatusTag>}

                      <button
                        type="button"
                        onClick={() => handleRemoveAuthor(idx)}
                        disabled={authors.length <= 1}
                        className="p-2 text-ink-3 hover:text-err disabled:opacity-30 transition-colors shrink-0 cursor-pointer"
                      >
                        <FontAwesomeIcon icon={faTrash} className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Abstract */}
          {currentStep === 2 && (
            <div className="bg-white border border-line rounded-sm p-6 flex flex-col gap-6">
              <div className="flex items-baseline gap-3 border-b border-line-soft pb-3">
                <span className="tnum text-sm font-semibold text-primary tabular-nums">02</span>
                <h3 className="text-item">Abstract</h3>
              </div>

              <div className="flex flex-col gap-2">
                <div className="flex justify-between items-center">
                  <label className={FIELD_LABEL}>Abstract Content</label>
                  <span className="tnum text-xs text-ink-3">
                    {(projectFields.abstract.match(/\w+/g) || []).length} words · {projectFields.abstract.length} chars
                  </span>
                </div>
                <textarea
                  rows={14}
                  value={projectFields.abstract}
                  onChange={(e) => setProjectFields({ ...projectFields, abstract: e.target.value })}
                  className={`${FIELD_INPUT} leading-relaxed resize-y min-h-[320px]`}
                  placeholder="Paste or edit the full project abstract here…"
                />
              </div>
            </div>
          )}

          {/* Step 3: Keywords */}
          {currentStep === 3 && (
            <div className="bg-white border border-line rounded-sm p-6 flex flex-col gap-6">
              <div className="flex items-baseline gap-3 border-b border-line-soft pb-3">
                <span className="tnum text-sm font-semibold text-primary tabular-nums">03</span>
                <h3 className="text-item">Subject keywords</h3>
              </div>

              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newKeywordInput}
                    onChange={(e) => setNewKeywordInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddKeyword())}
                    placeholder="Enter keyword or technology tag (e.g. Deep Learning)"
                    className={`${FIELD_INPUT} flex-1`}
                  />
                  <Button variant="primary" size="md" onClick={handleAddKeyword}>Add Tag</Button>
                </div>

                <div className="flex flex-wrap gap-2 pt-1">
                  {keywords.map((kw, idx) => (
                    <span key={idx} className="flex items-center gap-2 rounded-sm border border-line-strong bg-band px-2.5 py-1 text-sm text-ink">
                      <span>{kw}</span>
                      <button type="button" onClick={() => handleRemoveKeyword(idx)} className="text-ink-3 hover:text-err transition-colors cursor-pointer">
                        <FontAwesomeIcon icon={faXmark} className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  {keywords.length === 0 && <p className="text-sm text-ink-3">No keywords added yet.</p>}
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Section Editor */}
          {currentStep === 4 && (
            <div className="bg-white border border-line rounded-sm p-6 flex flex-col gap-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-line pb-4">
                <div>
                  <div className="flex items-baseline gap-3">
                    <span className="tnum text-sm font-semibold text-primary tabular-nums">04</span>
                    <h3 className="text-item">Document sections</h3>
                  </div>
                  <p className="text-sm font-medium text-ink-2 mt-0.5">
                    Review section content. Heading canonicalization is computed automatically based on heading titles.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                  <label className="flex cursor-pointer items-center gap-2 whitespace-nowrap text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={skipSections}
                      onChange={(e) => setSkipSections(e.target.checked)}
                      className="cursor-pointer"
                    />
                    Skip section editing
                  </label>

                  {!skipSections && (
                    <Button variant="secondary" size="sm" onClick={handleAddSection}>
                      <FontAwesomeIcon icon={faPlus} className="h-3.5 w-3.5" /> Add section
                    </Button>
                  )}
                </div>
              </div>

              {skipSections ? (
                <div className="p-6 text-center border border-dashed border-line-soft rounded-sm">
                  <p className="text-base font-semibold text-ink">Section editing is currently skipped.</p>
                  <p className="text-sm text-ink-3 mt-1">
                    All extracted sections will be preserved exactly as extracted without any modifications.
                  </p>
                </div>
              ) : (
                // No inner max-height/scroller here: as flex items the cards
                // were shrinkable, so a list taller than 600px crushed every
                // card down to a few pixels. The page scrolls instead, and
                // each card is shrink-0 so it keeps its natural height.
                <div className="flex flex-col gap-4">
                  {sections.map((sec, idx) => (
                    <SectionEditorRow
                      key={idx}
                      node={sec}
                      path={[idx]}
                      isFirst={idx === 0}
                      isLast={idx === sections.length - 1}
                      depth={0}
                      onChange={handleSectionChange}
                      onMove={handleMoveSection}
                      onDelete={handleDeleteSection}
                      onAddChild={handleAddSubsection}
                      jobId={id}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 5: Review & Verify */}
          {currentStep === 5 && (
            <div className="bg-white border border-line rounded-sm p-6 flex flex-col gap-6">
              <div className="flex items-baseline gap-3 border-b border-line-soft pb-3">
                <span className="tnum text-sm font-semibold text-primary tabular-nums">05</span>
                <h3 className="text-item">Final Review & Publish</h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card variant="record" accent="bg-primary" className="flex flex-col gap-3 p-4">
                  <div className="flex justify-between items-center border-b border-line-soft pb-2">
                    <span className="text-sm font-semibold text-ink">Project Overview</span>
                    <button type="button" onClick={() => setCurrentStep(1)} className="tnum text-xs text-primary hover:underline cursor-pointer">
                      Edit
                    </button>
                  </div>
                  <p className="text-base font-semibold text-ink">{projectFields.title}</p>
                  <div className="grid grid-cols-2 gap-2 text-sm text-ink-2">
                    <div><span className="text-ink-3">Category</span> {projectFields.project_type}</div>
                    <div><span className="text-ink-3">Level</span> {projectFields.academic_level}</div>
                    <div><span className="text-ink-3">Batch</span> {projectFields.batch}</div>
                    <div>
                      <span className="text-ink-3">Department</span>{" "}
                      {departments.find((d) => String(d.id) === String(departmentId))?.name || projectFields.department_name}
                    </div>
                  </div>
                  <div className="text-sm text-ink-2">
                    <span className="text-ink-3">Supervisors </span>
                    {selectedSupervisors.length === 0
                      ? "None selected"
                      : selectedSupervisors
                        .map((s) => {
                          if (typeof s === "string") return s;
                          const titleStr = s?.title ? `${s.title} ` : "";
                          const desigStr = s?.designation ? ` (${s.designation})` : "";
                          return `${titleStr}${s?.full_name || "Unknown"}${desigStr}`;
                        })
                        .join(", ")}
                  </div>
                  <div className="text-sm text-ink-2">
                    <span className="text-ink-3">Authors </span>
                    {authors.filter((a) => a.full_name).map((a) => `${a.full_name} (${a.roll_number || "No roll"})`).join(", ")}
                  </div>
                </Card>

                <Card variant="record" accent="bg-primary" className="flex flex-col gap-3 p-4">
                  <div className="flex justify-between items-center border-b border-line-soft pb-2">
                    <span className="text-sm font-semibold text-ink">Abstract & Keywords</span>
                    <button type="button" onClick={() => setCurrentStep(2)} className="tnum text-xs text-primary hover:underline cursor-pointer">
                      Edit
                    </button>
                  </div>
                  <p className="text-sm text-ink-2 line-clamp-4 leading-relaxed">
                    {projectFields.abstract || "No abstract provided."}
                  </p>
                  <div className="flex flex-wrap gap-x-2.5 gap-y-1 tnum text-xs text-ink-2 mt-1">
                    {keywords.map((kw, i) => (
                      <span key={i}>{kw}</span>
                    ))}
                  </div>
                </Card>
              </div>

              <Card variant="record" accent="bg-ok" className="flex flex-col gap-2 p-4">
                <div className="flex justify-between items-center border-b border-line-soft pb-2">
                  <span className="text-sm font-semibold text-ink">Sections Summary</span>
                  <button type="button" onClick={() => setCurrentStep(4)} className="tnum text-xs text-primary hover:underline cursor-pointer">
                    Edit
                  </button>
                </div>
                {skipSections ? (
                  <p className="text-sm text-ink-3">Original sections preserved (skipped editing).</p>
                ) : (
                  <div className="flex flex-col divide-y divide-line-soft">
                    {flattenForSummary(sections).map((s, idx) => (
                      <div
                        key={idx}
                        style={s.depth > 0 ? { marginLeft: s.depth * 16 } : undefined}
                        className="py-2 flex items-baseline gap-2 text-sm"
                      >
                        <span className="tnum text-xs text-ink-3 shrink-0">#{s.numbering}</span>
                        <span className="text-ink font-medium">{s.heading}</span>
                        <span className="tnum text-xs text-ink-3">({s.canonical_section || "Introduction"})</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Verification & Publication Action Bar */}
              {submitError && (
                <ErrorNotice
                  title="The project could not be saved"
                  detail={submitError}
                  className="mt-4"
                />
              )}

              {Object.keys(validationErrors).length > 0 && (
                <ErrorNotice
                  title="Some details still need attention"
                  detail={Object.values(validationErrors).join(" ")}
                  action={
                    <Button variant="secondary" size="sm" onClick={() => setCurrentStep(1)}>
                      Go to details
                    </Button>
                  }
                  className="mt-4"
                />
              )}

              <div className="border-t border-line-soft pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div>
                  {verifiedSuccess ? (
                    <StatusTag tone="ok">Saved and validated — ready to publish</StatusTag>
                  ) : (
                    <span className="text-sm text-ink-2">
                      Save and validate the details before publishing to the catalogue.
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <Button
                    variant="secondary"
                    size="lg"
                    onClick={handleVerifyMetadata}
                    disabled={verifying || publishing || verifiedSuccess}
                  >
                    {verifying && <Spinner />}
                    {verifying ? "Saving project…" : verifiedSuccess ? "Saved" : "Save and validate"}
                  </Button>

                  <Button
                    variant="primary"
                    size="lg"
                    onClick={handlePublishProject}
                    disabled={!verifiedSuccess || publishing || verifying}
                  >
                    {publishing && <Spinner />}
                    {publishing
                      ? "Publishing…"
                      : job.status === "SECTIONS_PENDING"
                        ? "Update sections"
                        : "Publish to repository"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Stepper Footer Controls */}
          <div className="flex items-center justify-between border-t border-line-soft pt-6">
            <Button variant="ghost" size="md" onClick={() => setCurrentStep((s) => Math.max(1, s - 1))} disabled={currentStep === 1}>
              <FontAwesomeIcon icon={faChevronLeft} className="h-3.5 w-3.5" /> Previous Step
            </Button>

            <span className="tnum text-xs text-ink-3">Step {currentStep} of 5</span>

            <Button variant="primary" size="md" onClick={() => setCurrentStep((s) => Math.min(5, s + 1))} disabled={currentStep === 5}>
              Next Step <FontAwesomeIcon icon={faChevronRight} className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* Add Faculty — now the shared Dialog primitive, so it has real
          dialog semantics, closes on Escape, traps Tab inside itself and
          returns focus to the control that opened it. The hand-rolled
          overlay this replaced did none of that. */}
      <Dialog
        open={showAddFacultyModal}
        onClose={() => setShowAddFacultyModal(false)}
        title="Add a faculty member"
        description="Creates a faculty record and selects it for this project."
        width="max-w-md"
        footer={
          <>
            <Button type="button" variant="secondary" onClick={() => setShowAddFacultyModal(false)}>
              Cancel
            </Button>
            <Button type="submit" form="add-faculty-form" variant="primary" disabled={creatingFaculty}>
              {creatingFaculty ? "Saving…" : "Create and select"}
            </Button>
          </>
        }
      >
        <form id="add-faculty-form" onSubmit={handleCreateFaculty} className="flex flex-col gap-4">
          <div className="flex gap-3">
            <div className="w-28 flex flex-col gap-1.5">
              <label htmlFor="faculty-title" className="text-xs font-semibold text-ink-2">Title</label>
              <input
                id="faculty-title"
                type="text"
                value={newFaculty.title}
                onChange={(e) => setNewFaculty({ ...newFaculty, title: e.target.value })}
                className={FIELD_INPUT}
                placeholder="Dr."
              />
            </div>
            <div className="flex-1 flex flex-col gap-1.5">
              <label htmlFor="faculty-name" className="text-xs font-semibold text-ink-2">
                Full name <span className="text-err">*</span>
              </label>
              <input
                id="faculty-name"
                type="text"
                required
                value={newFaculty.full_name}
                onChange={(e) => setNewFaculty({ ...newFaculty, full_name: e.target.value })}
                className={FIELD_INPUT}
                placeholder="e.g. Rajiv Gupta"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="faculty-designation" className="text-xs font-semibold text-ink-2">Designation</label>
            <input
              id="faculty-designation"
              type="text"
              value={newFaculty.designation}
              onChange={(e) => setNewFaculty({ ...newFaculty, designation: e.target.value })}
              className={FIELD_INPUT}
              placeholder="e.g. Associate Professor"
            />
          </div>
        </form>
      </Dialog>
    </div>
  );
}
