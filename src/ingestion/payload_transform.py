"""
V10 Ingestion Layer: Multi-Anchor Header Cleaving Title Extractor.

Transforms semantic chunks into flat, DRF-ready payload records, and
extracts a clean project title from the cover page by cleaving off
institutional header noise (university/campus names) from the top and
the submission block from the bottom.
"""

import re


class DjangoIngestionTransformer:

    @staticmethod
    def extract_clean_project_title(raw_cover_text):
        """
        Extracts the project title by cleaving off the continuous block of
        institutional headers at the top and cutting off at the earliest
        submission marker below.
        """
        lines = [line.strip() for line in raw_cover_text.split("\n") if line.strip()]
        if not lines:
            return "UNKNOWN PROJECT TITLE"

        # Step 1: Find where the submission section begins (earliest bottom boundary)
        end_idx = len(lines)
        for i, line in enumerate(lines):
            if re.search(r"\bSUBMITTED\b", line, re.IGNORECASE):
                end_idx = i
                break

        # Step 2: Find the LAST institutional header line at the top (top boundary cleavage)
        header_noise_patterns = [
            r"\bTRIBHUVAN\b", r"\bUNIVERSITY\b", r"\bINSTITUTE\b", r"\bCAMPUS\b",
            r"\bPULCHOWK\b", r"\bTHAPATHALI\b", r"\bERC\b", r"\bWRC\b",
            r"\bPROJECT\s+REPORT\b", r"\bMAJOR\b", r"\bMINOR\b", r"\bMINI\b",
        ]

        last_header_idx = -1
        for i in range(end_idx):
            is_header = any(re.search(pattern, lines[i], re.IGNORECASE) for pattern in header_noise_patterns)
            if is_header:
                last_header_idx = i

        # Step 3: Slice the exact window where the title lives
        start_idx = last_header_idx + 1
        while start_idx < end_idx and lines[start_idx].upper() in ["ON", "FOR", "A", "AN", "OF"]:
            start_idx += 1

        title_lines = lines[start_idx:end_idx]

        # Step 4: Fallback protection if boundaries squeezed out text
        if not title_lines:
            title_lines = [lines[end_idx - 1]] if end_idx > 0 else [lines[0]]

        # Step 5: Combine lines and strip structural punctuation/quotes cleanly
        candidate_title = " ".join(title_lines)
        final_title = re.sub(r'[\u201c\u201d\u2018\u2019"\'\u201c\u201d]', "", candidate_title)
        final_title = re.sub(r"\s+", " ", final_title).strip(" ,-\u2014_:")

        return final_title.upper() if final_title else "UNKNOWN PROJECT TITLE"

    @staticmethod
    def calculate_token_estimate(text):
        return int(len(text.split()) * 1.33)

    @staticmethod
    def transform_to_payload(chunks):
        payloads = []

        # Extract title safely using layout boundaries
        global_title = "UNKNOWN PROJECT TITLE"
        for chunk in chunks:
            if chunk["metadata"].get("page_type") == "cover":
                global_title = DjangoIngestionTransformer.extract_clean_project_title(chunk["text"])
                break

        # Map semantic units into content payloads for Django REST Framework ingestion
        valid_chunk_index = 0
        for chunk in chunks:
            meta = chunk["metadata"]
            if meta.get("page_type") == "cover":
                continue

            text_content = chunk["text"]

            record = {
                "chunk_index": valid_chunk_index,
                "page_number": meta["page_number"],
                "page_type": meta["page_type"],
                "hierarchy": {
                    "project_title": global_title,
                    "chapter": meta["chapter"],
                    "chapter_title": meta["chapter_title"],
                    "section_number": meta["section"],
                    "section_title": meta["section_title"],
                },
                "estimated_tokens": DjangoIngestionTransformer.calculate_token_estimate(text_content),
                "content_body": text_content,
            }
            payloads.append(record)
            valid_chunk_index += 1

        return payloads
