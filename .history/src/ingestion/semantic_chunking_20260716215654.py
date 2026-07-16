"""
Semantic Academic Chapter Chunker & Heading Tree Extractor.

Walks classified pages and groups their lines into chunks aligned with
chapter/section boundaries, so each chunk carries chapter/section metadata
inherited from the last heading seen.
"""

import re


class AcademicSemanticChunker:
    # "CHAPTER I", "CHAPTER 1", "CHAPTER ONE", "Chapter  1:"
    CHAPTER_PAT = re.compile(
    r"""
    ^
    (?:
        chapter\s+([vixlcdm\d\w]+)[\s.:\-]*(.*)
        |
        (\d+)\s+
        (
            Introduction|
            Literature\s+Review|
            Theory|
            Methodology|
            System\s+Design|
            Results|
            Discussion|
            Limitations|
            Future(?:\s+Improvements)?|
            References|
            Appendix
        )
    )
    $
    """,
    re.IGNORECASE | re.VERBOSE
)
    # "1.1 Background", "3.4.2 System Architecture"
    SECTION_PAT = re.compile(
    r"^(\d+\.\d+(?:\.\d+)*)\s+(.+)$"
)
    @staticmethod
    def chunk_document(classified_pages):
        chunks = []

        current_chapter_num = "0"
        current_chapter_title = "Front Matter"
        current_section_num = ""
        current_section_title = ""

        current_chunk_buffer = []
        active_metadata = {}

        def flush_buffer():
            if current_chunk_buffer:
                combined_text = "\n".join(current_chunk_buffer).strip()
                if combined_text:
                    chunks.append({
                        "text": combined_text,
                        "metadata": active_metadata.copy()
                    })
                current_chunk_buffer.clear()

        for page in classified_pages:
            page_num = page.get("page_number")
            page_type = page.get("page_type")
            lines = page.get("lines", [])

            if page_type != "content":
                page_text = "\n".join(line["text"] for line in lines).strip()
                if page_text:
                    chunks.append({
                        "text": page_text,
                        "metadata": {
                            "page_number": page_num,
                            "page_type": page_type,
                            "chapter": "0",
                            "chapter_title": "Front Matter",
                            "section": page_type.upper(),
                            "section_title": page_type.replace("_", " ").title(),
                        }
                    })
                continue

            for line_obj in lines:
                line_text = line_obj["text"].strip()
                if not line_text:
                    continue

                chap_match = AcademicSemanticChunker.CHAPTER_PAT.match(line_text)
                sec_match = AcademicSemanticChunker.SECTION_PAT.match(line_text)

                if chap_match:
                    flush_buffer()

                    # Case 1: CHAPTER 1 / CHAPTER I
                    if chap_match.group(1) is not None:
                        current_chapter_num = chap_match.group(1).upper()
                        current_chapter_title = chap_match.group(2).strip()

                    # Case 2: 1 Introduction / 2 Literature Review
                    else:
                        current_chapter_num = chap_match.group(3)
                        current_chapter_title = chap_match.group(4).strip()

                    current_section_num = ""
                    current_section_title = ""

                    active_metadata = {
                        "page_number": page_num,
                        "page_type": "content",
                        "chapter": current_chapter_num,
                        "chapter_title": current_chapter_title,
                        "section": current_chapter_num,
                        "section_title": current_chapter_title,
                    }

                    continue

                elif sec_match:
                    flush_buffer()

                    current_section_num = sec_match.group(1)
                    current_section_title = sec_match.group(2).strip()

                    active_metadata = {
                        "page_number": page_num,
                        "page_type": "content",
                        "chapter": current_chapter_num,
                        "chapter_title": current_chapter_title,
                        "section": current_section_num,
                        "section_title": current_section_title,
                    }

                    continue

                if not active_metadata:
                    active_metadata = {
                        "page_number": page_num,
                        "page_type": "content",
                        "chapter": current_chapter_num,
                        "chapter_title": current_chapter_title,
                        "section": "General",
                        "section_title": "Body Paragraphs",
                    }

                current_chunk_buffer.append(line_text)

        flush_buffer()
        return chunks
