"""
Nested document-tree reconstruction.

Replaces the previous flat, alias-gated section scan. A heading is accepted
purely on its confidence score (see heading_scoring.py), and its place in
the tree is resolved with a stack of currently-open sections -- the same
way a person outlining a document by hand would: a new heading either opens
a sibling at its own level, a child of whatever is currently deepest open,
or closes deeper levels back up to its own level. Numbering depth ("2.3.1"
-> level 3) is used when present; font-size clustering relative to whatever
is currently open is used when it is not. A heading whose level would leave
an impossible gap (e.g. a level-3 heading with no level-2 open) is clamped
to the deepest legal level rather than orphaned, and the clamp is recorded
as a processing warning so it surfaces in the QA JSON instead of silently
reshaping the document.

Back-matter (References / Appendices) detection and footer/TOC line
filtering are shared with metadata_sections.py's public API so both stay in
agreement about what counts as body content on a "content" page.
"""

import re

from ingestion.pipeline.utils.heading_scoring import (
    HEADING_CONFIDENCE_THRESHOLD,
    UNNUMBERED_HEADING_CONFIDENCE_THRESHOLD,
    score_heading_candidate,
)
from ingestion.pipeline.utils.text_cleaners import (
    TOC_ENTRY,
    TOC_LEADER,
    canonicalize_heading,
    normalize_line,
)

# A standalone footer page number -- a lone "4", "23", etc., optionally
# decorated with a single dash/pipe/bullet on either side ("- 4 -"). Only
# ever treated as a footer when it is the LAST rendered line on its page, so
# a numbered heading or a number that's genuinely part of body content is
# never affected.
FOOTER_PAGE_NUMBER = re.compile(r"^[-–—|•]?\s*\d{1,4}\s*[-–—|•]?$")


def last_nonempty_line_index(lines):
    last = None
    for idx, line in enumerate(lines):
        if normalize_line(line.get("text", "")):
            last = idx
    return last


def first_nonempty_line_index(lines):
    for idx, line in enumerate(lines):
        if normalize_line(line.get("text", "")):
            return idx
    return None


def detect_running_lines(pages):
    """Finds lines that recur as the first-or-last rendered line across many
    different pages of the SAME document -- the general signature of a
    running header/footer, independent of its wording. FOOTER_PAGE_NUMBER
    (above) already handles a bare page number, but that changes on every
    page by definition and could never be caught by exact-text repetition;
    this catches the complementary case -- constant TEXT repeated on every
    page (an institution name, a document title, a confidentiality notice)
    -- without needing to know its wording in advance. A line only counts
    once per page (not once per occurrence), so this can't be tripped by a
    body sentence that coincidentally repeats a couple of times."""
    content_pages = [p for p in pages if p.get("page_type") == "content"]
    if len(content_pages) < 4:
        return set()  # too few pages for frequency to mean anything

    counts = {}
    for page in content_pages:
        lines = page.get("lines", [])
        first_idx = first_nonempty_line_index(lines)
        last_idx = last_nonempty_line_index(lines)
        candidates = set()
        for idx in (first_idx, last_idx):
            if idx is None:
                continue
            text = normalize_line(lines[idx].get("text", ""))
            if text and 0 < len(text) <= 80 and not FOOTER_PAGE_NUMBER.match(text):
                candidates.add(text)
        for text in candidates:
            counts[text] = counts.get(text, 0) + 1

    threshold = max(4, round(len(content_pages) * 0.3))
    return {text for text, n in counts.items() if n >= threshold}


def content_body_font_size(pages):
    sizes = sorted(
        float(line.get("font_size") or 0)
        for page in pages
        if page.get("page_type") == "content"
        for line in page.get("lines", [])
        if normalize_line(line.get("text", ""))
        and not line.get("is_bold", False)
        and float(line.get("font_size") or 0) > 0
    )
    return sizes[len(sizes) // 2] if sizes else 10.0


def content_pages_with_toc_guard(pages):
    """Yields "content"-classified pages, skipping any that are still really
    the tail of the Table of Contents (dot-leader rows) even though page
    classification already moved past the ToC's own title page."""
    in_toc_sequence = False
    for page in pages:
        if page.get("page_type") == "toc":
            in_toc_sequence = True
            continue
        dot_leader_count = sum(
            bool(TOC_LEADER.search(normalize_line(line.get("text", ""))))
            for line in page.get("lines", [])
        )
        if in_toc_sequence and dot_leader_count:
            continue
        if page.get("page_type") == "content":
            in_toc_sequence = False
            yield page


def back_matter_kind(text: str):
    """Return "references" / "appendices" if `text` is a back-matter
    heading, else None. Shared verbatim with the previous implementation's
    matching rules so back-matter detection behavior doesn't change."""
    normalized = normalize_line(text).lower()
    normalized = re.sub(r"^chapter\s+(?:[ivxlcdm]+|\d+)\b[\s.:\-]*", "", normalized)
    normalized = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", normalized)
    if normalized in {"reference", "references", "bibliography"}:
        return "references"
    if re.match(
        r"^(?:appendices?|appendix\s*:\s*.*|appendix\s+(?:[a-z]|\d+|[ivxlcdm]+)(?:\s*:\s*.*)?)$",
        normalized,
    ):
        return "appendices"
    return None


def _new_node(text, numbering, level, page_num, canonical_hint, semantic_role, confidence, signals, display_order):
    return {
        "heading": text,
        "numbering": ".".join(str(p) for p in numbering) if numbering else None,
        "canonical_section": canonicalize_heading(text, canonical_hint),
        "semantic_role": semantic_role,
        "heading_level": level,
        "confidence": confidence,
        "signals": signals,
        "display_order": display_order,
        "page_start": page_num,
        "page_end": page_num,
        "content": "",
        "children": [],
        "_font_size": 0.0,  # internal bookkeeping, stripped before output
    }


def _font_based_level(font_size, stack):
    """For an unnumbered heading: how many currently-open ancestors render
    visually larger than this one? That count (+1) is this heading's level
    -- a heading the same size as what's already open is a sibling; a
    clearly smaller one is a child; one bigger than everything open starts
    a fresh chain back at level 1 (enforced by the caller's clamp)."""
    level = 1
    for lvl, node in stack:
        if node["_font_size"] > font_size + 0.5:
            level = lvl + 1
    return level


def _resolve_level(candidate, stack, warnings):
    if candidate.level_hint is not None:
        level = candidate.level_hint
    else:
        level = _font_based_level(candidate.font_size, stack)

    max_allowed = (stack[-1][0] + 1) if stack else 1
    if level > max_allowed:
        warnings.append(
            f"Heading \"{candidate.text}\" implied level {level} with no level "
            f"{max_allowed} section currently open -- demoted to level {max_allowed}."
        )
        level = max_allowed
    return max(1, level)


def _attach(node, level, stack, root):
    while stack and stack[-1][0] >= level:
        stack.pop()
    if stack:
        parent = stack[-1][1]
        node["display_order"] = len(parent["children"]) + 1
        parent["children"].append(node)
    else:
        node["display_order"] = len(root) + 1
        root.append(node)
    stack.append((level, node))


def _finalize(nodes):
    """Bottom-up cleanup: strips internal bookkeeping, computes word counts,
    and widens each node's page_start/page_end to also cover its children --
    a parent's page range should reflect its whole subtree, not just
    whatever page happened to be current when its own heading was seen."""
    for node in nodes:
        node.pop("_font_size", None)
        node["word_count"] = len(re.findall(r"\w+", node["content"]))
        _finalize(node["children"])
        for child in node["children"]:
            if child["page_start"] is not None:
                node["page_start"] = min(node["page_start"], child["page_start"]) if node["page_start"] is not None else child["page_start"]
            if child["page_end"] is not None:
                node["page_end"] = max(node["page_end"], child["page_end"]) if node["page_end"] is not None else child["page_end"]


# An unnumbered heading must at least be followed by some body text. This
# is a floor, not the main defence: a label and a short section can have
# bodies of similar length, so what actually separates them is the
# short-label penalty in heading_scoring (a one- or two-word unnumbered
# line with no recognised section name loses 0.30) plus artifact
# rejection. This rule only removes candidates followed by nothing at all.
_MIN_WORDS_UNDER_UNNUMBERED_HEADING = 4


def _decide_accepted_headings(stream):
    """Chooses which stream positions become headings.

    Numbering is the document's own statement of its structure and is
    trusted directly. Everything else has to earn it:

      * it must clear a much higher confidence bar, and
      * substantial body text must actually follow it before the next
        candidate, and
      * once a document has demonstrated that it numbers its headings,
        unnumbered candidates need a recognised section name as well --
        in a numbered report, a bold unnumbered line is far more likely to
        be a label inside a section than a section of its own.

    Returns a set of indices into `stream`.
    """
    numbered_positions = set()
    unnumbered_positions = []

    for position, entry in enumerate(stream):
        candidate = entry["candidate"]
        if candidate is None:
            continue
        if candidate.numbering is not None:
            if candidate.confidence >= HEADING_CONFIDENCE_THRESHOLD:
                numbered_positions.add(position)
        elif candidate.confidence >= UNNUMBERED_HEADING_CONFIDENCE_THRESHOLD:
            unnumbered_positions.append(position)

    # Does this document number its headings at all?
    document_is_numbered = len(numbered_positions) >= 3

    accepted = set(numbered_positions)
    boundaries = sorted(numbered_positions | set(unnumbered_positions))

    for position in unnumbered_positions:
        candidate = stream[position]["candidate"]

        if document_is_numbered and not candidate.signals.get("exact_alias"):
            # A numbered report that suddenly has an unnamed unnumbered
            # heading is almost always a label; leave it in the content.
            continue

        if candidate.signals.get("exact_alias"):
            # An EXACT match against a known section name ("Methodology",
            # "Conclusion") is strong evidence on its own. A fuzzy
            # near-miss is not, and still has to show real body text.
            accepted.add(position)
            continue

        # Novel wording has only typography behind it, so require that real
        # text actually follows before the next candidate.
        following = 0
        for later in range(position + 1, len(stream)):
            if later in boundaries and later != position:
                break
            following += len(stream[later]["text"].split())
        if following >= _MIN_WORDS_UNDER_UNNUMBERED_HEADING:
            accepted.add(position)

    return accepted


def build_section_tree(pages, warnings=None):
    """Builds the nested section tree for a document's "content" pages.

    `warnings` (a list, mutated in place if provided) collects human-
    readable notes about any hierarchy clamping performed, so a caller can
    surface them as `processing_warnings` without needing to re-derive them.
    """
    if warnings is None:
        warnings = []

    body_font_size = content_body_font_size(pages)
    running_lines = detect_running_lines(pages)
    root = []
    stack = []  # list[(level, node)], shallowest-open first
    in_back_matter = False

    # --- Pass 1: collect the body stream ------------------------------
    # Acceptance for an UNNUMBERED heading depends on what follows it (does
    # real body text come next, or another label?), which a per-line scorer
    # cannot see. So the document is flattened first, then decided.
    stream = []  # [{text, page_num, candidate}]
    for page in content_pages_with_toc_guard(pages):
        page_num = page.get("page_number", page.get("page_num", 1))
        lines = page.get("lines", [])
        first_idx = first_nonempty_line_index(lines)
        last_idx = last_nonempty_line_index(lines)

        for idx, line in enumerate(lines):
            text = normalize_line(line.get("text", ""))
            if not text or TOC_ENTRY.search(text):
                continue
            if idx == last_idx and FOOTER_PAGE_NUMBER.match(text):
                continue
            if idx in (first_idx, last_idx) and text in running_lines:
                continue
            stream.append({
                "text": text,
                "page_num": page_num,
                "candidate": score_heading_candidate(line, body_font_size),
            })

    accepted = _decide_accepted_headings(stream)

    # --- Pass 2: build the tree ---------------------------------------
    for position, entry in enumerate(stream):
        text = entry["text"]
        page_num = entry["page_num"]

        kind = back_matter_kind(text)
        if kind:
            in_back_matter = True
            stack = []
            continue
        if in_back_matter:
            continue

        candidate = entry["candidate"]
        if position in accepted:
            level = _resolve_level(candidate, stack, warnings)
            node = _new_node(
                candidate.text,
                candidate.numbering,
                level,
                page_num,
                candidate.canonical_hint,
                candidate.semantic_role,
                candidate.confidence,
                candidate.signals,
                display_order=None,
            )
            node["_font_size"] = candidate.font_size
            _attach(node, level, stack, root)
            continue

        # Not accepted as a heading -> body text, folded into whatever
        # section is currently deepest-open (this is the actual section
        # boundary: a section's content runs from its own heading to
        # the next accepted heading, full stop -- not to the next line
        # that happens to match a keyword).
        if stack:
            node = stack[-1][1]
            node["content"] += ("\n" if node["content"] else "") + text
            node["page_end"] = page_num
        else:
            # Content on a "content" page before any heading has been
            # recognized yet -- kept rather than silently dropped, so a
            # missed first heading shows up as a visible, reviewable
            # "Unsectioned Content" node instead of vanishing.
            if root and root[-1].get("heading") == "Unsectioned Content" and root[-1]["heading_level"] == 1:
                node = root[-1]
                node["content"] += ("\n" if node["content"] else "") + text
                node["page_end"] = page_num
            else:
                node = {
                    "heading": "Unsectioned Content",
                    "numbering": None,
                    "canonical_section": None,
                    "semantic_role": [],
                    "heading_level": 1,
                    "confidence": 0.0,
                    "signals": {"synthetic": True},
                    "display_order": len(root) + 1,
                    "page_start": page_num,
                    "page_end": page_num,
                    "content": text,
                    "children": [],
                    "_font_size": 0.0,
                }
                root.append(node)
                stack = [(1, node)]

    _finalize(root)
    return root
