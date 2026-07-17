"""
Semantic Academic Chapter Chunker.

Walks classified pages and creates chunks aligned with
chapter/section boundaries.

Each chunk receives hierarchy metadata inherited from
the latest detected heading.

Compatible with PostgreSQL + pgvector document_chunks schema.

Handles:
- CHAPTER 1 Introduction
- Chapter 1 + Introduction on next line
- 1 Introduction
- 1.1 Background
- 2.3 Dataset

Also prevents false positives where normal text starts
with numbers.
"""

import re

from .heading_utils import looks_like_heading


class AcademicSemanticChunker:


    CHAPTER_PAT = re.compile(
        r"""
        ^
        (?:
            chapter\s+([vixlcdm\d\w]+)[\s.:\-]*(.*)
            |
            (\d+)\s+(.+)
        )
        $
        """,
        re.IGNORECASE | re.VERBOSE,
    )


    SECTION_PAT = re.compile(
        r"^(\d+\.\d+(?:\.\d+)*)\s+(.+)$"
    )


    MAX_CHUNK_WORDS = 500



    @staticmethod
    def chunk_document(classified_pages):


        chunks = []


        current_chapter_num = ""
        current_chapter_title = ""

        current_section_num = ""
        current_section_title = ""


        current_chunk_buffer = []

        active_metadata = {}

        awaiting_chapter_title = False



        def flush_buffer():

            if not current_chunk_buffer:
                return


            text = "\n".join(
                current_chunk_buffer
            ).strip()


            if text:

                chunks.append(
                    {
                        "chunk_index": len(chunks),

                        "text": text,

                        "metadata":
                            active_metadata.copy()
                    }
                )


            current_chunk_buffer.clear()



        for page in classified_pages:


            page_num = page.get(
                "page_number"
            )


            page_type = page.get(
                "page_type"
            )


            lines = page.get(
                "lines",
                []
            )



            # -----------------------------
            # Front Matter
            # -----------------------------

            if page_type != "content":


                page_text = "\n".join(
                    line["text"]
                    for line in lines
                ).strip()


                if page_text:

                    chunks.append(
                        {
                            "text": page_text,

                            "metadata":
                            {
                                "page_number": page_num,
                                "page_end": page_num,
                                "page_type": page_type,

                                "chapter": "0",

                                "chapter_title":
                                    "Front Matter",

                                "section":
                                    page_type.upper(),

                                "section_number":
                                    page_type.upper(),

                                "section_title":
                                    page_type.replace(
                                        "_",
                                        " "
                                    ).title()
                            }
                        }
                    )


                continue



            # -----------------------------
            # Content Pages
            # -----------------------------

            for line_obj in lines:


                line_text = line_obj["text"].strip()


                if not line_text:
                    continue



                chap_match = (
                    AcademicSemanticChunker
                    .CHAPTER_PAT
                    .match(line_text)
                )


                sec_match = (
                    AcademicSemanticChunker
                    .SECTION_PAT
                    .match(line_text)
                )



                if chap_match:


                    title_candidate = (
                        chap_match.group(2)
                        or
                        chap_match.group(4)
                        or ""
                    )


                    if (
                        title_candidate.strip()
                        and
                        not looks_like_heading(
                            title_candidate
                        )
                    ):

                        chap_match = None



                if sec_match:

                    if not looks_like_heading(
                        sec_match.group(2)
                    ):

                        sec_match = None



                # -----------------------------
                # Chapter title next line
                # -----------------------------

                if (
                    awaiting_chapter_title
                    and
                    not chap_match
                    and
                    not sec_match
                ):


                    awaiting_chapter_title = False


                    if looks_like_heading(
                        line_text
                    ):


                        current_chapter_title = line_text
                        current_section_title = line_text


                        active_metadata.update(
                            {
                                "chapter_title":
                                    current_chapter_title,

                                "section_title":
                                    current_section_title
                            }
                        )


                        continue



                # -----------------------------
                # Chapter Heading
                # -----------------------------

                if chap_match:


                    flush_buffer()


                    if chap_match.group(1):

                        current_chapter_num = (
                            chap_match.group(1)
                            .upper()
                        )


                        current_chapter_title = (
                            chap_match.group(2)
                            .strip()
                        )


                    else:

                        current_chapter_num = (
                            chap_match.group(3)
                        )


                        current_chapter_title = (
                            chap_match.group(4)
                            .strip()
                        )



                    current_section_num = (
                        current_chapter_num
                    )


                    current_section_title = (
                        current_chapter_title
                    )


                    awaiting_chapter_title = (
                        not current_chapter_title
                    )


                    active_metadata = {

                        "page_number":
                            page_num,

                        "page_type":
                            "content",

                        "chapter":
                            current_chapter_num,

                        "chapter_title":
                            current_chapter_title,


                        "section_number":
                            current_section_num,

                        "section_title":
                            current_section_title

                    }


                    continue



                # -----------------------------
                # Section Heading
                # -----------------------------

                if sec_match:


                    flush_buffer()


                    awaiting_chapter_title = False


                    current_section_num = (
                        sec_match.group(1)
                    )


                    current_section_title = (
                        sec_match.group(2)
                        .strip()
                    )


                    active_metadata = {

                        "page_number":
                            page_num,

                        "page_type":
                            "content",

                        "chapter":
                            current_chapter_num,

                        "chapter_title":
                            current_chapter_title,

                        "section":
                            current_section_num,

                        "section_number":
                            current_section_num,

                        "section_title":
                            current_section_title

                    }


                    continue



                # -----------------------------
                # Normal text
                # -----------------------------

                if not active_metadata:


                    active_metadata = {

                        "page_number":
                            page_num,

                        "page_type":
                            "content",

                        "chapter":
                            current_chapter_num,

                        "chapter_title":
                            current_chapter_title,

                        "section":
                            current_section_num or "General",

                        "section_number":
                            current_section_num or "General",

                        "section_title":
                            current_section_title
                            or
                            "Body Paragraphs"

                    }



                current_chunk_buffer.append(
                    line_text
                )


                word_count = sum(
                    len(x.split())
                    for x in current_chunk_buffer
                )


                if word_count >= AcademicSemanticChunker.MAX_CHUNK_WORDS:

                    flush_buffer()



        flush_buffer()


        return chunks