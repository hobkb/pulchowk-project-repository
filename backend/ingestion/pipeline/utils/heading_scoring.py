"""
Multi-signal heading detection.

A line becomes a heading candidate by combining several independently weak
signals into one confidence score, rather than gating acceptance on any
single one. The previous approach required either explicit numbering or an
exact hit against a ~90-entry alias dictionary (MAJOR_SECTION_ALIASES) --
which meant any unnumbered document using section wording outside that list
produced zero headings for those sections, and their entire body silently
became part of the previous recognized section's content.

Signals used here:
    - numbering (and its depth, e.g. "2.3" implies a deeper heading than "2")
    - boldness
    - font size relative to the document's own body-text font size
    - text shape (looks_like_heading: capitalization, length, punctuation)
    - an optional semantic-alias hit (supporting evidence only, never a gate)
    - whether the line is the first line of its own layout block

None of these alone determines the outcome. A bold uppercase line is not
automatically a heading; a line containing "Results" is not automatically a
section boundary; a numbered line is not automatically a valid heading if it
reads like a sentence ("3 respondents participated..."). The heading text
itself (numbering stripped) is never rewritten to a canonical synonym here --
that stays a separate, additive `semantic_role` classification.
"""

import re
from dataclasses import dataclass, field

from rapidfuzz.process import extractOne

from ingestion.pipeline.utils.heading_utils import looks_like_heading
from ingestion.pipeline.utils.section_aliases import MAJOR_SECTION_ALIASES, normalize_major_heading
from ingestion.pipeline.utils.text_cleaners import normalize_line

# Accept as a heading candidate once combined evidence crosses this bar.
# Calibrated so that "numbered + shape_ok" alone (0.40 + implicit shape
# requirement) is NOT sufficient on its own -- it also needs boldness or a
# font-size lift or a semantic hit, since plain numbered body sentences
# ("2. This finding suggests...") are common in some report styles.
HEADING_CONFIDENCE_THRESHOLD = 0.55

# An UNNUMBERED line clears the same score bar, but the score is only the
# entry ticket: section_tree._decide_accepted_headings then requires real
# STRUCTURAL evidence (substantial body text following it, and a recognised
# section name if the document otherwise numbers its headings). Raising the
# score threshold instead would simply trade false positives for false
# negatives -- a genuine unnumbered heading and a bold block label score
# almost identically, so what separates them is what follows them, not how
# they are styled.
UNNUMBERED_HEADING_CONFIDENCE_THRESHOLD = 0.55

# Characters that essentially only occur in mathematics, and the shapes a
# PDF text extractor produces when it tears a formula apart.
_MATH_CHARS = set("=+−–—×÷∑∏∫√∞≈≠≤≥∈∉⊂⊆∀∃∇∂⋅·^_|⟨⟩→←↔⇒⇔αβγδεθλμσφψωΓΔΘΛΣΦΨΩ′″")
_SUPER_SUB = set("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉ᵢⱼₖₙₜ̃̂")
# "19FFN", "10x" -- a digit run fused to a word, which is what happens when
# an equation number ends up glued to the start of the next fragment.
_DIGIT_WORD_FUSION = re.compile(r"\b\d+[A-Za-z]{2,}\b")
_FUNCTION_CALL = re.compile(r"[A-Za-z]{1,6}\s*\([^)]*$|[A-Za-z]{1,6}\s*\(.*[,;].*\)")


def looks_like_artifact(text: str) -> bool:
    """True when a line is a formula fragment, an equation number, an OCR
    tear, or an isolated symbol rather than anything a human wrote as a
    heading.

    These must never become sections regardless of how they are styled --
    they are frequently bold, isolated in their own layout block, and
    rendered in a larger maths font, which is precisely the combination
    that otherwise scores highest.
    """
    stripped = text.strip()
    if not stripped:
        return True

    # A bare number, or a number with trailing punctuation: an equation
    # number or a stray page artifact.
    if re.fullmatch(r"[\d\W_]+", stripped):
        return True

    chars = [c for c in stripped if not c.isspace()]
    if not chars:
        return True

    if any(c in _SUPER_SUB for c in chars):
        return True

    math_ratio = sum(1 for c in chars if c in _MATH_CHARS) / len(chars)
    if math_ratio >= 0.10:
        return True

    # Mostly punctuation/symbols rather than letters.
    letters = sum(1 for c in chars if c.isalpha())
    if letters / len(chars) < 0.55:
        return True

    if _DIGIT_WORD_FUSION.search(stripped):
        return True

    if _FUNCTION_CALL.search(stripped):
        return True

    # A single token with no vowel is almost never a heading word, but is a
    # very common variable/acronym fragment ("xk", "FFN", "ĥt").
    words = stripped.split()
    if len(words) == 1 and len(words[0]) <= 4 and not re.search(r"[aeiouAEIOU]", words[0]):
        return True

    return False

_CHAPTER_NUMBERING = re.compile(r"^chapter\s+(?:[ivxlcdm]+|\d+)\b[\s.:\-]*(.*)$", re.IGNORECASE)
_DOTTED_NUMBERING = re.compile(r"^(\d+(?:\.\d+)*)\.?\)?\s+(.*)$")


def parse_numbering(text: str):
    """Returns (numbering_tuple_or_None, remainder_text).

    "2.3 Data Collection" -> ((2, 3), "Data Collection")
    "Chapter 2 Literature Review" -> ((1,), "Literature Review")  [chapter-word numbering never implies a subsection depth]
    "Conclusion" -> (None, "Conclusion")
    """
    text = text.strip()

    m = _CHAPTER_NUMBERING.match(text)
    if m:
        return (1,), m.group(1).strip()

    m = _DOTTED_NUMBERING.match(text)
    if m:
        try:
            parts = tuple(int(p) for p in m.group(1).split("."))
        except ValueError:
            return None, text
        if parts:
            return parts, m.group(2).strip()

    return None, text


# A fuzzy alias hit is weak evidence and was previously accepted at 85,
# which matched a whole sentence ("where x represents the input sequence.")
# onto "Scope" and a hardware label ("System Memory") onto "System Design".
# Raised, and only applied to text short enough to plausibly BE a heading.
_FUZZY_ALIAS_CUTOFF = 92
_FUZZY_ALIAS_MAX_WORDS = 5


def semantic_roles(remainder_text: str):
    """Best-effort semantic classification of a heading's wording.

    Returns (roles, canonical, exact). `exact` distinguishes a real alias
    hit from a fuzzy near-miss: an exact hit is strong evidence that the
    line names a known section, a fuzzy one is not, and callers weigh them
    differently. Used as supporting evidence and as an additive,
    non-destructive field -- never to rewrite the heading text itself.
    """
    normalized = normalize_major_heading(normalize_line(remainder_text)).lower()
    if not normalized:
        return [], None, False

    canonical = MAJOR_SECTION_ALIASES.get(normalized)
    if canonical:
        return [canonical.lower().replace(" ", "_")], canonical, True

    if len(normalized.split()) > _FUZZY_ALIAS_MAX_WORDS:
        return [], None, False

    match = extractOne(
        normalized, MAJOR_SECTION_ALIASES.keys(), score_cutoff=_FUZZY_ALIAS_CUTOFF
    )
    if match:
        canonical = MAJOR_SECTION_ALIASES[match[0]]
        return [canonical.lower().replace(" ", "_")], canonical, False

    return [], None, False


@dataclass
class HeadingCandidate:
    text: str                  # heading wording as written, numbering stripped -- NEVER renamed
    numbering: tuple | None
    level_hint: int | None
    confidence: float
    signals: dict = field(default_factory=dict)
    semantic_role: list = field(default_factory=list)
    canonical_hint: str | None = None
    font_size: float = 0.0
    is_bold: bool = False


def score_heading_candidate(line: dict, body_font_size: float) -> "HeadingCandidate | None":
    raw_text = normalize_line(line.get("text", ""))
    if not raw_text:
        return None

    # A formula fragment or extraction artifact is never a heading, no
    # matter how it is styled. Checked on the RAW line, before numbering is
    # stripped, so an equation number is not mistaken for section numbering.
    if looks_like_artifact(raw_text):
        return None

    numbering, remainder = parse_numbering(raw_text)
    remainder = remainder.strip() if remainder else ""
    if not remainder:
        return None

    if looks_like_artifact(remainder):
        return None

    shape_ok = looks_like_heading(remainder)

    try:
        font_size = float(line.get("font_size") or 0)
    except (TypeError, ValueError):
        font_size = 0.0
    is_bold = bool(line.get("is_bold", False))
    font_ratio = (font_size / body_font_size) if body_font_size else 1.0

    roles, canonical, exact_alias = semantic_roles(remainder)

    signals = {
        "numbering": numbering is not None,
        "bold": is_bold,
        "font_ratio": round(font_ratio, 2),
        "shape_ok": shape_ok,
        "semantic_hit": bool(roles),
        "exact_alias": exact_alias,
        "block_start": line.get("line_number", 0) == 0,
    }

    score = 0.0
    if numbering is not None:
        score += 0.40
    if is_bold:
        score += 0.25
    if font_ratio >= 1.35:
        score += 0.25
    elif font_ratio >= 1.15:
        score += 0.15
    if roles:
        score += 0.15
    if signals["block_start"]:
        score += 0.05

    # Shape is a near-hard requirement (not absolute, so an all-caps
    # numbered heading ending oddly isn't thrown out over one edge case),
    # but a strong negative -- a line that reads like prose should very
    # rarely still cross the acceptance threshold.
    if not shape_ok:
        score -= 0.55

    # An unnumbered one- or two-word label ("CPU", "System Memory") is the
    # single most common false positive: it is short, capitalised, often
    # bold, and sits in its own layout block. Without either numbering or a
    # recognised section name behind it there is no evidence it is
    # structural rather than a term being defined inside a section.
    if numbering is None and not exact_alias and len(remainder.split()) <= 2:
        score -= 0.30

    score = max(0.0, min(1.0, score))

    level_hint = len(numbering) if numbering is not None else None

    return HeadingCandidate(
        text=remainder,
        numbering=numbering,
        level_hint=level_hint,
        confidence=round(score, 3),
        signals=signals,
        semantic_role=roles,
        canonical_hint=canonical,
        font_size=font_size,
        is_bold=is_bold,
    )
