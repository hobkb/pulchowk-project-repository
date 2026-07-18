"""
Document-level metadata extraction.

Extracts academic metadata that should not be embedded:

- student names
- student roll numbers
- supervisor information
- publication date

Stored separately from vector chunks.
"""


import re



class DocumentMetadataExtractor:


    MONTH_PATTERN = (
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    )


    ROLL_PATTERN = re.compile(
        r"\b(?:[A-Z]{2,5}\s*)?\d{3}\s*[A-Z]{2,5}\s*\d{3}\b",
        re.IGNORECASE
    )


    SUPERVISOR_PATTERN = re.compile(
        r"\b("
        r"supervisor|"
        r"supervised\s+by|"
        r"under\s+the\s+guidance\s+of|"
        r"guided\s+by|"
        r"guidance\s+of|"
        r"advisor|"
        r"adviser"
        r")\b",
        re.IGNORECASE
    )


    TITLE_PATTERN = re.compile(
        r"\b("
        r"prof\.?|"
        r"professor|"
        r"assoc\.?\s*prof\.?|"
        r"associate\s+prof\.?|"
        r"associate\s+professor|"
        r"asst\.?\s*prof\.?|"
        r"assistant\s+prof\.?|"
        r"assistant\s+professor|"
        r"dr\.?|"
        r"mr\.?|"
        r"mrs\.?|"
        r"ms\.?"
        r")\b",
        re.IGNORECASE
    )


    SUBMITTED_PATTERN = re.compile(
        r"\b(submitted\s*by|prepared\s*by)\b",
        re.IGNORECASE
    )


    STOP_STUDENT_PATTERN = re.compile(
        r"\b(supervisor|submitted\s+to|department|"
        r"institute|campus|tribhuvan|university|"
        r"under\s+the\s+guidance)\b",
        re.IGNORECASE
    )



    @staticmethod
    def normalize_line(text):

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()



    @staticmethod
    def clean_roll_number(roll):

        return re.sub(
            r"[^A-Za-z0-9]",
            "",
            roll
        ).upper()



    @staticmethod
    def extract_roll(line):

        match = (
            DocumentMetadataExtractor
            .ROLL_PATTERN
            .search(line)
        )


        if not match:

            return None



        return (
            DocumentMetadataExtractor
            .clean_roll_number(
                match.group()
            )
        )



    @staticmethod
    def extract_name_from_line(line):

        roll = (
            DocumentMetadataExtractor
            .extract_roll(
                line
            )
        )


        if roll:

            line = (
                DocumentMetadataExtractor
                .ROLL_PATTERN
                .sub(
                    "",
                    line
                )
            )


        line = re.sub(
            r"[\(\)\[\]]",
            "",
            line
        )


        line = re.sub(
            r"\s+",
            " ",
            line
        ).strip()



        if not line:

            return None



        return line.upper()
    @staticmethod
    def extract_students(cover_lines):


        students = []

        collecting = False


        for line in cover_lines:


            line = (
                DocumentMetadataExtractor
                .normalize_line(line)
            )


            if not line:

                continue



            if (
                DocumentMetadataExtractor
                .SUBMITTED_PATTERN
                .search(line)
            ):

                collecting = True


                after = re.split(
                    r":",
                    line,
                    maxsplit=1
                )


                if len(after) == 2:


                    candidate = after[1].strip()


                    if candidate:


                        roll = (
                            DocumentMetadataExtractor
                            .extract_roll(candidate)
                        )


                        if roll:


                            name = (
                                DocumentMetadataExtractor
                                .extract_name_from_line(candidate)
                            )


                            if (
                                name
                                and not
                                DocumentMetadataExtractor
                                .STOP_STUDENT_PATTERN
                                .search(name)
                            ):

                                students.append(
                                    {
                                        "name": name,
                                        "roll_number": roll
                                    }
                                )


                continue



            if not collecting:

                continue



            # stop collecting students
            # once university/institute section begins

            if (
                DocumentMetadataExtractor
                .STOP_STUDENT_PATTERN
                .search(line)
            ):

                break



            roll = (
                DocumentMetadataExtractor
                .extract_roll(line)
            )


            if roll:


                name = (
                    DocumentMetadataExtractor
                    .extract_name_from_line(line)
                )


                if (
                    name
                    and not
                    DocumentMetadataExtractor
                    .SUBMITTED_PATTERN
                    .search(name)
                ):

                    students.append(
                        {
                            "name": name,
                            "roll_number": roll
                        }
                    )



        # second pass:
        # NAME
        # ROLL NUMBER
        #
        # but only before Submitted To section


        for index in range(
            len(cover_lines)-1
        ):


            if len(students) >= 4:

                break



            current = (
                DocumentMetadataExtractor
                .normalize_line(
                    cover_lines[index]
                )
            )


            next_line = (
                DocumentMetadataExtractor
                .normalize_line(
                    cover_lines[index+1]
                )
            )



            if (
                not current
                or
                DocumentMetadataExtractor
                .STOP_STUDENT_PATTERN
                .search(current)
                or
                DocumentMetadataExtractor
                .SUBMITTED_PATTERN
                .search(current)
            ):

                continue



            roll = (
                DocumentMetadataExtractor
                .extract_roll(
                    next_line
                )
            )



            if not roll:

                continue



            name = (
                DocumentMetadataExtractor
                .extract_name_from_line(
                    current
                )
            )



            if not name:

                continue



            if (
                DocumentMetadataExtractor
                .TITLE_PATTERN
                .search(name)
            ):

                continue



            students.append(
                {
                    "name": name,
                    "roll_number": roll
                }
            )



        unique = []

        seen = set()



        for student in students:


            key = (
                student["name"],
                student["roll_number"]
            )


            if key not in seen:


                seen.add(key)

                unique.append(student)



        return unique[:4]
    @staticmethod
    def clean_supervisor_name(text):


        text = re.sub(
            r"\s+",
            " ",
            text
        ).strip()


        text = re.sub(
            r"^(name|:|-)\s*",
            "",
            text,
            flags=re.IGNORECASE
        )


        return text.strip(
            "() "
        ).upper()



    @staticmethod
    def extract_supervisor(pages):


        for page in pages:


            if page.get("page_type") not in [
                "approval",
                "acknowledgement",
                "cover"
            ]:

                continue



            lines = [

                line["text"]

                for line in page.get(
                    "lines",
                    []
                )

            ]



            for index, line in enumerate(lines):


                line = line.strip()



                if (
                    DocumentMetadataExtractor
                    .SUPERVISOR_PATTERN
                    .search(line)
                ):


                    parts = re.split(
                        r":",
                        line,
                        maxsplit=1
                    )


                    if len(parts) == 2:

                        candidate = parts[1].strip()

                        if candidate:

                            return {
                                "name":
                                DocumentMetadataExtractor
                                .clean_supervisor_name(
                                    candidate
                                )
                            }



                    for next_line in lines[index+1:index+4]:

                        candidate = next_line.strip()


                        if candidate:

                            return {
                                "name":
                                DocumentMetadataExtractor
                                .clean_supervisor_name(
                                    candidate
                                )
                            }



            for line in lines:


                if (
                    DocumentMetadataExtractor
                    .TITLE_PATTERN
                    .search(line)
                ):

                    candidate = line.strip()


                    if len(candidate.split()) <= 8:

                        return {
                            "name":
                            DocumentMetadataExtractor
                            .clean_supervisor_name(
                                candidate
                            )
                        }



        return None



    @staticmethod
    def extract_publication_date(cover_lines):


        text = " ".join(
            cover_lines
        )



        patterns = [

            DocumentMetadataExtractor.MONTH_PATTERN
            + r"\s*,?\s*(\d{4})",

            r"(\d{4})\s*,?\s*"
            + DocumentMetadataExtractor.MONTH_PATTERN

        ]



        for pattern in patterns:


            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )


            if match:


                groups = match.groups()



                if groups[0].isdigit():

                    year = groups[0]
                    month = groups[1]

                else:

                    month = groups[0]
                    year = groups[1]



                return {

                    "month":
                    month.capitalize(),

                    "year":
                    int(year)

                }



        return None



    @staticmethod
    def extract(pages):


        metadata = {

            "students": [],

            "supervisor": None,

            "publication": None,

            "source_pages": {}

        }



        cover_lines = []



        for page in pages:


            if page.get("page_type") == "cover":


                cover_lines.extend(
                    [
                        line["text"]
                        for line in page.get(
                            "lines",
                            []
                        )
                    ]
                )


                metadata["source_pages"]["cover"] = (
                    page.get("page_number")
                )



            if page.get("page_type") == "approval":


                metadata["source_pages"]["approval"] = (
                    page.get("page_number")
                )



        metadata["students"] = (
            DocumentMetadataExtractor
            .extract_students(
                cover_lines
            )
        )



        metadata["supervisor"] = (
            DocumentMetadataExtractor
            .extract_supervisor(
                pages
            )
        )



        metadata["publication"] = (
            DocumentMetadataExtractor
            .extract_publication_date(
                cover_lines
            )
        )


        return metadata