"""
Ingestion Verification & Similarity Diagnostics.

Runs after ingestion to verify PostgreSQL + pgvector storage.

Checks:

CONTENT LEVEL:
- payload backup exists
- chunk_index continuity
- excluded pages removed
- empty chunks detection
- stored chunk count matches JSON backup


PROJECT LEVEL:
- project profile exists
- metadata completeness
- embedding text quality
- keyword extraction quality


SIMILARITY:
- project self-match test
- pairwise project similarity


Does not re-run extraction or ingestion.
"""


import json


from .config import PAYLOADS_DIR

from .postgres_vector_store import PostgreSQLVectorStore

from .project_vector_store import ProjectVectorStore

from .payload_transform import DjangoIngestionTransformer





# -------------------------------------------------
# Loading payload backups
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
        ) as file:

            payloads = json.load(file)



        stem = json_path.stem.replace(
            "processed_",
            ""
        )


        backups[
            f"{stem}.pdf"
        ] = payloads


    return backups





# -------------------------------------------------
# Count stored chunks
# -------------------------------------------------

def count_document_chunks(
    vector_store,
    filename
):

    with vector_store.connection.cursor() as cursor:

        cursor.execute(

            """
            SELECT COUNT(*)

            FROM document_chunks dc

            JOIN documents d

            ON dc.document_id = d.id

            WHERE d.filename = %s

            """,

            (
                filename,
            )

        )

        return cursor.fetchone()[0]





# -------------------------------------------------
# Content checks
# -------------------------------------------------

def check_content_level(
    filename,
    payloads,
    vector_store
):

    issues = []


    if not payloads:

        issues.append(
            "payload backup empty"
        )

        return issues



    # chunk index continuity

    indices = [

        record["chunk_index"]

        for record in payloads

    ]


    if indices != list(
        range(len(payloads))
    ):

        issues.append(
            "chunk_index sequence invalid"
        )




    # excluded pages check

    for record in payloads:


        if record.get(
            "page_type"
        ) in DjangoIngestionTransformer.EXCLUDED_PAGE_TYPES:


            issues.append(
                f"excluded page leaked: {record.get('page_type')}"
            )





    # token validation

    invalid_tokens = [

        record["chunk_index"]

        for record in payloads

        if record.get(
            "estimated_tokens",
            0
        ) <= 0

    ]


    if invalid_tokens:

        issues.append(
            f"invalid token count: {invalid_tokens[:5]}"
        )





    # empty content validation

    empty_chunks = [

        record["chunk_index"]

        for record in payloads

        if not record.get(
            "content",
            ""
        ).strip()

    ]


    if empty_chunks:

        issues.append(
            f"empty content chunks: {empty_chunks[:5]}"
        )





    # title validation

    title = (

        payloads[0]
        .get(
            "hierarchy",
            {}
        )
        .get(
            "project_title",
            "UNKNOWN PROJECT TITLE"
        )

    )


    if title == "UNKNOWN PROJECT TITLE":

        issues.append(
            "missing project title"
        )





    # database count verification

    stored_count = count_document_chunks(
        vector_store,
        filename
    )


    if stored_count != len(payloads):

        issues.append(

            f"PostgreSQL has {stored_count} chunks, "
            f"backup has {len(payloads)}"

        )


    return issues





# -------------------------------------------------
# Project metrics
# -------------------------------------------------

def project_level_metrics(
    filename,
    project_store
):


    profile = project_store.get_project_profile(
        filename
    )


    if not profile:

        return None




    keywords = profile.get(
        "keywords",
        []
    )


    if isinstance(
        keywords,
        str
    ):

        keywords = [

            keyword.strip()

            for keyword in keywords.split(",")

            if keyword.strip()

        ]



    embedding_text = profile.get(
        "embedding_text",
        ""
    )


    words = len(
        embedding_text.split()
    )


    estimated_tokens = int(
        words * 1.33
    )



    return {


        "filename": filename,


        "title":
            profile.get(
                "project_title"
            ),



        "title_ok":

            profile.get(
                "project_title"
            )
            not in
            [
                "",
                "UNKNOWN",
                None
            ],



        "domain":
            profile.get(
                "domain"
            ),



        "abstract_found":

            bool(
                profile.get(
                    "abstract"
                )
            ),



        "objectives_found":

            bool(
                profile.get(
                    "objectives"
                )
            ),



        "keyword_count":

            len(
                keywords
            ),



        "embedding_text_word_count":

            words,



        "estimated_tokens":

            estimated_tokens,



        "likely_truncated":

            estimated_tokens > 256

    }





# -------------------------------------------------
# Similarity tests
# -------------------------------------------------

def self_match_test(
    project_store,
    filenames
):


    results = []


    for filename in filenames:


        profile = project_store.get_project_profile(
            filename
        )


        if not profile:

            results.append({

                "filename": filename,

                "status": "MISSING",

                "distance": None

            })

            continue





        matches = project_store.query_similar_projects(

            profile["embedding_text"],

            top_k=1

        )



        if not matches:

            results.append({

                "filename": filename,

                "status": "FAIL",

                "distance": 1.0

            })

            continue




        top = matches[0]



        matched_title = (

            top
            .get(
                "metadata",
                {}
            )
            .get(
                "project_title"
            )

        )



        status = (

            "PASS"

            if matched_title == profile["project_title"]

            else

            "FAIL"

        )



        results.append({

            "filename": filename,

            "status": status,

            "distance":
                round(
                    top["distance"],
                    4
                )

        })


    return results





def pairwise_similarity_matrix(
    project_store,
    filenames
):


    matrix = {}



    for filename in filenames:


        profile = project_store.get_project_profile(
            filename
        )


        if not profile:

            continue




        matches = project_store.query_similar_projects(

            profile["embedding_text"],

            top_k=len(filenames)

        )



        row = {}



        for item in matches:


            title = (

                item
                .get(
                    "metadata",
                    {}
                )
                .get(
                    "project_title"
                )

            )


            row[title] = round(

                item["distance"],

                4

            )



        matrix[
            filename
        ] = row



    return matrix





# -------------------------------------------------
# Reporting
# -------------------------------------------------

def _print_header(title):

    print()

    print(title)

    print(
        "-" * len(title)
    )





def run_verification():


    content_store = PostgreSQLVectorStore()


    project_store = ProjectVectorStore()



    backups = load_payload_backups()


    filenames = sorted(
        backups.keys()
    )



    if not filenames:

        print(
            "No payload backups found."
        )

        return





    _print_header(
        "CONTENT LEVEL CHECKS"
    )


    clean = 0



    for filename in filenames:


        issues = check_content_level(

            filename,

            backups[filename],

            content_store

        )



        if issues:


            print(
                "[FAIL]",
                filename
            )


            for issue in issues:

                print(
                    " -",
                    issue
                )


        else:


            print(
                "[OK]",
                filename
            )


            clean += 1





    print(

        f"{clean}/{len(filenames)} documents clean"

    )





    _print_header(
        "PROJECT LEVEL"
    )



    for filename in filenames:


        metrics = project_level_metrics(

            filename,

            project_store

        )


        print(
            filename,
            metrics
        )





    _print_header(
        "SELF MATCH TEST"
    )


    for result in self_match_test(

        project_store,

        filenames

    ):

        print(
            result
        )





    _print_header(
        "PAIRWISE PROJECT SIMILARITY"
    )



    print(

        pairwise_similarity_matrix(

            project_store,

            filenames

        )

    )






if __name__ == "__main__":

    run_verification()