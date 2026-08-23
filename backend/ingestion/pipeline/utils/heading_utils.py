"""
Shared heading-plausibility heuristic.
"""

import re

from ingestion.pipeline.utils.text_cleaners import SUPERVISOR_PATTERN, TOC_ENTRY

_LOWERCASE_STOPWORDS = {
    "of", "and", "the", "for", "in", "on", "to", "a", "an", "with", "by", "as",
}

# An ordinal date ("13th April, 2023") rendered with the numeral and its
# suffix as separate text runs is exactly the shape numbering-stripping
# elsewhere in this pipeline expects ("13" consumed as a leading number,
# leaving "th April, 2023" as the "remainder") -- without this guard that
# remainder passes every other heading check (capitalized second word, no
# trailing punctuation, not prose) and gets accepted as a heading, even
# though it's a date fragment, not a title.
_ORDINAL_FRAGMENT = re.compile(r"^(?:st|nd|rd|th)\b", re.IGNORECASE)


def looks_like_heading(title_text: str, max_words: int = 8) -> bool:
    """
    True if `title_text` (the part of a line after a leading chapter/section
    number) plausibly reads like a heading rather than a sentence of body
    text or a table-of-contents row.
    """
    title = title_text.strip()
    if not title:
        return False

    # ToC rows look like "Introduction ........ 5" or "Background . . . . 12"
    # -- a leader (dots/underscores) plus a trailing page reference. A real
    # heading never has that.
    if TOC_ENTRY.search(title):
        return False

    words = title.split()
    if not words or len(words) > max_words:
        return False

    if _ORDINAL_FRAGMENT.match(words[0]):
        return False

    # A short, prominently-styled front-matter label -- "Under the
    # Supervision of", "Supervised by" -- reads exactly like a heading by
    # shape alone (short, capitalized, no trailing punctuation), but it's
    # part of the title/approval block, not a chapter title. Reusing the
    # same cue-phrase vocabulary the supervisor extractor already trusts
    # elsewhere keeps this a narrow, well-evidenced exclusion rather than a
    # new guess -- the word-count cap keeps it from also rejecting a
    # legitimately long heading that merely mentions "supervisor" as one
    # word among several.
    if len(words) <= 6 and SUPERVISOR_PATTERN.search(title):
        return False

    # Real headings don't trail off with sentence punctuation.
    if title.rstrip()[-1] in ".,;":
        return False

    # Headings start capitalized ("Introduction", "Literature Review"),
    # sentences that merely start with a digit usually don't
    # ("3 respondents participated...").
    if not words[0][0].isupper():
        return False

    # If most of the remaining words are ordinary lowercase words, it reads
    # like prose rather than a heading.
    lowercase_count = sum(
        1 for w in words if w.islower() and w not in _LOWERCASE_STOPWORDS
    )
    if lowercase_count > len(words) * 0.6:
        return False

    return True
