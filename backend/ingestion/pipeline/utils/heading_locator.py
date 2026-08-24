"""
Finding which real PDF page a manually-typed heading corresponds to.

Used from the review screen: a reviewer adds a section by hand and types a
heading like "System Design", and this looks through the document's own
content pages for a line that matches it, returning just the page number
that heading actually starts on -- never the matched text itself, so a
lookup never puts document content into a response body.

Kept separate from the section-extraction pipeline (`section_tree.py`)
because it solves a different problem: extraction discovers ALL headings in
one forward pass, while this searches for ONE specific, already-known
heading string on demand.
"""

from rapidfuzz import fuzz

from ingestion.pipeline.steps.line_reconstruction import LineReconstructionStep
from ingestion.pipeline.steps.page_classification import PageClassificationStep
from ingestion.pipeline.steps.pdf_extraction import PDFExtractionStep
from ingestion.pipeline.utils.section_aliases import normalize_major_heading
from ingestion.pipeline.utils.section_tree import content_body_font_size
from ingestion.pipeline.utils.text_cleaners import normalize_line

# Below this, a match is treated as coincidence rather than the real
# heading -- a paraphrase or a caption mentioning the same words in passing
# should not silently redirect a section to the wrong page.
_MATCH_THRESHOLD = 82

# A candidate line must look at least this much larger than the surrounding
# body text (or be bold) to be considered a heading at all, so an ordinary
# sentence that happens to reuse the typed words is never a match --
# consistent with the boldness/font-ratio signal score_heading_candidate
# already uses to accept real headings during extraction.
_FONT_RATIO_FLOOR = 1.15


def locate_heading_page(job, heading_text):
    """Returns the 1-based page number a heading most likely starts on, or
    None if nothing in the document's content pages matches confidently.

    Runs PDF extraction fresh against `job.file` -- read-only, nothing
    about the job is written -- rather than depending on any previous
    run's output, so it works even for a job whose transient pipeline
    context has long since been discarded.
    """
    query = normalize_major_heading(normalize_line(heading_text or "")).strip()
    if not query:
        return None

    context = {"start_time": 0, "stop_pipeline": False}
    context = PDFExtractionStep().run(job, context)
    context = LineReconstructionStep().run(job, context)
    context = PageClassificationStep().run(job, context)
    pages = context.get("classified_pages", [])

    body_font_size = content_body_font_size(pages)

    best_score = 0
    best_page = None

    for page in pages:
        # Only real chapter pages count. A heading's entry in the Table of
        # Contents ("System Design .......... 34") would otherwise match
        # just as well and report the ToC's own page instead of the page
        # the content actually starts on.
        if page.get("page_type") != "content":
            continue

        page_number = page.get("page_number", page.get("page_num"))
        if page_number is None:
            continue

        for line in page.get("lines", []):
            raw = normalize_line(line.get("text", ""))
            if not raw:
                continue

            is_bold = bool(line.get("is_bold", False))
            try:
                font_size = float(line.get("font_size") or 0)
            except (TypeError, ValueError):
                font_size = 0.0
            font_ratio = (font_size / body_font_size) if body_font_size else 1.0
            if not is_bold and font_ratio < _FONT_RATIO_FLOOR:
                continue

            candidate = normalize_major_heading(raw)
            if not candidate:
                continue

            score = fuzz.ratio(query.lower(), candidate.lower())
            if score > best_score:
                best_score = score
                best_page = page_number

    return best_page if best_score >= _MATCH_THRESHOLD else None
