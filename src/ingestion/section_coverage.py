"""
Thesis Section Coverage + Domain Classification Checker.

Validates whether ingestion produced correctly classified content
sections AND a meaningful domain/task classification before/after
storing into PostgreSQL + pgvector.

Section checks:

- Abstract
- Introduction
- Literature Review
- Methodology
- Results
- Discussion

Domain/task checks (new):

- Did the project get a domain/task at all, or fall back to the
  "General Computer Science & Engineering" / "General Analysis" defaults
  (meaning nothing in the ontology scored above zero for it)?
- Does the project have domain_scores/task_scores populated (i.e. was it
  ingested through the current pipeline, or is it a pre-upgrade row that
  still needs re-ingestion)?
- What are the primary and secondary domains/tasks, so a human reviewer
  can eyeball whether the classification actually looks right?


Works with PostgreSQL ingestion payloads:

document_chunks
    |
    DjangoIngestionTransformer
    |
    processed_*.json backup

and with:

project_profiles (joined to documents by filename)
    |
    domain / task / domain_scores / task_scores


Used for detecting:
- heading detection failures
- incorrect chapter mapping
- missing semantic sections
- weak/fallback domain classification
- projects not yet re-ingested through the multi-domain classifier
"""


import json
import re
from collections import Counter
import psycopg

from . import config
from .config import PAYLOADS_DIR
from .domain_classifier import DEFAULT_DOMAIN
from .task_classifier import DEFAULT_TASK


REQUIRED_SECTIONS = {

    "introduction":
        re.compile(
            r"\bintroduction\b|"
            r"\bbackground\b|"
            r"\boverview\b",
            re.IGNORECASE
        ),


    "literature_review":
        re.compile(
            r"literature\s+review|"
            r"related\s+work|"
            r"background\s+study|"
            r"state\s+of\s+the\s+art|"
            r"existing\s+(work|research)|"
            r"survey",
            re.IGNORECASE
        ),


    "methodology":
        re.compile(
            r"methodolog|"
            r"system\s+design|"
            r"implementation|"
            r"architecture|"
            r"proposed\s+system|"
            r"experimental\s+setup|"
            r"design\s+and\s+implementation",
            re.IGNORECASE
        ),


    "results":
        re.compile(
            r"\bresults?\b|"
            r"evaluation|"
            r"performance\s+analysis|"
            r"experimental\s+results|"
            r"results?\s*(and|&)\s*discussion|"
            r"testing|"
            r"validation",
            re.IGNORECASE
        ),


    "discussion":
        re.compile(
            r"\bdiscussion\b|"
            r"results?\s*(and|&)\s*discussion|"
            r"analysis|"
            r"interpretation",
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
# Load domain/task classification from PostgreSQL
# -------------------------------------------------

def load_domain_task_info():

    """
    Returns {filename: {domain, task, domain_scores, task_scores,
    project_title}} pulled straight from project_profiles, joined to
    documents by filename.

    Returns an empty dict (rather than raising) if the DB is unreachable,
    so this report still works as a pure filesystem check when run
    somewhere without DB access -- domain/task rows just get reported as
    "unavailable" per project in that case.
    """

    info = {}

    try:

        connection = psycopg.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            dbname=config.POSTGRES_DB,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
        )

    except Exception as error:

        print(
            f"[warning] Could not connect to PostgreSQL for domain/task "
            f"lookup ({error}). Domain/task checks will be skipped."
        )

        return info


    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT

                    d.filename,
                    pp.project_title,
                    pp.domain,
                    pp.task,
                    pp.domain_scores,
                    pp.task_scores

                FROM project_profiles pp

                JOIN documents d
                ON pp.document_id = d.id
                """
            )

            rows = cursor.fetchall()

    finally:

        connection.close()


    for filename, project_title, domain, task, domain_scores, task_scores in rows:

        info[filename] = {

            "project_title": project_title,

            "domain": domain,

            "task": task,

            "domain_scores": domain_scores or [],

            "task_scores": task_scores or [],

        }


    return info







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

    (
        record.get("page_type") == "abstract"
        or
        "abstract" in normalize_heading(
            extract_hierarchy(record).get("section_title", "")
        )
    )

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
# Domain / task validation
# -------------------------------------------------

def check_domain_classification(domain_info):

    """
    Evaluates a single project's domain/task entry (from
    load_domain_task_info) and returns a small report dict:

        {
            "available": bool,      # was there a DB row for this file at all
            "status": "OK" | "FALLBACK" | "NOT_REINGESTED" | "UNAVAILABLE",
            "domain": str,
            "task": str,
            "secondary_domains": [str, ...],
            "secondary_tasks": [str, ...],
        }

    "FALLBACK" means the ontology scored nothing above zero (domain/task
    landed on the generic default), which usually means the project's
    abstract/objectives text is too thin or off-vocabulary for the current
    keyword ontology -- worth a human look, not necessarily a bug.

    "NOT_REINGESTED" means the row predates the domain_scores/task_scores
    columns (they're NULL/empty) -- the project needs to go through the
    pipeline again to get a real multi-domain classification.
    """

    if domain_info is None:

        return {
            "available": False,
            "status": "UNAVAILABLE",
            "domain": None,
            "task": None,
            "secondary_domains": [],
            "secondary_tasks": [],
        }


    domain = domain_info.get("domain")
    task = domain_info.get("task")
    domain_scores = domain_info.get("domain_scores") or []
    task_scores = domain_info.get("task_scores") or []


    if not domain_scores and not task_scores:

        status = "NOT_REINGESTED"


    elif domain == DEFAULT_DOMAIN or task == DEFAULT_TASK:

        status = "FALLBACK"


    else:

        status = "OK"


    secondary_domains = [
        entry.get("domain")
        for entry in domain_scores[1:]
        if entry.get("domain")
    ]

    secondary_tasks = [
        entry.get("task")
        for entry in task_scores[1:]
        if entry.get("task")
    ]


    return {

        "available": True,

        "status": status,

        "domain": domain,

        "task": task,

        "secondary_domains": secondary_domains,

        "secondary_tasks": secondary_tasks,

    }








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



    domain_task_info = load_domain_task_info()



    section_order = (

        ["abstract"]

        +

        list(
            REQUIRED_SECTIONS.keys()
        )

    )


    summary_missing_sections = 0

    summary_fallback_domain = 0

    summary_not_reingested = 0

    summary_unavailable_domain = 0
    missing_counter = Counter()


    for filename in filenames:



        found, matched_titles = check_section_coverage(
            backups[filename]
        )


        domain_report = check_domain_classification(
            domain_task_info.get(filename)
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
                f"Missing sections: {', '.join(missing)}"
            )

            for section in missing:
                missing_counter[section] += 1

            summary_missing_sections += 1

        else:


            print(
                "All thesis sections detected"
            )



        # -----------------------------
        # Domain / task classification
        # -----------------------------

        print()

        if domain_report["status"] == "UNAVAILABLE":

            print(
                "[DOMAIN ] UNAVAILABLE  "
                "(no project_profiles row found for this filename -- "
                "has it been ingested?)"
            )

            summary_unavailable_domain += 1


        elif domain_report["status"] == "NOT_REINGESTED":

            print(
                "[DOMAIN ] NOT RE-INGESTED  "
                "(domain_scores/task_scores are empty -- this row predates "
                "the multi-domain classifier; re-run ingestion on this PDF)"
            )

            print(
                f"           current domain='{domain_report['domain']}', "
                f"task='{domain_report['task']}' (from the old single-value "
                f"columns only)"
            )

            summary_not_reingested += 1


        else:

            status_label = (
                "OK"
                if domain_report["status"] == "OK"
                else "FALLBACK"
            )

            print(
                f"[DOMAIN ] {status_label:<7} domain='{domain_report['domain']}', "
                f"task='{domain_report['task']}'"
            )

            if domain_report["secondary_domains"]:

                print(
                    "           secondary domains: "
                    + ", ".join(domain_report["secondary_domains"])
                )

            if domain_report["secondary_tasks"]:

                print(
                    "           secondary tasks: "
                    + ", ".join(domain_report["secondary_tasks"])
                )

            if domain_report["status"] == "FALLBACK":

                print(
                    "           note: nothing in the ontology scored above "
                    "zero for this project -- its abstract/objectives text "
                    "may be too thin, or off-vocabulary for the current "
                    "domain/task keyword lists. Worth a human look."
                )

                summary_fallback_domain += 1



    # -----------------------------
    # Batch summary
    # -----------------------------

    print(
        "\n" + "=" * 40
    )

    print(
        "SUMMARY"
    )

    print(
        "=" * 40
    )

    print(
        f"Projects checked: {len(filenames)}"
    )

    print(
        f"Projects with missing thesis section(s): {summary_missing_sections}"
    )

    print(
        f"Projects with fallback/unclassified domain: {summary_fallback_domain}"
    )

    print(
        f"Projects not yet re-ingested (no domain_scores): {summary_not_reingested}"
    )

    print(
        f"Projects with no project_profiles row at all: {summary_unavailable_domain}"
    )

    print()

    print(
        "Missing section frequency:"
    )

    for section, count in missing_counter.most_common():

        print(
            f"{section}: {count}"
        )


if __name__ == "__main__":

    run_section_coverage_report()