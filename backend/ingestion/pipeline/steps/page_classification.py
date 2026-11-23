import re
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.heading_scoring import parse_numbering
from ingestion.pipeline.utils.heading_utils import looks_like_heading
from ingestion.pipeline.utils.section_aliases import (
    MAJOR_SECTION_ALIASES,
    normalize_major_heading,
)
from ingestion.pipeline.utils.section_tree import FOOTER_PAGE_NUMBER
from ingestion.pipeline.utils.text_cleaners import normalize_line

# A page-classification-only plausibility floor: bold and at least this
# size is treated as "probably a heading" typography, independent of the
# rest of the document's own body-text size (which isn't known yet at this
# stage -- page classification runs before any page has been confirmed as
# "content"). This deliberately stays conservative; MetadataSectionsStep's
# confidence scoring is the real, document-calibrated heading acceptance
# test and runs afterward on pages this step has already let through.
MIN_CONFIDENT_HEADING_FONT_SIZE = 12.0


class DocumentPageClassifier:
    TOC_TITLE = re.compile(
        r"^\s*(contents|table\s+of\s+contents|table\s+contents|index)\s*:?\s*$",
        re.IGNORECASE
    )
    FIGURES_TITLE = re.compile(
        r"^\s*(list\s+of\s+figures|figures|figure\s+list)\s*:?\s*$",
        re.IGNORECASE
    )
    TABLES_TITLE = re.compile(
        r"^\s*(list\s+of\s+tables|tables|table\s+list)\s*:?\s*$",
        re.IGNORECASE
    )
    ABBR_TITLE = re.compile(
        r"^\s*(list\s+of\s+abbreviations|abbreviations|acronyms|list\s+of\s+acronyms)\s*:?\s*$",
        re.IGNORECASE
    )
    # "Recommendation" pages are included here (not a separate state) because
    # they serve the same role in the sequence -- a signature-block page
    # naming the supervisor -- and are at least as common a heading as
    # "Approval" in Nepali/IOE-style thesis templates ("Letter of
    # Recommendation" precedes or replaces the "Certificate of Approval").
    # Anchored to the WHOLE line (like ACKNOWLEDGEMENT/ABSTRACT below), not a
    # bare substring search -- "approval" and "recommendation" are also
    # ordinary English words that show up inside real body sentences (e.g. a
    # thesis's own "Recommendations" chapter, or a sentence discussing a
    # supervisor's "approval" of a design choice). An unanchored search would
    # misclassify that content page as front matter and silently drop it,
    # since a page's type is never revisited once classification moves past
    # it. Anchoring still matches a page whose entire title line just reads
    # "APPROVAL" or "RECOMMENDATION", which is exactly the real front-matter
    # case this is meant to catch.
    APPROVAL = re.compile(
        r"^\s*(?:page\s+of\s+approval|approval\s+page|certificate\s+of\s+approval|approval"
        r"|letter\s+of\s+recommendation|recommendation\s+letter|recommendation)\s*:?\s*$",
        re.IGNORECASE
    )
    COPYRIGHT = re.compile(
        r"^\s*(?:copyright\s+page|copyright\s*©.*|©.*|copyright)\s*:?\s*$",
        re.IGNORECASE
    )
    ACKNOWLEDGEMENT = re.compile(
        r"^\s*(acknowledgements?|acknowledgments?|thanks|gratitude)\s*:?\s*$",
        re.IGNORECASE
    )
    ABSTRACT = re.compile(
        r"^\s*"
        r"(?:\d+[\.\)]?\s*)?"
        r"(abstract(?:\s+of\s+the\s+project)?"
        r"|project\s+abstract"
        r"|executive\s+summary"
        r"|project\s+summary"
        r"|summary"
        r"|synopsis"
        r"|a\s+brief\s+summary)"
        r"\s*:?\s*$",
        re.IGNORECASE
    )
    # Chapter number may be followed by a period/paren before the title
    # ("1 Introduction", "1. Introduction", "1) Introduction"), not just a
    # bare space -- a numbered-with-period heading is a common report style.
    CHAPTER_START = re.compile(
        r"^(?:chapter\s+([ivxlcdm\d]+)\b[\s.:\-]*(.*)|(\d+)[.\)]?\s+(.+)|(introduction)\s*(.*))$",
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize_line(line):
        return re.sub(r"\s+", " ", line).strip()

    @staticmethod
    def _matches_chapter_start(line: str) -> bool:
        line = DocumentPageClassifier._normalize_line(line)
        m = DocumentPageClassifier.CHAPTER_START.match(line)
        if not m:
            return False
        title = m.group(2) or m.group(4) or m.group(6) or ""
        if not title.strip():
            return True
        return looks_like_heading(title)

    @staticmethod
    def _matches_known_section_alias(line: str) -> bool:
        # Any heading MetadataSectionsStep already knows how to canonicalize
        # (e.g. "Requirement Analysis", "Literature Survey") also counts as
        # the start of a content page, even with no leading chapter number.
        normalized = normalize_major_heading(DocumentPageClassifier._normalize_line(line))
        return normalized.lower() in MAJOR_SECTION_ALIASES

    # A "prose" companion line needs at least this many words to count as
    # real running sentence text rather than another short label.
    MIN_PROSE_WORDS = 4

    @staticmethod
    def _is_confident_heading_shaped(line: dict) -> bool:
        text = normalize_line(line.get("text", ""))
        if not text:
            return False
        if not line.get("is_bold", False):
            return False
        try:
            font_size = float(line.get("font_size") or 0)
        except (TypeError, ValueError):
            font_size = 0.0
        if font_size < MIN_CONFIDENT_HEADING_FONT_SIZE:
            return False
        _, remainder = parse_numbering(text)
        return looks_like_heading(remainder or text)

    @staticmethod
    def _is_prose_line(line: dict) -> bool:
        text = normalize_line(line.get("text", ""))
        if not text or FOOTER_PAGE_NUMBER.match(text):
            return False
        if looks_like_heading(text):
            return False
        return len(text.split()) >= DocumentPageClassifier.MIN_PROSE_WORDS

    @staticmethod
    def _matches_confident_heading_line(lines: list) -> bool:
        """A page also counts as the start of real content when one of its
        own top lines is confidently heading-shaped by typography (bold + a
        real font-size lift) AND the page also has a genuine prose line
        elsewhere -- so a report chapter titled something outside
        MAJOR_SECTION_ALIASES's exact wording (and with no numbering) still
        gets its page classified as "content", without requiring an exact
        alias hit.

        Typography alone is deliberately NOT enough: a title/declaration/
        cover page in these reports is typically made of several short,
        bold, larger-than-body lines too (an institution name, "SUBMITTED
        BY:", a person's name in caps) that read as heading-shaped by pure
        shape/typography, but the page as a whole has no actual running
        prose -- only short labels. A real chapter-start page always has at
        least one full sentence of body text following its heading; a
        cover/declaration page never does. Requiring that companion prose
        line is what tells the two apart without needing numbering or a
        semantic-role hit, which a legitimately novel-worded first heading
        may have neither of."""
        heading_found = any(
            DocumentPageClassifier._is_confident_heading_shaped(line) for line in lines
        )
        if not heading_found:
            return False
        return any(DocumentPageClassifier._is_prose_line(line) for line in lines)

    @staticmethod
    def classify(pages):
        classified = []
        current_sequence_state = "cover"

        for idx, page in enumerate(pages):
            page_num = idx + 1
            lines = page.get("lines", [])
            top_lines = [
                DocumentPageClassifier._normalize_line(line["text"]).lower()
                for line in lines[:30]
            ]
            raw_top_lines = [
                DocumentPageClassifier._normalize_line(line["text"])
                for line in lines[:30]
            ]
            top_line_dicts = lines[:30]

            if page_num == 1:
                page["page_type"] = "cover"
                classified.append(page)
                continue

            matched_state = None

            if any(DocumentPageClassifier.TOC_TITLE.match(line) for line in top_lines):
                matched_state = "toc"
            elif any(DocumentPageClassifier.FIGURES_TITLE.match(line) for line in top_lines):
                matched_state = "list_of_figures"
            elif any(DocumentPageClassifier.TABLES_TITLE.match(line) for line in top_lines):
                matched_state = "list_of_tables"
            elif any(DocumentPageClassifier.ABBR_TITLE.match(line) for line in top_lines):
                matched_state = "list_of_abbreviations"
            elif any(DocumentPageClassifier.ABSTRACT.search(line) for line in raw_top_lines[:30]):
                matched_state = "abstract"
            elif any(DocumentPageClassifier.ACKNOWLEDGEMENT.match(line) for line in top_lines):
                matched_state = "acknowledgement"
            elif any(DocumentPageClassifier.APPROVAL.search(line) for line in top_lines):
                matched_state = "approval"
            elif any(DocumentPageClassifier.COPYRIGHT.search(line) for line in top_lines):
                matched_state = "copyright"
            # Explicit chapter-start evidence (a numbered heading, a known
            # section alias, or a confidently heading-shaped line) is
            # checked BEFORE the loose abstract-paragraph heuristic below --
            # an actual "1. Introduction" heading on a page is much stronger,
            # more specific evidence than a page merely containing two of a
            # handful of common project-description phrases, and must never
            # be preempted by that weaker heuristic (which would otherwise
            # silently swallow the real chapter-start page as "abstract",
            # losing the whole page's content -- it's never revisited once
            # classification has moved past it).
            elif any(DocumentPageClassifier._matches_chapter_start(line) for line in raw_top_lines):
                matched_state = "content"
            elif any(DocumentPageClassifier._matches_known_section_alias(line) for line in raw_top_lines):
                matched_state = "content"
            elif DocumentPageClassifier._matches_confident_heading_line(top_line_dicts):
                matched_state = "content"
            elif (
                page_num <= 8
                and current_sequence_state in ["cover", "approval", "acknowledgement"]
                and sum(
                    1 for keyword in [
                        "this project", "this study", "proposed system",
                        "the proposed", "aims to", "objective of this", "we propose",
                    ]
                    if keyword in " ".join(raw_top_lines).lower()
                ) >= 2
            ):
                matched_state = "abstract"

            if matched_state:
                current_sequence_state = matched_state
            elif current_sequence_state == "cover" and page_num == 2:
                current_sequence_state = "approval"

            page["page_type"] = current_sequence_state
            classified.append(page)

        return classified


class PageClassificationStep(BasePipelineStep):
    step_name = "Page Classification"

    def run(self, job: IngestionJob, context: dict) -> dict:
        reconstructed_pages = context.get("reconstructed_pages", [])
        classified = DocumentPageClassifier.classify(reconstructed_pages)
        context["classified_pages"] = classified
        self.log(job, f"Page classification finished for {len(classified)} pages.")
        return context
