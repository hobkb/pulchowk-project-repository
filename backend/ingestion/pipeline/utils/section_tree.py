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
from ingestion.pipeline.utils.toc_outline import (
    TocOutline,
    parse_toc_outline,
    split_numbered_heading,
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


def _clamp_level(level, stack, text, warnings):
    """Keeps a level from leaving an impossible gap in the tree.

    A level-3 heading with no level-2 section open would otherwise orphan
    itself. This happens under a ToC too, when the intermediate heading
    exists in the outline but was never found on the page (a scanned page,
    a heading rendered as an image); demoting is better than dropping.
    """
    max_allowed = (stack[-1][0] + 1) if stack else 1
    if level > max_allowed:
        warnings.append(
            f"Heading \"{text}\" implied level {level} with no level "
            f"{max_allowed} section currently open -- demoted to level {max_allowed}."
        )
        level = max_allowed
    return max(1, level)


def _resolve_level(candidate, stack, warnings):
    if candidate.level_hint is not None:
        level = candidate.level_hint
    else:
        level = _font_based_level(candidate.font_size, stack)

    return _clamp_level(level, stack, candidate.text, warnings)


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


def _looks_typographically_like_heading(candidate):
    """Set apart from body text -- bold, or noticeably larger, and shaped
    like a heading rather than a sentence.

    Deliberately NOT the confidence score. That score carries a 0.30
    penalty for a short unnumbered line, which exists to reject labels like
    "CPU" or "System Memory" when nothing else vouches for them. Here the
    ToC vouches for them: a two-word heading such as "Backend Development"
    scores 0.25 and would fail the confidence bar despite being listed in
    the ToC by name, which silently dropped real subsections into the body
    of the chapter above.
    """
    if candidate is None:
        return False
    signals = candidate.signals or {}
    if not signals.get("shape_ok"):
        return False
    return bool(signals.get("bold")) or float(signals.get("font_ratio") or 0) >= 1.15


def _collect_stream(pages, body_font_size, running_lines):
    """Flattens the body into one ordered list of lines, with each line's
    heading score attached. Acceptance of an unnumbered heading depends on
    what follows it, which a per-line scorer cannot see, so the document is
    flattened first and decided afterwards."""
    stream = []
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
    return stream


def _outline_skeleton(outline):
    """The tree the ToC describes, built before the body is read at all.

    A node's parent is its numbering prefix -- 5.3.4 belongs to 5.3, full
    stop. Deriving the parent from "whichever section happened to be open
    when this heading was found" is what put 5.3.4 underneath 5.1 when 5.3
    was never spotted on the page: the outline plainly said otherwise and
    was being overruled by the body scan.
    """
    root = []
    by_numbering = {}
    node_for = {}

    for entry in outline.entries:
        node = _new_node(
            entry["title"],
            entry["numbering"],
            1,                      # replaced below, once the parent is known
            None,
            None,
            [],
            1.0,
            {"from_toc": True},
            display_order=None,
        )
        node["_seen"] = False
        node_for[id(entry)] = node

        parent = None
        numbering = entry["numbering"]
        if numbering and len(numbering) > 1:
            # Nearest ancestor actually present in the ToC. A report that
            # lists 5 and 5.3.4 but no 5.3 still nests correctly under 5.
            for cut in range(len(numbering) - 1, 0, -1):
                parent = by_numbering.get(numbering[:cut])
                if parent is not None:
                    break

        if parent is None:
            node["heading_level"] = 1
            root.append(node)
        else:
            node["heading_level"] = parent["heading_level"] + 1
            parent["children"].append(node)

        if numbering:
            by_numbering.setdefault(numbering, node)

    return root, node_for


def _prune_unseen(nodes):
    """Drops outline entries never found in the body, keeping any that
    still have a descendant that was. A ToC lists sections a scanned or
    image-rendered page may not yield; an empty card for one of those is
    noise, but its parent must survive if a child was found."""
    kept = []
    for node in nodes:
        node["children"] = _prune_unseen(node["children"])
        if node["_seen"] or node["children"]:
            kept.append(node)
    return kept


def _renumber(nodes):
    for index, node in enumerate(nodes, start=1):
        node["display_order"] = index
        node.pop("_seen", None)
        _renumber(node["children"])


def _build_from_outline(stream, outline, accepted, warnings):
    """Pours the body into the outline's shape.

    The ToC decides the structure; the body only supplies text. A line is a
    heading when the outline names it -- anything else, numbered list items
    included, is content of whichever section is current. That is the whole
    rule.
    """
    root, node_for = _outline_skeleton(outline)

    current = None
    unsectioned = None
    in_back_matter = False

    for position, item in enumerate(stream):
        text = item["text"]
        page_num = item["page_num"]

        if back_matter_kind(text):
            in_back_matter = True
            current = None
            continue
        if in_back_matter:
            continue

        candidate = item["candidate"]
        numbering, title = split_numbered_heading(text)

        matched = outline.match(
            numbering, title, scored_as_heading=position in accepted
        )
        if (
            matched is None
            and numbering is None
            and _looks_typographically_like_heading(candidate)
        ):
            matched = outline.match_title(title)

        if matched is not None:
            node = node_for[id(matched)]
            node["_seen"] = True
            node["page_start"] = page_num
            node["page_end"] = page_num
            current = node
            continue

        if current is not None:
            current["content"] += ("\n" if current["content"] else "") + text
            current["page_end"] = page_num
        else:
            # Body text before the first outline heading was reached.
            if unsectioned is None:
                unsectioned = _new_node(
                    "Unsectioned Content", None, 1, page_num, None, [], 0.0,
                    {"synthetic": True}, display_order=None,
                )
                unsectioned["_seen"] = True
                root.insert(0, unsectioned)
            unsectioned["content"] += ("\n" if unsectioned["content"] else "") + text
            unsectioned["page_end"] = page_num

    root = _prune_unseen(root)
    _renumber(root)
    _finalize(root)
    return root


def _build_from_typography(stream, accepted, warnings):
    """The fallback for a report with no usable ToC: a heading is whatever
    the scorer accepted, placed with a stack of currently-open sections."""
    root = []
    stack = []
    in_back_matter = False

    for position, item in enumerate(stream):
        text = item["text"]
        page_num = item["page_num"]

        if back_matter_kind(text):
            in_back_matter = True
            stack = []
            continue
        if in_back_matter:
            continue

        candidate = item["candidate"]
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

        if stack:
            node = stack[-1][1]
            node["content"] += ("\n" if node["content"] else "") + text
            node["page_end"] = page_num
        else:
            if root and root[-1].get("heading") == "Unsectioned Content" and root[-1]["heading_level"] == 1:
                node = root[-1]
                node["content"] += ("\n" if node["content"] else "") + text
                node["page_end"] = page_num
            else:
                node = _new_node(
                    "Unsectioned Content", None, 1, page_num, None, [], 0.0,
                    {"synthetic": True}, display_order=len(root) + 1,
                )
                root.append(node)
                stack = [(1, node)]

    _finalize(root)
    return root


def build_section_tree(pages, warnings=None):
    """Builds the nested section tree for a document's "content" pages.

    Where the report has a Table of Contents, that is the structure -- the
    tree is built from it and the body only fills in text. Where it has
    none, headings are inferred from typography as before.

    `warnings` (a list, mutated in place if provided) collects human-
    readable notes about any hierarchy clamping performed, so a caller can
    surface them as `processing_warnings` without needing to re-derive them.
    """
    if warnings is None:
        warnings = []

    outline = TocOutline(parse_toc_outline(pages))
    body_font_size = content_body_font_size(pages)
    running_lines = detect_running_lines(pages)

    stream = _collect_stream(pages, body_font_size, running_lines)
    accepted = _decide_accepted_headings(stream)

    if outline.is_authoritative:
        return _build_from_outline(stream, outline, accepted, warnings)
    return _build_from_typography(stream, accepted, warnings)
