"""
Shared heading-plausibility heuristic.

Both the page-level classifier (page_classification.py) and the
section-level chunker (semantic_chunking.py) need to tell a real heading
("1 Introduction", "3.4 Dataset Preparation") apart from a body sentence
that merely happens to start with a number ("3 respondents participated in
the pilot study conducted last year..."). Both now import this single
function instead of judging it two different ways.
"""

import re

_LOWERCASE_STOPWORDS = {
    "of", "and", "the", "for", "in", "on", "to", "a", "an", "with", "by", "as",
}

# ToC rows look like "Introduction ........ 5" -- leader dots + a trailing
# page number. A real heading never has that.
_TOC_LEADER_DOTS = re.compile(r"\.{2,}\s*\d*\s*$")


def looks_like_heading(title_text: str, max_words: int = 12) -> bool:
    """
    True if `title_text` (the part of a line after a leading chapter/section
    number) plausibly reads like a heading rather than a sentence of body
    text or a table-of-contents row.
    """
    title = title_text.strip()
    if not title:
        return False

    if _TOC_LEADER_DOTS.search(title):
        return False

    words = title.split()
    if not words or len(words) > max_words:
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
