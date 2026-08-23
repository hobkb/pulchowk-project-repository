#!/usr/bin/env python3
"""
Ingestion QA / validation tool (TEMPORARY, standalone -- see the extraction
architecture notes in ingestion/pipeline/utils/section_tree.py for context).

Independently scans the debug JSON produced by
`python manage.py extract_debug_json ...` (or any JSON matching the same
shape) and reports suspicious extraction problems. It never modifies the
JSON it reads, never "fixes" anything, and has no Django dependency -- it
is a plain, standalone Python script so it can be run directly:

    python validate_ingestion.py path/to/project.json
    python validate_ingestion.py path/to/project.json --verbose
    python validate_ingestion.py path/to/ingestion_json_dir/

The goal is to surface RECURRING patterns across many documents so the
actual extraction pipeline can be improved -- not to certify any single
document as "correct". A document with unusual but genuine structure is
expected to produce some findings; that is a prompt to look, not proof of
a bug.

CONFIDENTIALITY: this tool's entire output -- both per-file reports and the
batch summary -- is designed to never contain any real extracted text.
Sections are identified by a purely positional address ("1", "1.2", "1.2.3"
-- the 1-based sibling index at each tree level), never by their actual
heading. People are identified by role and index ("Author #2", "Supervisor
candidate #1"), never by name. Repeated-line and leakage findings describe
what was found (word counts, category names from a small fixed vocabulary,
counts, confidence scores) without ever quoting the line or section content
itself. This means the ENTIRE terminal output of this script is safe to
paste anywhere -- including directly into a chat with an AI assistant --
without redacting anything: cross-reference an address like "3.2" against
your own copy of the JSON file to see what it actually is.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


@dataclass
class Finding:
    severity: str  # HIGH / MEDIUM / LOW
    category: str
    message: str


@dataclass
class FileReport:
    path: Path
    findings: list = field(default_factory=list)
    metadata_checks: list = field(default_factory=list)   # (label, ok: bool, note: str|None)
    section_checks: list = field(default_factory=list)    # (label, ok: bool, note: str|None)
    error: str | None = None

    def add(self, severity, category, message):
        self.findings.append(Finding(severity, category, message))

    @property
    def verdict(self):
        if self.error:
            return "ERROR"
        if any(f.severity == "HIGH" for f in self.findings):
            return "SEVERE"
        if self.findings:
            return "NEEDS_REVIEW"
        return "PASS"


# ---------------------------------------------------------------------
# Shape helpers
# ---------------------------------------------------------------------

REQUIRED_TOP_KEYS = {"metadata", "sections"}
EXPECTED_SECTION_KEYS = {"heading", "heading_level", "content", "children"}

WORD_RE = re.compile(r"\w+")
FOOTER_NUMBER_RE = re.compile(r"^[-–—|•]?\s*\d{1,4}\s*[-–—|•]?$")
# A bare numeric/percentage table-cell value ("34.92", "-1", "78%", "1,024")
# -- these recur across result tables in a technical report as a matter of
# course and are never a running header/footer.
TABLE_VALUE_RE = re.compile(r"^[-+]?[\d,]+(\.\d+)?%?$")

# Deliberately small, category-level keyword sets used ONLY as a QA signal
# for possible section-content leakage -- flags a MISMATCH between a
# section's own declared topic and what its body text actually reads like,
# never used to decide what a section's heading IS (that stays the
# pipeline's job, not this validator's).
TOPIC_KEYWORDS = {
    "introduction": ["motivation", "objective", "problem statement", "scope of", "background of the"],
    "literature_review": ["prior work", "existing system", "related work", "previous stud", "literature", "researchers have"],
    "methodology": ["proposed method", "we propose", "algorithm", "methodology", "system architecture", "block diagram"],
    "implementation": ["implemented using", "was developed", "source code", "module was", "deployed on"],
    "results": ["we obtained", "accuracy of", "we surveyed", "respondents", "results show", "table shows", "figure shows", "performance of"],
    "discussion": ["in contrast to", "this suggests", "compared to", "one possible explanation"],
    "conclusion": ["in conclusion", "to conclude", "future work", "we conclude", "this project has"],
}


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def flatten_sections(sections, prefix=""):
    """Yields (address, node, depth) for every node in the tree, depth-first,
    in document order. `address` is a purely positional label ("1", "1.2",
    "1.2.3") -- the 1-based sibling index at each level -- and NEVER the
    node's actual heading text. Every check below identifies a specific
    section by this address alone, so a finding can always be traced back
    to an exact place in your own copy of the JSON without this tool ever
    needing to print, and you never needing to redact, any real extracted
    content."""
    for idx, node in enumerate(sections, start=1):
        address = f"{prefix}{idx}"
        depth = address.count(".") + 1
        yield address, node, depth
        children = node.get("children") or []
        if children:
            yield from flatten_sections(children, prefix=f"{address}.")


# ---------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------

def check_json_structure(data, report: FileReport):
    if not isinstance(data, dict):
        report.add("HIGH", "structure", "Top-level JSON is not an object.")
        return

    missing = REQUIRED_TOP_KEYS - set(data.keys())
    if missing:
        report.add("HIGH", "structure", f"Missing required top-level key(s): {sorted(missing)}.")

    sections = data.get("sections")
    if sections is not None and not isinstance(sections, list):
        report.add("HIGH", "structure", "`sections` is present but not a list.")
        return

    def _check_node(node, where):
        if not isinstance(node, dict):
            report.add("HIGH", "structure", f"Section node at {where} is not an object.")
            return
        missing_keys = EXPECTED_SECTION_KEYS - set(node.keys())
        if missing_keys:
            report.add("MEDIUM", "structure", f"Section node at {where} is missing key(s): {sorted(missing_keys)}.")
        children = node.get("children")
        if children is not None and not isinstance(children, list):
            report.add("HIGH", "structure", f"`children` at {where} is not a list.")
            return
        level = node.get("heading_level")
        if level is not None and not isinstance(level, int):
            report.add("MEDIUM", "structure", f"`heading_level` at {where} is not an integer ({level!r}).")
        for i, child in enumerate(children or []):
            _check_node(child, f"{where} > child[{i}]")

    for i, node in enumerate(sections or []):
        _check_node(node, f"sections[{i}]")


def check_metadata_completeness(data, report: FileReport):
    meta = data.get("metadata") or {}
    fields = [
        ("title", meta.get("title")),
        ("abstract", meta.get("abstract")),
        ("department_name", meta.get("department_name")),
        ("academic_level", meta.get("academic_level")),
        ("batch", meta.get("batch")),
    ]
    for label, value in fields:
        present = bool(value and str(value).strip())
        report.metadata_checks.append((label.replace("_", " ").title(), present, None))
        if not present:
            # Missing metadata is common and often legitimate (not every
            # report states a research group, for instance) -- LOW, a
            # prompt to look rather than an assumed defect.
            report.add("LOW", "metadata", f"{label} is missing or empty.")

    people = data.get("people_and_roles") or []
    authors = [p for p in people if (p.get("role") or "").lower() == "author"]
    supervisors = [p for p in people if "supervisor" in (p.get("role") or "").lower()]
    report.metadata_checks.append((f"Authors ({len(authors)})", bool(authors), None))
    report.metadata_checks.append((
        f"Supervisor ({len(supervisors)})" if supervisors else "Supervisor",
        bool(supervisors),
        None,
    ))
    sections = data.get("sections") or []
    report.metadata_checks.append((f"Sections ({len(sections)} top-level)", bool(sections), None))

    if not authors:
        report.add("HIGH", "authors", "No authors were extracted at all.")
    if not supervisors:
        report.add("LOW", "supervisor", "No supervisor was extracted -- may be legitimate (e.g. a faculty-only project), or an extraction miss; check the source PDF.")
    if not sections:
        report.add("HIGH", "sections", "No sections were extracted at all -- likely an extraction failure, not a real empty document.")


def check_title(data, report: FileReport):
    title = (data.get("metadata") or {}).get("title")
    if not title:
        return  # already flagged by completeness check
    words = title.split()
    if len(words) < 2:
        report.add("MEDIUM", "title", f"Title is suspiciously short ({len(words)} word(s)): {word_count(title)} words.")
    if len(title) > 200:
        report.add("MEDIUM", "title", "Title is suspiciously long -- may have absorbed body text or an adjacent line.")
    if FOOTER_NUMBER_RE.match(title.strip()):
        report.add("HIGH", "title", "Title looks like a bare page-number artifact, not a real title.")


def check_authors(data, report: FileReport):
    people = data.get("people_and_roles") or []
    authors = [p for p in people if (p.get("role") or "").lower() == "author"]
    if not authors:
        return  # already flagged

    if len(authors) > 8:
        report.add("MEDIUM", "authors", f"Unusually many authors ({len(authors)}) -- check for author/body-text confusion.")

    seen_names = set()
    for i, a in enumerate(authors, start=1):
        name = (a.get("full_name") or "").strip()
        if not name:
            report.add("MEDIUM", "authors", f"Author #{i} has an empty name.")
            continue
        if len(name) > 60:
            report.add("MEDIUM", "authors", f"Author #{i}'s name is suspiciously long ({len(name)} chars) -- may contain body text.")
        if word_count(name) > 6:
            report.add("MEDIUM", "authors", f"Author #{i}'s name has an unusually high word count ({word_count(name)}) for a person's name.")
        key = name.lower()
        if key in seen_names:
            report.add("LOW", "authors", f"Author #{i} duplicates another author's name.")
        seen_names.add(key)

    supervisors = {(p.get("full_name") or "").strip().lower() for p in people if "supervisor" in (p.get("role") or "").lower()}
    if seen_names & supervisors:
        report.add("HIGH", "authors", "At least one person appears as both an author and a supervisor -- likely role confusion.")


def check_supervisor(data, report: FileReport):
    people = data.get("people_and_roles") or []
    supervisors = [p for p in people if "supervisor" in (p.get("role") or "").lower()]
    if not supervisors:
        return  # absence already flagged at LOW by completeness check; a
        # genuinely supervisor-less document (e.g. a faculty project) is
        # not necessarily wrong.

    if len(supervisors) > 3:
        report.add("MEDIUM", "supervisor", f"Unusually many supervisor/co-supervisor entries ({len(supervisors)}).")

    for i, s in enumerate(supervisors, start=1):
        name = (s.get("full_name") or "").strip()
        if not name:
            report.add("HIGH", "supervisor", f"Supervisor candidate #{i} has an empty name.")
            continue
        if word_count(name) > 5:
            report.add("HIGH", "supervisor", f"Supervisor candidate #{i}'s name reads like a sentence, not a name ({word_count(name)} words) -- likely extracted from surrounding prose rather than an actual name.")
        confidence = s.get("confidence")
        source = s.get("confidence_source")
        if confidence is not None and confidence < 0.7:
            note = f" (source: {source})" if source else ""
            report.add(
                "MEDIUM",
                "supervisor",
                f"Supervisor candidate #{i} was extracted with low confidence ({confidence}){note} -- "
                "verify it wasn't picked up from acknowledgement/thanks prose without real supervisory context.",
            )


def check_section_tree(data, report: FileReport):
    sections = data.get("sections") or []
    if not sections:
        return

    seen_headings_by_parent = {}

    for address, node, depth in flatten_sections(sections):
        heading = (node.get("heading") or "").strip()
        level = node.get("heading_level")
        content = node.get("content") or ""
        children = node.get("children") or []

        report.section_checks.append((address, True, None))

        if not heading:
            report.add("MEDIUM", "sections", f"Section {address} has no heading text.")

        parent_addr = address.rsplit(".", 1)[0] if "." in address else "root"
        seen = seen_headings_by_parent.setdefault(parent_addr, {})
        key = heading.lower()
        if key:
            if key in seen:
                # A duplicate among top-level sections (a whole page
                # processed twice, or a repeated running header promoted
                # to a heading) is a stronger signal than two same-titled
                # subsections under different chapters (e.g. each chapter
                # having its own "Summary"), which is common and benign.
                severity = "HIGH" if parent_addr == "root" else "MEDIUM"
                report.add(
                    severity, "sections",
                    f"Section {address} has the same heading as section {seen[key]} (same parent) -- possible duplicate extraction.",
                )
            else:
                seen[key] = address

        wc = word_count(content)
        if not content.strip() and not children:
            report.add("MEDIUM", "sections", f"Section {address} is completely empty (no content, no subsections).")
        elif 0 < wc < 8 and not children:
            report.add("LOW", "sections", f"Section {address} is unusually short ({wc} words) for a leaf section.")

        if isinstance(level, int) and level != depth:
            # Not necessarily wrong (level is set by the pipeline relative
            # to numbering/font clustering, depth is purely tree position)
            # -- but a mismatch here is worth a look since the two should
            # normally agree.
            report.add("LOW", "hierarchy", f"Section {address} has heading_level={level} but sits at tree depth {depth}.")


def check_page_number_artifacts(data, report: FileReport):
    sections = data.get("sections") or []
    for address, node, _depth in flatten_sections(sections):
        content = node.get("content") or ""
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        if lines and FOOTER_NUMBER_RE.match(lines[-1]):
            report.add(
                "LOW",
                "artifacts",
                f"Section {address} content ends with what looks like a bare page-footer number.",
            )

    # Repeated running header/footer: an identical short line recurring
    # verbatim across many different sections' content. Deliberately
    # conservative -- a table of comparison results (metric names, model
    # names, numeric values) legitimately repeats across several sections
    # of a technical report without being a header/footer artifact, so
    # table-cell-shaped lines (numeric, or too short to be an institutional
    # phrase) are excluded, and the section-count bar is set well above
    # what one shared table would produce. The line's own text is used
    # only internally to group matching occurrences -- never printed.
    line_to_sections = {}
    for address, node, _depth in flatten_sections(sections):
        content = node.get("content") or ""
        for line in {l.strip() for l in content.split("\n") if l.strip()}:
            if not (0 < len(line) <= 80):
                continue
            if word_count(line) < 3:
                continue  # table column headers / single labels ("Engine", "Steps")
            if TABLE_VALUE_RE.match(line):
                continue  # numeric/percentage table cell
            line_to_sections.setdefault(line, set()).add(address)
    for line, addrs in line_to_sections.items():
        if len(addrs) >= 5:
            report.add(
                "LOW",
                "artifacts",
                f"The same {word_count(line)}-word line recurs verbatim across {len(addrs)} different sections "
                f"({', '.join(sorted(addrs))}) -- possible repeated header/footer leaking into content.",
            )


def check_section_leakage(data, report: FileReport):
    sections = data.get("sections") or []
    for address, node, _depth in flatten_sections(sections):
        content = (node.get("content") or "").lower()
        if word_count(content) < 15:
            continue  # too little text for a meaningful topic signal

        own_roles = set(node.get("semantic_role") or [])
        # canonical_section falls back to the heading's own wording when
        # nothing canonicalizes it (by design, in section_tree.py -- the
        # heading is never blanked out just because it's novel), so it is
        # NOT reliable evidence of a declared topic on its own; only count
        # it when it actually landed on one of this checker's known topics.
        own_canonical = (node.get("canonical_section") or "").lower().replace(" ", "_")
        own_topics = own_roles | ({own_canonical} if own_canonical else set())
        known_own_topics = own_topics & TOPIC_KEYWORDS.keys()
        if not known_own_topics:
            # No reliable baseline topic for this section (its heading is
            # specific/novel wording, which is expected and correct) --
            # nothing to meaningfully compare its content against.
            continue

        scores = {}
        for topic, keywords in TOPIC_KEYWORDS.items():
            hits = sum(content.count(kw) for kw in keywords)
            if hits:
                scores[topic] = hits

        if not scores:
            continue

        best_topic, best_hits = max(scores.items(), key=lambda kv: kv[1])
        if best_topic in known_own_topics or best_hits < 2:
            continue

        own_hits = max((scores.get(t, 0) for t in known_own_topics), default=0)
        if best_hits > own_hits:
            # best_topic/known_own_topics are always members of the fixed
            # TOPIC_KEYWORDS category vocabulary above, never text pulled
            # from the document itself, so naming them here is safe.
            confidence = round(min(0.95, 0.5 + 0.1 * (best_hits - own_hits)), 2)
            declared = "/".join(sorted(t.replace("_", " ") for t in known_own_topics))
            report.add(
                "MEDIUM",
                "leakage",
                f"Possible content leakage: section {address} (declared topic: {declared}) reads strongly like "
                f"\"{best_topic.replace('_', ' ')}\" content ({best_hits} keyword hit(s) vs {own_hits} for its "
                f"own declared topic), confidence={confidence}.",
            )


def check_processing_warnings(data, report: FileReport):
    # The pipeline's own warning strings embed real heading text (e.g.
    # "Heading \"X\" implied level 3 ... demoted to level 2"), so they're
    # aggregated into one count-only summary here rather than reported
    # verbatim -- this is the one signal in this tool that comes from the
    # pipeline itself rather than being computed fresh from the JSON.
    warnings = data.get("processing_warnings") or []
    if warnings:
        report.add(
            "MEDIUM",
            "hierarchy",
            f"The extraction pipeline recorded {len(warnings)} hierarchy-level demotion(s) during extraction "
            "(a heading's numbering implied a deeper level than was currently open, so it was demoted to the "
            "deepest legal level rather than left as an orphan). Often reflects the source PDF's own irregular "
            "numbering -- only worth a closer look if this count is unusually high relative to the section count.",
        )


CHECKS = [
    check_json_structure,
    check_metadata_completeness,
    check_title,
    check_authors,
    check_supervisor,
    check_section_tree,
    check_page_number_artifacts,
    check_section_leakage,
    check_processing_warnings,
]


def validate_file(path: Path) -> FileReport:
    report = FileReport(path=path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        report.error = f"Could not parse JSON: {exc}"
        return report

    for check in CHECKS:
        try:
            check(data, report)
        except Exception as exc:  # noqa: BLE001 -- one broken check must not abort the whole report
            report.add("MEDIUM", "validator", f"Check {check.__name__} raised an error: {exc}")

    report.findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 3))
    return report


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------

# Windows terminals commonly default to a legacy codepage (cp1252) that
# can't encode these glyphs, which would otherwise crash the very first
# print -- reconfigure stdout/stderr to UTF-8 where possible (Python 3.7+),
# and fall back to plain ASCII markers if that isn't available at all.
_UNICODE_MARKS = True
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        _UNICODE_MARKS = False


def _mark(ok: bool) -> str:
    if _UNICODE_MARKS:
        return "✓" if ok else "⚠"
    return "[OK]" if ok else "[!!]"


def print_report(report: FileReport, verbose: bool, index: int | None = None):
    print("=" * 50)
    print("INGESTION VALIDATION")
    print("=" * 50)
    # Deliberately never prints the source filename -- in a batch run that
    # can itself reveal a project's title/topic (e.g.
    # "Automated_Fare_Collection report.pdf"), which is exactly the kind of
    # content this tool exists to keep out of its own output. A positional
    # index is enough to let you refer back to "document #7" without
    # naming it.
    print(f"Document: #{index}" if index is not None else "Document")
    print()

    if report.error:
        print(f"ERROR: {report.error}")
        print()
        print(f"OVERALL: {report.verdict}")
        print("=" * 50)
        return

    print("METADATA")
    for label, ok, note in report.metadata_checks:
        line = f"{_mark(ok)} {label}"
        if note:
            line += f" -- {note}"
        print(line)
    print()

    if report.section_checks:
        print("SECTIONS")
        shown = report.section_checks if verbose else report.section_checks[:15]
        for label, ok, note in shown:
            print(f"{_mark(ok)} {label}")
        if not verbose and len(report.section_checks) > 15:
            print(f"  ... and {len(report.section_checks) - 15} more (use --verbose to show all)")
        print()

    if report.findings:
        print("POTENTIAL PROBLEMS")
        print()
        for f in report.findings:
            print(f"[{f.severity}] {f.category}:")
            print(f"       {f.message}")
            print()
    else:
        print("No issues detected by this validator.")
        print()

    print(f"OVERALL: {report.verdict}")
    print("=" * 50)


def print_batch_summary(reports: list):
    total = len(reports)
    passed = sum(1 for r in reports if r.verdict == "PASS")
    needs_review = sum(1 for r in reports if r.verdict == "NEEDS_REVIEW")
    severe = sum(1 for r in reports if r.verdict == "SEVERE")
    errored = sum(1 for r in reports if r.verdict == "ERROR")

    category_counts = {}
    for r in reports:
        for f in r.findings:
            category_counts[f.category] = category_counts.get(f.category, 0) + 1

    print()
    print("=" * 50)
    print("BATCH SUMMARY")
    print("=" * 50)
    print(f"Documents scanned: {total}")
    print()
    print(f"Passed:         {passed}")
    print(f"Needs review:   {needs_review}")
    print(f"Severe problems:{severe:>4}")
    if errored:
        print(f"Errored:        {errored}")
    print()

    if category_counts:
        print("Problems by category:")
        for cat, count in sorted(category_counts.items(), key=lambda kv: -kv[1]):
            print(f"  {cat}: {count}")
        print()

    flagged = [(i, r) for i, r in enumerate(reports, start=1) if r.verdict in ("NEEDS_REVIEW", "SEVERE", "ERROR")]
    if flagged:
        print("Documents requiring review:")
        for i, r in flagged:
            print(f"  [{r.verdict}] Document #{i}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Validate ingestion debug JSON for suspicious extraction problems.")
    parser.add_argument("path", help="A single JSON file, or a directory of JSON files.")
    parser.add_argument("--verbose", action="store_true", help="Show full section-by-section detail.")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Path does not exist: {target}", file=sys.stderr)
        sys.exit(2)

    if target.is_dir():
        json_files = sorted(target.glob("*.json"))
        if not json_files:
            print(f"No .json files found in {target}", file=sys.stderr)
            sys.exit(2)
        reports = [validate_file(p) for p in json_files]
        for i, r in enumerate(reports, start=1):
            print_report(r, verbose=args.verbose, index=i)
            print()
        print_batch_summary(reports)
        sys.exit(1 if any(r.verdict in ("SEVERE", "ERROR") for r in reports) else 0)
    else:
        report = validate_file(target)
        print_report(report, verbose=args.verbose)
        sys.exit(1 if report.verdict in ("SEVERE", "ERROR") else 0)


if __name__ == "__main__":
    main()
