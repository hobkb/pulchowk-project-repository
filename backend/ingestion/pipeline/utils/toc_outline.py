"""
The document's own Table of Contents, read as the authoritative outline.

Font size and boldness are a *guess* at which lines are headings. The ToC
is the author's own explicit statement of it, and it is the only place in
the report that distinguishes a real subsection from a numbered list item
inside one. "4.4.1 FastAPI" appears in the ToC; the "1. 2. 3." enumerating
functional requirements underneath it does not -- yet on the page both are
a short numbered line, often bold, and no typographic rule can separate
them. Reading the ToC removes the guesswork entirely.

Only NUMBERED entries are taken, which is also what makes the outline start
at "1 Introduction": the front matter above it (Approval, Acknowledgements,
Abstract, Contents, List of Figures) is unnumbered and is skipped as a
consequence of the same rule, not as a special case.

Nothing here prints or returns document text to a caller that logs it --
`parse_toc_outline` returns structured entries for the section builder to
match against, and the builder only ever reports counts.
"""

import re

from rapidfuzz import fuzz

from ingestion.pipeline.utils.text_cleaners import TOC_ENTRY, TOC_LEADER, normalize_line

# A ToC row's leading section number: "1", "2.3", "4.4.1". The trailing dot
# ("4.4.1.") is optional and not part of the numbering.
_TOC_ROW = re.compile(r"^(?P<numbering>\d+(?:\.\d+)*)\.?\s+(?P<rest>\S.*)$")

# The page reference that ends a completed ToC row, with or without a dot
# leader in front of it. Roman numerals are matched so a front-matter row
# is recognised as a complete row (and then discarded for being unnumbered)
# rather than being mistaken for the start of a wrapped entry.
_TRAILING_PAGE = re.compile(
    r"^(?P<title>.*?)"
    r"(?:\s*(?:\.\s?){2,}\s*|\s*_{2,}\s*|\s{2,}|\s+)"
    r"(?P<page>\d{1,4}|[ivxlcdm]+)\s*$",
    re.IGNORECASE,
)

# How many numbered entries a ToC must yield before the section builder is
# willing to treat it as authoritative. A handful of rows could be a stray
# numbered paragraph; a real ToC for a report of this kind has many.
MIN_AUTHORITATIVE_ENTRIES = 5

# A line consisting of nothing but a page reference. Layout extraction
# regularly puts the page number of a ToC row on its own line when the dot
# leader is wide, and treating that as more of a wrapped title is what
# produced headings like "Backend Development 12".
_BARE_PAGE_REF = re.compile(r"^[\s.…·]*(?P<page>\d{1,4}|[ivxlcdm]+)\s*$", re.IGNORECASE)

# Leader characters beyond the ASCII dots TOC_LEADER knows about: a real
# ellipsis and a middle dot both appear in these reports.
_UNICODE_LEADER = re.compile(r"[…·•]+")

# How close a heading on the page must read to its ToC row to be considered
# the same heading. Generous, because the two are frequently capitalised
# differently and extraction can mangle punctuation -- the numbering has
# already done the hard part of identifying which entry this is.
_TITLE_MATCH_THRESHOLD = 70

# Matching on the title ALONE, with no number to corroborate it, has to be
# near-exact -- a loose match here would attach a section to the wrong row.
_TITLE_ONLY_MATCH_THRESHOLD = 88


def _normalize_title(text):
    """Comparison form: lowercase, punctuation-free, single-spaced."""
    cleaned = re.sub(r"[^0-9a-z]+", " ", normalize_line(text).lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _looks_like_toc_page(page):
    """True when a page is still part of the ToC even though classification
    has moved on. Page classification only recognises the ToC by its title
    line, so a ToC running onto a second or third page reverts to whatever
    state matched next -- usually "content", because rows like "1
    Introduction 1" look exactly like a chapter start."""
    rows = 0
    for line in page.get("lines", []):
        text = normalize_line(line.get("text", ""))
        if not text:
            continue
        if TOC_ENTRY.search(text) or (TOC_LEADER.search(text) and _TOC_ROW.match(text)):
            rows += 1
    return rows >= 3


def toc_pages(pages):
    """The pages making up the Table of Contents, including continuations."""
    collected = []
    started = False
    for page in pages:
        if page.get("page_type") == "toc":
            started = True
            collected.append(page)
            continue
        if started:
            if _looks_like_toc_page(page):
                collected.append(page)
                continue
            break
    return collected


def parse_toc_outline(pages):
    """Reads the ToC into an ordered list of numbered outline entries.

    Each entry is {"numbering": (4, 4, 1), "title": "FastAPI",
    "page": 31, "depth": 3}. Unnumbered rows (the front matter) are
    dropped, so the outline begins at the first numbered chapter.

    A row whose title wraps onto the following line is joined back
    together: the ToC in a long report regularly breaks a long subsection
    title across two lines, and half a title would never match the heading
    as it appears on the page.
    """
    entries = []
    pending = None

    def flush(page_value):
        nonlocal pending
        if pending is None:
            return
        if _BARE_PAGE_REF.match(pending["title"] or ""):
            # Nothing but a page reference -- never a heading.
            pending = None
            return

        title = normalize_line(_UNICODE_LEADER.sub(" ", pending["title"]))
        # A trailing page reference that survived because the row had no
        # recognisable separator in front of it.
        title = re.sub(r"[\s.]*(?:\d{1,4}|[ivxlcdm]+)$", "", title, flags=re.IGNORECASE).strip()
        if title:
            entries.append({
                "numbering": pending["numbering"],
                "title": title,
                "page": page_value,
                "depth": len(pending["numbering"]),
            })
        pending = None

    for page in toc_pages(pages):
        for line in page.get("lines", []):
            text = normalize_line(line.get("text", ""))
            if not text:
                continue

            row = _TOC_ROW.match(text)
            if row:
                rest = row.group("rest")

                # "8 vi" -- a row's page number followed by the ToC page's
                # own roman-numeral footer, merged into one line by layout
                # reconstruction. It reads as chapter 8 titled "vi", which
                # became a top-level section that adopted every chapter
                # after it. It is really the page reference completing the
                # row still pending above.
                if _BARE_PAGE_REF.match(rest):
                    if pending is not None:
                        page_str = row.group("numbering")
                        flush(int(page_str) if page_str.isdigit() else None)
                    continue

                # A new numbered row ends whatever was still being wrapped.
                flush(None)
                numbering = tuple(int(part) for part in row.group("numbering").split("."))
                complete = _TRAILING_PAGE.match(rest)
                if complete:
                    page_ref = complete.group("page")
                    pending = {
                        "numbering": numbering,
                        "title": TOC_LEADER.sub(" ", complete.group("title")),
                    }
                    flush(int(page_ref) if page_ref.isdigit() else None)
                else:
                    pending = {
                        "numbering": numbering,
                        "title": TOC_LEADER.sub(" ", rest),
                    }
                continue

            if pending is not None:
                # The row's page number, pushed onto its own line by layout
                # extraction. It completes the row; it is not more title.
                bare = _BARE_PAGE_REF.match(text)
                if bare:
                    page_ref = bare.group("page")
                    flush(int(page_ref) if page_ref.isdigit() else None)
                    continue

                # A continuation line for a title that wrapped.
                complete = _TRAILING_PAGE.match(text)
                if complete:
                    page_ref = complete.group("page")
                    pending["title"] += " " + TOC_LEADER.sub(" ", complete.group("title"))
                    flush(int(page_ref) if page_ref.isdigit() else None)
                elif not TOC_ENTRY.search(text):
                    pending["title"] += " " + TOC_LEADER.sub(" ", text)
                else:
                    # An unnumbered completed row (front matter) -- ends the
                    # wrap without contributing to it.
                    flush(None)
                continue

            # An unnumbered row AFTER the outline has begun is a chapter the
            # report chose not to number ("Conclusion", "References"). Before
            # the first numbered row it is front matter, and is skipped -- the
            # same rule that makes the outline start at "1 Introduction".
            if entries:
                complete = _TRAILING_PAGE.match(text)
                if complete:
                    title = normalize_line(TOC_LEADER.sub(" ", complete.group("title")))
                    if title and len(title.split()) <= 8:
                        entries.append({
                            "numbering": None,
                            "title": title,
                            "page": int(complete.group("page")) if complete.group("page").isdigit() else None,
                            "depth": 1,
                        })

    flush(None)
    return entries


# A numbered heading as it appears in the BODY. Deliberately separate from
# heading_scoring.parse_numbering, which deliberately collapses "Chapter 2"
# to depth 1 (a chapter word never implies a subsection depth). Here the
# real number matters, because it is the key the ToC is matched on: a body
# heading reading "Chapter 2 Literature Review" has to find the ToC row
# "2 Literature Review".
_BODY_NUMBERED_HEADING = re.compile(
    r"^(?:chapter|section|unit)?\s*(?P<numbering>\d+(?:\.\d+)*)\.?\s*[:\-–]?\s+(?P<title>\S.*)$",
    re.IGNORECASE,
)


def split_numbered_heading(text):
    """(numbering_tuple, title) for a numbered body heading, else (None, text)."""
    match = _BODY_NUMBERED_HEADING.match(normalize_line(text))
    if not match:
        return None, normalize_line(text)
    numbering = tuple(int(part) for part in match.group("numbering").split("."))
    return numbering, match.group("title").strip()


class TocOutline:
    """A parsed ToC, ready to be matched against headings on the page.

    Each entry may be claimed only once. Two different pages both matching
    "3.1 Feasibility Study" means one of them is a running header or a
    cross-reference, not a second section, and a document cannot contain
    the same numbered subsection twice.
    """

    def __init__(self, entries):
        self.entries = entries
        self._by_numbering = {}
        self._by_title = {}
        for entry in entries:
            # First occurrence wins: a ToC that lists the same number twice
            # is malformed, and the earlier row is the more likely real one.
            if entry["numbering"] is not None:
                self._by_numbering.setdefault(entry["numbering"], entry)
            self._by_title.setdefault(_normalize_title(entry["title"]), entry)
        self._claimed = set()

    def __len__(self):
        return len(self.entries)

    @property
    def is_authoritative(self):
        return len(self.entries) >= MIN_AUTHORITATIVE_ENTRIES

    def match(self, numbering, title, *, scored_as_heading=False):
        """The outline entry this heading is, or None.

        Numbering must match an entry exactly -- that is what rejects a
        "1. 2. 3." list inside a section, whose numbering either matches
        no entry or matches a chapter whose title is nothing like it.

        The title then has to agree, which is what stops list item "1."
        being accepted as chapter "1 Introduction". The one exception is a
        heading two or more levels deep that the scorer independently
        judged a heading: nothing in a report enumerates list items as
        "4.4.1", so the numbering alone is already conclusive there, and
        this keeps a section whose title extraction was mangled.
        """
        if numbering is None:
            return None

        entry = self._by_numbering.get(tuple(numbering))
        if entry is None or id(entry) in self._claimed:
            return None

        if _title_agrees(title, entry["title"]):
            self._claimed.add(id(entry))
            return entry

        if scored_as_heading and len(entry["numbering"]) >= 2:
            self._claimed.add(id(entry))
            return entry

        return None


    def match_title(self, title):
        """The outline entry for a heading printed WITHOUT its number.

        Plenty of reports set "Backend Development" in a large face and
        leave the "5.1" to the ToC alone. Matching on numbering only would
        find nothing in such a document, and every real subsection would be
        swallowed into the chapter above it -- so the title is matched on
        its own here.

        Deliberately much stricter than the numbered path: there is no
        number to confirm the identity, so an exact normalised title is
        required, or a near-identical one. The caller additionally has to
        have judged the line heading-shaped before asking.
        """
        key = _normalize_title(title)
        if not key:
            return None

        entry = self._by_title.get(key)
        if entry is None:
            best, best_score = None, 0
            for candidate in self.entries:
                if id(candidate) in self._claimed:
                    continue
                score = fuzz.ratio(key, _normalize_title(candidate["title"]))
                if score > best_score:
                    best, best_score = candidate, score
            if best_score >= _TITLE_ONLY_MATCH_THRESHOLD:
                entry = best

        if entry is None or id(entry) in self._claimed:
            return None

        self._claimed.add(id(entry))
        return entry


def _title_agrees(page_title, toc_title):
    left = _normalize_title(page_title)
    right = _normalize_title(toc_title)
    if not left or not right:
        return False
    if left == right or left.startswith(right) or right.startswith(left):
        return True
    return fuzz.ratio(left, right) >= _TITLE_MATCH_THRESHOLD
