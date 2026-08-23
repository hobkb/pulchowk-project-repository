"""
Text normalization, regex extraction, and cleaning utilities.
Extracted from metadata_extraction.py.
"""

import re
from rapidfuzz.process import extractOne

MONTH_PATTERN = (
    r"(January|February|March|April|May|June|July|August|"
    r"September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
)

ROLL_PATTERN = re.compile(
    # The optional campus/institute prefix ("PUL080BCT099") must be glued
    # directly to the digits with no space -- if it allowed a space there,
    # an ordinary 2-5 letter surname immediately before a roll number on the
    # same line (e.g. "Nischal Karki 079BCT047") would be swallowed into the
    # match as if "Karki" were a prefix code.
    r"\b(?:[A-Z]{2,5})?\d{3}\s*[A-Z]{2,5}\s*\d{3}\b",
    re.IGNORECASE,
)

# Connective phrases that indicate a nearby name is (probably) being
# identified as a project supervisor, even with no standalone "Supervisor:"
# label -- e.g. "...Asst. Prof. Bikal Adhikari, who also serves as our
# supervisor..." inside ordinary acknowledgement prose. Deliberately a
# compact set of grammatical connectors rather than a list of full example
# sentences; a nearby person's name (checked separately) is what turns a
# cue-phrase hit into an actual candidate.
SUPERVISOR_PATTERN = re.compile(
    r"\b(?:"
    r"under\s+the\s+supervision\s+of"
    r"|under\s+the\s+guidance\s+of"
    r"|with\s+guidance\s+from"
    r"|supervised\s+by"
    r"|guided\s+by"
    r"|(?:who\s+)?(?:also\s+)?(?:serves?|served|acting)\s+as\s+(?:our|the|my)\s+(?:project\s+)?(?:co-)?supervisor"
    r"|(?:our|my)\s+(?:project\s+)?(?:co-)?supervisor"
    r"|co-supervisor|co\s+supervisor|supervisor"
    r"|advisor|adviser"
    r")\b",
    re.IGNORECASE,
)

TITLE_PATTERN = re.compile(
    r"\b(prof\.?|professor|assoc\.?\s*prof\.?|associate\s+prof\.?|"
    r"associate\s+professor|asst\.?\s*prof\.?|assistant\s+prof\.?|"
    r"assistant\s+professor|dr\.?|mr\.?|mrs\.?|ms\.?)\b",
    re.IGNORECASE,
)

# A single academic-title token, ordered so multi-word compounds
# ("Assoc. Prof.", "Assistant Professor") are tried before the bare "Prof."
# they contain -- otherwise the shorter alternative would win and leave a
# stray "Assoc." / "Asst." glued onto the front of the extracted name.
_PERSON_TITLE_TOKEN = (
    r"(?:Assoc\.?\s*Prof(?:essor)?\.?|Associate\s+Prof(?:essor)?\.?"
    r"|Asst\.?\s*Prof(?:essor)?\.?|Assistant\s+Prof(?:essor)?\.?"
    r"|Prof(?:essor)?\.?|Drs\.?|Dr\.?|Mr\.?|Mrs\.?|Ms\.?|Miss|Engr\.?|Rev\.?|Hon\.?)"
)

# Matches one or more stacked title tokens at the start of a name, e.g.
# "Prof. Dr. Manoj Shrestha" or "Asst. Prof. Bikal Adhikari". Shared by
# extraction (MetadataPeopleStep) and publish-time faculty-record creation
# so there is exactly one place that knows how to split a title from a name.
PERSON_TITLE_PATTERN = re.compile(
    rf"^(?P<title>{_PERSON_TITLE_TOKEN}(?:\s+{_PERSON_TITLE_TOKEN})*)\s+(?P<name>.+)$",
    re.IGNORECASE,
)

# Same title-plus-name shape as PERSON_TITLE_PATTERN, but NOT anchored to
# the start of the string -- for finding a titled name anywhere inside a
# free-form sentence, e.g. scanning acknowledgement prose for "...Asst.
# Prof. Bikal Adhikari, who also serves as our supervisor...".
#
# IMPORTANT: the trailing `[A-Z]...` name-word part is deliberately left
# OUTSIDE any case-insensitive scope. Compiling this with a blanket
# re.IGNORECASE (the previous approach) makes `[A-Z]` match a lowercase
# letter too, which silently defeats the entire point of that character
# class -- it stops meaning "must be a capitalized word" and starts
# matching any word at all, so ordinary lowercase sentence text right
# after the name ("...Bhattarai for his continuous support...") gets
# captured as though it were more of the name ("Bhattarai For His").
# `(?i:...)` scopes case-insensitivity to just the title-token part, where
# it's actually wanted (matching "dr."/"DR."/"Dr." alike).
NAME_WITH_TITLE = re.compile(
    rf"(?i:{_PERSON_TITLE_TOKEN}(?:\s+{_PERSON_TITLE_TOKEN})*)"
    r"\s+[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,3}"
)

HEADING_PATTERN = re.compile(
    r"^(?P<order>\d+(?:\.\d+)+|\d+)\s+(?P<title>[A-Za-z][A-Za-z\s,\-\(\)'\"’&]+)$"
)

YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2}|[1-2]\d{3})\b")

REPOSITORY_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[^\s]+",
    re.IGNORECASE,
)

# A table-of-contents "leader": a run of dots (tight "...." or spaced ". . . .")
# or underscores. On its own this is only weak evidence -- a sentence that
# trails off with "...." would also match -- so it's for coarse, page-level
# heuristics (e.g. "does this page still look like it's part of the ToC?")
# where being a little over-inclusive is harmless.
TOC_LEADER = re.compile(r"(?:\.\s?){2,}|_{2,}")

# A confirmed TOC *row*: a leader immediately followed by an actual page
# reference (Arabic, Roman numeral, or a lone letter). The trailing
# reference is required here -- unlike TOC_LEADER -- so a line of real
# section content that merely ends in an ellipsis is never mistaken for a
# TOC row and silently dropped. Shared by page classification and section
# extraction so both agree on what counts as a genuine TOC entry.
TOC_ENTRY = re.compile(
    r"(?:(?:\.\s?){2,}|_{2,})\s*(?:[ivxlcdm]+|\d+|[a-z])\s*$",
    re.IGNORECASE,
)


def normalize_line(text: str) -> str:
    # PostgreSQL cannot store NUL characters in text or JSON values.  Some
    # PDFs expose them through layout extraction, so discard them before the
    # text becomes part of extracted metadata.
    return re.sub(r"\s+", " ", (text or "").replace("\x00", "")).strip()


def clean_roll_number(roll: str) -> str:
    roll = re.sub(r"[^A-Za-z0-9]", "", roll).upper()
    roll = re.sub(r"^[A-Z]{3}(?=\d)", "", roll)
    return roll


def split_person_title(full_name: str):
    """Split a leading academic title from a person's name, e.g.
    "Asst. Prof. Bikal Adhikari" -> ("Bikal Adhikari", "Asst. Prof.").
    Returns (name, title); title is "" when no recognized title prefix is
    present. Used both when extracting a supervisor's name from a report
    and when turning an extracted full_name into a Faculty record's
    name/title fields at publish time, so the two stay consistent."""
    cleaned = (full_name or "").strip()
    if not cleaned:
        return "", ""

    match = PERSON_TITLE_PATTERN.match(cleaned)
    if not match:
        return normalize_person_name(cleaned), ""

    title = re.sub(r"\s+", " ", match.group("title")).strip()
    name = normalize_person_name(match.group("name"))
    return name, title


def normalize_person_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""

    tokens = []
    for token in cleaned.split():
        if not token:
            continue
        token = token.strip(".,;:()[]{}\"'")
        if not token:
            continue
        if token.isupper() and len(token) <= 3:
            tokens.append(token)
            continue
        tokens.append(token[:1].upper() + token[1:].lower())

    return " ".join(tokens)


# A leading section number on a heading: "1", "1.1", "2.3.1", optionally
# with a trailing dot or closing paren. This is the heading's position in
# the document outline and must survive normalization intact -- stripping
# the separators turned "1.1 Background" into "11 Background" and
# "1.2 Problem Statement" into "12 Problem Statement", destroying the one
# visible cue that tells a reader (and an admin reviewing an extraction)
# which subsection belongs to which chapter.
SECTION_NUMBER_PREFIX = re.compile(r"^(\d+(?:\.\d+)*)[.)]?$")


def _normalize_title_token(token: str) -> str:
    """Title-cases one word of a heading while keeping the punctuation that
    carries meaning inside it -- an internal hyphen ("Real-Time"), an
    apostrophe, an ampersand, or a slash. Only decoration at the token's
    edges is trimmed."""
    token = token.strip("_,;:()[]{}\"'")
    if not token:
        return ""
    if token.isupper() and len(token) <= 4:
        return token  # an acronym: PID, IoT-ish caps, GPS
    # Title-case each hyphen/slash-separated part so "real-time" -> "Real-Time".
    parts = re.split(r"([-/])", token.lower())
    return "".join(
        part if part in "-/" else (part[:1].upper() + part[1:]) for part in parts
    )


def normalize_section_title(value: str) -> str:
    """Normalizes a section heading for display.

    Preserves the heading's own numbering prefix verbatim (see
    SECTION_NUMBER_PREFIX) and keeps meaningful in-word punctuation;
    everything after the number is title-cased. Distinct from
    normalize_canonical_section below, which is a lookup KEY and is
    deliberately reduced to bare alphanumerics.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        return ""

    cleaned = cleaned.replace("_", " ")
    raw_tokens = [token for token in re.split(r"\s+", cleaned) if token]

    tokens = []
    for index, token in enumerate(raw_tokens):
        # Only the very first token may be a numbering prefix -- a number
        # appearing later in a heading is ordinary content.
        if index == 0:
            number_match = SECTION_NUMBER_PREFIX.match(token)
            if number_match:
                tokens.append(number_match.group(1))
                continue
        normalized = _normalize_title_token(token)
        if normalized:
            tokens.append(normalized)

    return " ".join(tokens)


def normalize_canonical_section(value: str) -> str:
    """Normalizes a CANONICAL section name -- the coarse category a heading
    maps to ("Introduction", "Results And Discussion"), used as a lookup
    key rather than shown as the heading itself. Reduced to bare
    alphanumeric words on purpose, so punctuation and numbering variants
    all collapse onto the same key."""
    cleaned = (value or "").strip()
    if not cleaned:
        return ""

    cleaned = cleaned.replace("_", " ").replace("-", " ")
    tokens = []
    for token in re.split(r"\s+", cleaned):
        if not token:
            continue
        token = re.sub(r"[^A-Za-z0-9]", "", token)
        if not token:
            continue
        if token.isupper() and len(token) <= 3:
            tokens.append(token)
            continue
        tokens.append(token[:1].upper() + token[1:].lower())

    return " ".join(tokens)


def extract_roll(line: str):
    match = ROLL_PATTERN.search(line or "")
    if not match:
        return None
    return clean_roll_number(match.group())


def extract_name_from_line(line: str):
    roll = extract_roll(line)
    if roll:
        line = ROLL_PATTERN.sub("", line)
    line = re.sub(r"[\(\)\[\]]", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    if not line:
        return None
    return line.strip(" -:")


def looks_like_noise(line: str) -> bool:
    lowered = normalize_line(line).lower()
    if len(lowered.split()) > 6 or "source of strength" in lowered or "journey" in lowered:
        return True
    return not lowered or any(
        token in lowered
        for token in [
            "submitted", "prepared", "supervisor", "co-supervisor",
            "department", "campus", "tribhuvan", "university",
            "institute", "guidance", "approval", "abstract", "report",
            # Author/team-list section labels ("Student Members", "Project
            # Members", "Authors", "Team Members") -- these are structurally
            # indistinguishable from a real 2-word capitalized name, so they
            # must be filtered out explicitly rather than by name shape.
            "members", "authors",
        ]
    )


def canonicalize_heading(title: str, parent_canonical=None):
    cleaned = re.sub(r"^\d+(?:\.\d+)*\s*", "", title).strip()
    if not cleaned:
        return parent_canonical

    candidates = [
        "Introduction", "Background", "Literature Review", "Methodology",
        "Implementation", "Results", "Discussion", "Conclusion",
        "Future Work", "Evaluation", "Recommendations", "Appendix", "References",
    ]
    match = extractOne(cleaned, candidates, score_cutoff=75)
    if match:
        return match[0]

    return parent_canonical if parent_canonical else cleaned
