"""
Thesis Section Coverage Checker.

Validates whether ingestion produced correctly classified
content sections before storing into PostgreSQL + pgvector.

Checks:

- Abstract
- Introduction
- Literature Review
- Methodology
- Results
- Discussion


Works with PostgreSQL ingestion payloads:

document_chunks
    |
    DjangoIngestionTransformer
    |
    processed_*.json backup


Used for detecting:
- heading detection failures
- incorrect chapter mapping
- missing semantic sections
"""


import json
import re


from .config import PAYLOADS_DIR



REQUIRED_SECTIONS = {


    "introduction":
        re.compile(
            r"\bintroduction\b",
            re.IGNORECASE
        ),


    "literature_review":
        re.compile(
            r"literature\s+review|"
            r"related\s+work|"
            r"background\s+study|"
            r"state\s+of\s+the\s+art|"
            r"existing\s+(work|research)",
            re.IGNORECASE
        ),


    "methodology":
        re.compile(
            r"methodolog|"
            r"system\s+design|"
            r"implementation|"
            r"architecture|"
            r"proposed\s+system|"
            r"experimental\s+setup",
            re.IGNORECASE
        ),


    "results":
        re.compile(
            r"\bresults?\b|"
            r"evaluation|"
            r"performance\s+analysis|"
            r"experimental\s+results|"
            r"results?\s*(and|&)\s*discussion",
            re.IGNORECASE
        ),


    "discussion":
        re.compile(
            r"\bdiscussion\b|"
            r"results?\s*(and|&)\s*discussion",
            re.IGNORECASE
        )

}







# -------------------------------------------------
# Load JSON payload backups
# -------------------------------------------------

def load_payload_backups():

    backups = {}


    for json_path in sorted(
        PAYLOADS_DIR.glob(
            "processed_*.json"
        )
    ):


        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as f:


            payloads = json.load(f)



        stem = json_path.stem.replace(
            "processed_",
            ""
        )


        filename = (
            f"{stem}.pdf"
        )


        backups[filename] = payloads



    return backups







# -------------------------------------------------
# Extract hierarchy safely
# -------------------------------------------------

def extract_hierarchy(record):

    """
    Supports:

    1. Final PostgreSQL payload format

    {
        hierarchy:{}
    }


    2. Raw semantic chunk format

    {
        metadata:{}
    }

    """


    if "hierarchy" in record:

        return record.get(
            "hierarchy",
            {}
        )



    if "metadata" in record:

        metadata = record.get(
            "metadata",
            {}
        )


        return {


            "chapter_title":
                metadata.get(
                    "chapter_title",
                    ""
                ),


            "section_title":
                metadata.get(
                    "section_title",
                    ""
                )

        }



    return {

        "chapter_title":"",
        "section_title":""

    }








# -------------------------------------------------
# Normalize heading text
# -------------------------------------------------

def normalize_heading(text):

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9&\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()








# -------------------------------------------------
# Section validation
# -------------------------------------------------

def check_section_coverage(payloads):


    found = {

        "abstract":
            False

    }


    found.update(
        {
            name:False
            for name in REQUIRED_SECTIONS
        }
    )



    matched_titles = {


        name:[]

        for name in REQUIRED_SECTIONS

    }




    # -----------------------------
    # Abstract check
    # -----------------------------

    found["abstract"] = any(

        record.get(
            "page_type"
        ) == "abstract"

        and

        record.get(
            "content",
            ""
        ).strip()


        for record in payloads

    )






    # -----------------------------
    # Content sections
    # -----------------------------

    for record in payloads:



        if record.get(
            "page_type"
        ) != "content":

            continue




        hierarchy = extract_hierarchy(
            record
        )



        chapter = normalize_heading(
            hierarchy.get(
                "chapter_title",
                ""
            )
        )


        section = normalize_heading(
            hierarchy.get(
                "section_title",
                ""
            )
        )



        haystack = (

            f"{chapter} {section}"

        ).strip()





        for name, pattern in REQUIRED_SECTIONS.items():



            if pattern.search(
                haystack
            ):



                found[name] = True



                title = (

                    hierarchy.get(
                        "chapter_title",
                        ""
                    )

                    or

                    hierarchy.get(
                        "section_title",
                        ""
                    )

                )



                if (

                    title

                    and

                    title not in matched_titles[name]

                ):


                    matched_titles[name].append(
                        title
                    )





    return found, matched_titles










# -------------------------------------------------
# Report
# -------------------------------------------------

def run_section_coverage_report():


    backups = load_payload_backups()



    filenames = sorted(
        backups.keys()
    )



    if not filenames:


        print(
            "No payload backups found. Run ingestion first."
        )


        return






    section_order = (

        ["abstract"]

        +

        list(
            REQUIRED_SECTIONS.keys()
        )

    )





    for filename in filenames:



        found, matched_titles = check_section_coverage(
            backups[filename]
        )



        print(
            f"\n{filename}"
        )


        print(
            "-" * len(filename)
        )



        for name in section_order:



            status = (

                "OK"

                if found[name]

                else

                "MISSING"

            )



            titles = matched_titles.get(
                name,
                []
            )



            title_note = (

                f" (matched: {', '.join(titles)})"

                if titles

                else ""

            )



            print(
                f"[{status:<7}] {name:<18}{title_note}"
            )






        missing = [


            name

            for name in section_order

            if not found[name]


        ]



        if missing:


            print(

                f"Missing sections: "
                f"{', '.join(missing)}"

            )


        else:


            print(
                "All thesis sections detected"
            )








if __name__ == "__main__":


    run_section_coverage_report()