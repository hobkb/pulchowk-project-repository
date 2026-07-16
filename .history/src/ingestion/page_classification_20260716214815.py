"""
Robust Document Page Classifier (Deterministic State Engine).

Walks through a document's pages in order and tags each one with a
`page_type` (cover, toc, list_of_figures, list_of_tables,
list_of_abbreviations, abstract, acknowledgement, approval, content),
carrying state forward between pages when no explicit heading is found.
"""

import re


class DocumentPageClassifier:

    # ---------------------------------------------------------
    # Anchor Header Regular Expressions
    # ---------------------------------------------------------

    TOC_TITLE = re.compile(
        r"^(contents|table\s+of\s+contents)$",
        re.IGNORECASE
    )

    FIGURES_TITLE = re.compile(
        r"^list\s+of\s+figures$",
        re.IGNORECASE
    )

    TABLES_TITLE = re.compile(
        r"^list\s+of\s+tables$",
        re.IGNORECASE
    )

    ABBR_TITLE = re.compile(
        r"^list\s+of\s+abbreviations$",
        re.IGNORECASE
    )

    APPROVAL = re.compile(
        r"(page\s+of\s+approval|approval\s+page)",
        re.IGNORECASE
    )

    COPYRIGHT = re.compile(
        r"copyright",
        re.IGNORECASE
    )

    ACKNOWLEDGEMENT = re.compile(
        r"^acknowledgements?$",
        re.IGNORECASE
    )

    ABSTRACT = re.compile(
        r"^abstract$",
        re.IGNORECASE
    )

    # ---------------------------------------------------------
    # TOC Detection
    # Works for:
    # ...............18
    # . . . . . . . 18
    # ---------------------------------------------------------

    TOC_ENTRY = re.compile(
        r"(\.{2,}|(\.\s*){4,}).*\d+\s*$"
    )

    # ---------------------------------------------------------
    # Beginning of actual report
    # ---------------------------------------------------------

    CHAPTER_START = re.compile(
        r"""
        ^
        (
            \d+\s+
            (
                introduction|
                literature\s+review|
                theory|
                methodology|
                system\s+design|
                implementation|
                results|
                discussion|
                limitations|
                future(\s+improvements)?|
                references|
                appendix
            )
            |
            chapter\s+\d+
        )
        $
        """,
        re.IGNORECASE | re.VERBOSE
    )

    @staticmethod
    def classify(pages):

        classified = []

        current_sequence_state = "cover"

        for idx, page in enumerate(pages):

            page_num = idx + 1

            lines = page.get("lines", [])

            top_lines = [
                line["text"].strip().lower()
                for line in lines[:12]
                if line["text"].strip()
            ]

            toc_entries = sum(
                1
                for line in lines
                if DocumentPageClassifier.TOC_ENTRY.search(
                    line["text"]
                )
            )

            # -------------------------------------------------
            # Cover Page
            # -------------------------------------------------

            if page_num == 1:
                page["page_type"] = "cover"
                current_sequence_state = "cover"
                classified.append(page)
                continue

            matched_state = None

            # -------------------------------------------------
            # Explicit Header Detection
            # -------------------------------------------------

            if any(DocumentPageClassifier.TOC_TITLE.match(x) for x in top_lines):

                matched_state = "toc"

            elif any(DocumentPageClassifier.FIGURES_TITLE.match(x) for x in top_lines):

                matched_state = "list_of_figures"

            elif any(DocumentPageClassifier.TABLES_TITLE.match(x) for x in top_lines):

                matched_state = "list_of_tables"

            elif any(DocumentPageClassifier.ABBR_TITLE.match(x) for x in top_lines):

                matched_state = "list_of_abbreviations"

            elif any(DocumentPageClassifier.ABSTRACT.match(x) for x in top_lines):

                matched_state = "abstract"

            elif any(DocumentPageClassifier.ACKNOWLEDGEMENT.match(x) for x in top_lines):

                matched_state = "acknowledgement"

            elif any(DocumentPageClassifier.APPROVAL.search(x) for x in top_lines):

                matched_state = "approval"

            elif any(DocumentPageClassifier.COPYRIGHT.search(x) for x in top_lines):

                matched_state = "copyright"

            elif any(DocumentPageClassifier.CHAPTER_START.match(x) for x in top_lines):

                matched_state = "content"

            # -------------------------------------------------
            # Stateful Engine
            # -------------------------------------------------

            if matched_state:

                current_sequence_state = matched_state

            else:

                # Stay inside TOC / Lists while dotted entries exist
                if current_sequence_state in {

                    "toc",
                    "list_of_figures",
                    "list_of_tables",
                    "list_of_abbreviations"

                }:

                    if toc_entries >= 2:

                        pass

                    elif any(
                        DocumentPageClassifier.CHAPTER_START.match(x)
                        for x in top_lines
                    ):

                        current_sequence_state = "content"

                # Abstract normally transitions directly into content
                elif current_sequence_state == "abstract":

                    if any(
                        DocumentPageClassifier.CHAPTER_START.match(x)
                        for x in top_lines
                    ):

                        current_sequence_state = "content"

            page["page_type"] = current_sequence_state

            classified.append(page)

        return classified