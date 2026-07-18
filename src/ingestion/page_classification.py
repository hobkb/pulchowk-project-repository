"""
Robust Document Page Classifier (Deterministic State Engine).

Walks through a document's pages in order and tags each one with a
`page_type` (cover, toc, list_of_figures, list_of_tables,
list_of_abbreviations, abstract, acknowledgement, approval, content),
carrying state forward between pages when no explicit heading is found.
"""

import re
from .heading_utils import looks_like_heading

from .domain_classifier import classify_project_domain


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

    APPROVAL = re.compile(
        r"(page\s+of\s+approval|approval\s+page|certificate\s+of\s+approval|approval)",
        re.IGNORECASE
    )

    COPYRIGHT = re.compile(
        r"(copyright\s+page|copyright\s+©|copyright)",
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


    TOC_ENTRY = re.compile(
        r"\.{2,}\s*[a-zA-Z0-9_-]+\s*$"
    )


    CHAPTER_START = re.compile(
        r"^(?:chapter\s+([ivxlcdm\d]+)\b[\s.:\-]*(.*)|(\d+)\s+(.+)|(introduction)\s*(.*))$",
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


            has_toc_lines = sum(
                1
                for l in lines
                if DocumentPageClassifier.TOC_ENTRY.search(l["text"])
            )


            if page_num in [1, 2]:

                page["page_type"] = "cover"

                classified.append(page)

                continue



            matched_state = None


            if any(
                DocumentPageClassifier.TOC_TITLE.match(line)
                for line in top_lines
            ):

                matched_state = "toc"


            elif any(
                DocumentPageClassifier.FIGURES_TITLE.match(line)
                for line in top_lines
            ):

                matched_state = "list_of_figures"


            elif any(
                DocumentPageClassifier.TABLES_TITLE.match(line)
                for line in top_lines
            ):

                matched_state = "list_of_tables"


            elif any(
                DocumentPageClassifier.ABBR_TITLE.match(line)
                for line in top_lines
            ):

                matched_state = "list_of_abbreviations"


            elif any(
                DocumentPageClassifier.ABSTRACT.search(line)
                for line in raw_top_lines[:30]
            ):

                matched_state = "abstract"


            elif (
                page_num <= 8
                and current_sequence_state in [
                    "cover",
                    "approval",
                    "acknowledgement",
                ]
            ):

                page_text = " ".join(
                    raw_top_lines
                ).lower()

                abstract_keywords = [
                    "this project",
                    "this study",
                    "proposed system",
                    "the proposed",
                    "aims to",
                    "objective of this",
                    "we propose",
                ]

                abstract_hits = sum(
                    1
                    for keyword in abstract_keywords
                    if keyword in page_text
                )

                if abstract_hits >= 2:
                    matched_state = "abstract"


            elif any(
                DocumentPageClassifier.ACKNOWLEDGEMENT.match(line)
                for line in top_lines
            ):

                matched_state = "acknowledgement"


            elif any(
                DocumentPageClassifier.APPROVAL.search(line)
                for line in top_lines
            ):

                matched_state = "approval"


            elif any(
                DocumentPageClassifier.COPYRIGHT.search(line)
                for line in top_lines
            ):

                matched_state = "copyright"


            elif any(
                DocumentPageClassifier._matches_chapter_start(line)
                for line in raw_top_lines
            ):

                matched_state = "content"



            if matched_state:

                current_sequence_state = matched_state


            else:

                if current_sequence_state == "cover" and page_num == 3:

                    current_sequence_state = "approval"


                elif current_sequence_state in [
                    "toc",
                    "list_of_figures",
                    "list_of_tables",
                    "list_of_abbreviations"
                ]:

                    if has_toc_lines >= 2:

                        pass

                    elif page_num >= 12:

                        current_sequence_state = "content"



            page["page_type"] = current_sequence_state

            classified.append(page)



        return classified





def process_document_and_classify_domain(pages: list) -> tuple[list, str]:

    """
    1. Runs the exact DocumentPageClassifier state machine.
    2. Isolates abstract/content text.
    3. Executes domain classifier.
    """

    classified_pages = DocumentPageClassifier.classify(pages)


    abstract_text_parts = []

    content_fallback_parts = []


    for page in classified_pages:

        page_text = " ".join(
            [
                line["text"]
                for line in page.get("lines", [])
            ]
        )


        if page.get("page_type") == "abstract":

            abstract_text_parts.append(page_text)


        elif (
            page.get("page_type") == "content"
            and len(content_fallback_parts) < 3
        ):

            content_fallback_parts.append(page_text)



    target_classification_text = (

        " ".join(abstract_text_parts)

        if abstract_text_parts

        else " ".join(content_fallback_parts)

    )


    assigned_domain = classify_project_domain(
        target_classification_text
    )


    return classified_pages, assigned_domain    