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
    r"\b(?:[A-Z]{2,5}\s*)?\d{3}\s*[A-Z]{2,5}\s*\d{3}\b",
    re.IGNORECASE,
)

SUPERVISOR_PATTERN = re.compile(
    r"\b(supervisor|co-supervisor|co supervisor|supervised\s+by|"
    r"under\s+the\s+guidance\s+of|guided\s+by|advisor|adviser)\b",
    re.IGNORECASE,
)

TITLE_PATTERN = re.compile(
    r"\b(prof\.?|professor|assoc\.?\s*prof\.?|associate\s+prof\.?|"
    r"associate\s+professor|asst\.?\s*prof\.?|assistant\s+prof\.?|"
    r"assistant\s+professor|dr\.?|mr\.?|mrs\.?|ms\.?)\b",
    re.IGNORECASE,
)

HEADING_PATTERN = re.compile(
    r"^(?P<order>\d+(?:\.\d+)+|\d+)\s+(?P<title>[A-Za-z][A-Za-z\s,\-\(\)'\"’&]+)$"
)

YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2}|[1-2]\d{3})\b")

REPOSITORY_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[^\s]+",
    re.IGNORECASE,
)

TOC_ENTRY = re.compile(r"\.{2,}\s*\d+\s*$")


def normalize_line(text: str) -> str:
    # PostgreSQL cannot store NUL characters in text or JSON values.  Some
    # PDFs expose them through layout extraction, so discard them before the
    # text becomes part of extracted metadata.
    return re.sub(r"\s+", " ", (text or "").replace("\x00", "")).strip()


def clean_roll_number(roll: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", roll).upper()


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
