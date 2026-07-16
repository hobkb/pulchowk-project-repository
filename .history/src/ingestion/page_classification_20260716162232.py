"""
Robust Document Page Classifier (Deterministic State Engine).

Walks through a document's pages in order and tags each one with a
`page_type` (cover, toc, list_of_figures, list_of_tables,
list_of_abbreviations, abstract, acknowledgement, approval, content),
carrying state forward between pages when no explicit heading is found.
"""

import re


class DocumentPageClassifier:
    # Anchor Header Regular Expressions
    TOC_TITLE = re.compile(r"^(contents|table\s+of\s+contents)$", re.IGNORECASE)
    FIGURES_TITLE = re.compile(r"^list\s+of\s+figures$", re.IGNORECASE)
    TABLES_TITLE = re.compile(r"^list\s+of\s+tables$", re.IGNORECASE)
    ABBR_TITLE = re.compile(r"^list\s+of\s+abbreviations$", re.IGNORECASE)

    APPROVAL = re.compile(r"page\s+of\s+approval|approval\s+page", re.IGNORECASE)
    COPYRIGHT = re.compile(r"copyright\s+page|copyright\s+©", re.IGNORECASE)
    ACKNOWLEDGEMENT = re.compile(r"^acknowledgements?$", re.IGNORECASE)
    ABSTRACT = re.compile(r"^abstract$", re.IGNORECASE)

    # Leader dots pattern for multi-page TOC tracking
    TOC_ENTRY = re.compile(r"\.{2,}\s*[a-zA-Z0-9_-]+\s*$")
    CHAPTER_START = re.compile(r"^(chapter\s+\d+|introduction)$", re.IGNORECASE)

    @staticmethod
    def classify(pages):
        classified = []
        current_sequence_state = "cover"

        for idx, page in enumerate(pages):
            page_num = idx + 1
            lines = page.get("lines", [])
            top_lines = [line["text"].strip().lower() for line in lines[:12]]

            has_toc_lines = sum(
                1 for l in lines if DocumentPageClassifier.TOC_ENTRY.search(l["text"])
            )

            # --- PHASE 1: HARD DETERMINISTIC OVERRIDES (Pages 1 & 2) ---
            if page_num in [1, 2]:
                page["page_type"] = "cover"
                classified.append(page)
                continue

            # --- PHASE 2: EXPLICIT HEADER INTERCEPTS ---
            matched_state = None

            if any(DocumentPageClassifier.TOC_TITLE.match(line) for line in top_lines):
                matched_state = "toc"
            elif any(DocumentPageClassifier.FIGURES_TITLE.match(line) for line in top_lines):
                matched_state = "list_of_figures"
            elif any(DocumentPageClassifier.TABLES_TITLE.match(line) for line in top_lines):
                matched_state = "list_of_tables"
            elif any(DocumentPageClassifier.ABBR_TITLE.match(line) for line in top_lines):
                matched_state = "list_of_abbreviations"
            elif any(DocumentPageClassifier.ABSTRACT.match(line) for line in top_lines):
                matched_state = "abstract"
            elif any(DocumentPageClassifier.ACKNOWLEDGEMENT.match(line) for line in top_lines):
                matched_state = "acknowledgement"
            elif any(DocumentPageClassifier.APPROVAL.search(line) for line in top_lines):
                matched_state = "approval"
            elif any(DocumentPageClassifier.CHAPTER_START.match(line) for line in top_lines):
                matched_state = "content"

            # --- PHASE 3: STATEFUL CONTEXT ENGINE ---
            if matched_state:
                current_sequence_state = matched_state
            else:
                if current_sequence_state == "cover" and page_num == 3:
                    current_sequence_state = "approval"
                elif current_sequence_state in ["toc", "list_of_figures", "list_of_tables", "list_of_abbreviations"]:
                    if has_toc_lines >= 2:
                        pass  # Retain current list state
                    elif page_num >= 12:
                        current_sequence_state = "content"

            page["page_type"] = current_sequence_state
            classified.append(page)

        return classified
