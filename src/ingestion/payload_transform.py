"""
V10 Ingestion Layer: Multi-Anchor Header Cleaving Title Extractor.

Transforms semantic chunks into flat, DRF-ready payload records, and
extracts a clean project title from the cover page by removing
institutional header noise and submission metadata.
"""


import re



class DjangoIngestionTransformer:


    EXCLUDED_PAGE_TYPES = {
        "cover",
        "toc",
        "list_of_figures",
        "list_of_tables",
        "list_of_abbreviations",
        "approval",
        "acknowledgement",
        "copyright",
    }



    @staticmethod
    def extract_clean_project_title(raw_cover_text):

        """
        Extract clean academic project title from cover page.
        Removes:
        - university/campus headers
        - report labels
        - submission blocks
        - student information
        - dates
        - roll numbers
        """

        lines = [
            line.strip()
            for line in raw_cover_text.split("\n")
            if line.strip()
        ]


        if not lines:

            return "UNKNOWN PROJECT TITLE"



        submission_patterns = [

    r"\bsubmitted\s+by\b",

    r"\bsubmitted\s+to\b",

    r"\bprepared\s+by\b",

    r"\bunder\s+the\s+guidance\b",

    r"\bguided\s+by\b",

    r"\bsupervised\s+by\b",

    r"\bdepartment\b",

    r"\bsubmitted\s+in\b",

    r"\bsubmitted\s+for\b",

]



        end_idx = len(lines)



        for index, line in enumerate(lines):

            if any(
                re.search(
                    pattern,
                    line,
                    re.IGNORECASE
                )
                for pattern in submission_patterns
            ):

                end_idx = index

                break



        header_noise_patterns = [

            r"\bTRIBHUVAN\b",

            r"\bUNIVERSITY\b",

            r"\bINSTITUTE\b",

            r"\bCAMPUS\b",

            r"\bPULCHOWK\b",

            r"\bTHAPATHALI\b",

            r"\bERC\b",

            r"\bWRC\b",

            r"\bPROJECT\s+REPORT\b",

            r"\bMAJOR\s+PROJECT\b",

            r"\bMINOR\s+PROJECT\b",

            r"\bMINI\s+PROJECT\b",

            r"\bA\s+REPORT\b",

        ]



        last_header_index = -1



        for index in range(end_idx):

            if any(
                re.search(
                    pattern,
                    lines[index],
                    re.IGNORECASE
                )
                for pattern in header_noise_patterns
            ):

                last_header_index = index



        start_index = last_header_index + 1



        while (
            start_index < end_idx
            and lines[start_index].upper()
            in [
                "ON",
                "FOR",
                "A",
                "AN",
                "OF"
            ]
        ):

            start_index += 1



        title_lines = lines[start_index:end_idx]



        cleaned_lines = []



        for line in title_lines:


            # Remove publication date lines

            if re.search(
                r"\b("
                r"January|February|March|April|May|June|"
                r"July|August|September|October|November|December|"
                r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
                r")"
                r"\s*,?\s*\d{4}",
                line,
                re.IGNORECASE
            ):

                continue



            # Remove roll numbers

            if re.search(
                r"\b(?:[A-Z]{2,5}\s*)?\d{3}\s*[A-Z]{2,5}\s*\d{3}\b",
                line,
                re.IGNORECASE
            ):

                continue



            # Remove obvious student metadata

            if re.search(
                r"\b("
                r"submitted|prepared|supervisor|"
                r"department|guided|guidance"
                r")\b",
                line,
                re.IGNORECASE
            ):

                continue



            cleaned_lines.append(line)



        title_lines = cleaned_lines



        if not title_lines:

            return "UNKNOWN PROJECT TITLE"



        candidate_title = " ".join(
            title_lines
        )



        candidate_title = re.sub(
            r'[\u201c\u201d\u2018\u2019"\']',
            "",
            candidate_title
        )


        candidate_title = re.sub(
            r"\s+",
            " ",
            candidate_title
        ).strip(
            " ,-\u2014_:"
        )



        return (
            candidate_title.upper()
            if candidate_title
            else
            "UNKNOWN PROJECT TITLE"
        )



    @staticmethod
    def calculate_token_estimate(text):

        return int(
            len(text.split()) * 1.33
        )



    @staticmethod
    def get_project_title(chunks):

        """
        Finds cover page chunk and extracts title.
        Used by both content and project level processing.
        """


        for chunk in chunks:

            if (
                chunk["metadata"]
                .get("page_type")
                ==
                "cover"
            ):

                return (
                    DjangoIngestionTransformer
                    .extract_clean_project_title(
                        chunk["text"]
                    )
                )


        return "UNKNOWN PROJECT TITLE"



    @staticmethod
    def transform_to_payload(chunks):


        payloads = []



        global_title = (
            DjangoIngestionTransformer
            .get_project_title(
                chunks
            )
        )



        valid_chunk_index = 0



        for chunk in chunks:


            meta = chunk["metadata"]



            if (
                meta.get("page_type")
                in DjangoIngestionTransformer.EXCLUDED_PAGE_TYPES
            ):

                continue



            text_content = chunk["text"]



            record = {


                "chunk_index":
                    valid_chunk_index,


                "page_number":
                    meta.get(
                        "page_number",
                        0
                    ),


                "page_type":
                    meta.get(
                        "page_type",
                        "content"
                    ),


                "hierarchy": {


                    "project_title":
                        global_title,


                    "chapter":
                        meta.get(
                            "chapter",
                            ""
                        ),


                    "chapter_title":
                        meta.get(
                            "chapter_title",
                            ""
                        ),


                    "section_number":
                        meta.get(
                            "section_number",
                            meta.get(
                                "section",
                                "General"
                            )
                        ),


                    "section_title":
                        meta.get(
                            "section_title",
                            "Body Paragraphs"
                        ),

                },


                "estimated_tokens":
                    DjangoIngestionTransformer
                    .calculate_token_estimate(
                        text_content
                    ),


                "character_count":
                    len(text_content),


                "content":
                    text_content,


                "metadata":
                    meta

            }



            payloads.append(record)

            valid_chunk_index += 1



        return payloads