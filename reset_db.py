#!/usr/bin/env python

"""
Completely reset the PostgreSQL + pgvector ingestion pipeline.

Deletes:

DATABASE:
    - document_chunks table data
    - project_profiles table data

FILESYSTEM:
    - ingestion registry
    - extracted JSON payload backups
    - log file


Does NOT delete:

    - docs/
    - source code
    - PostgreSQL database itself
    - table structure
"""


import sys
import shutil


from src.ingestion.config import (
    REGISTRY_PATH,
    PAYLOADS_DIR,
    LOG_FILE,
    ensure_directories,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
)


import psycopg



def clear_vector_tables():

    try:

        connection = psycopg.connect(

            host=POSTGRES_HOST,

            port=POSTGRES_PORT,

            dbname=POSTGRES_DB,

            user=POSTGRES_USER,

            password=POSTGRES_PASSWORD

        )


        with connection.cursor() as cursor:


            cursor.execute(
                """
                TRUNCATE TABLE document_chunks
                RESTART IDENTITY CASCADE;
                """
            )


            cursor.execute(
                """
                TRUNCATE TABLE project_profiles
                RESTART IDENTITY CASCADE;
                """
            )


        connection.commit()

        connection.close()


        print(
            "[OK] Cleared PostgreSQL vector tables"
        )


    except Exception as e:

        print(
            f"[ERROR] PostgreSQL reset failed: {e}"
        )



def reset_registry():

    if REGISTRY_PATH.exists():

        REGISTRY_PATH.unlink()

        print(
            f"[OK] Deleted {REGISTRY_PATH}"
        )

    else:

        print(
            "[SKIP] Registry not found"
        )



def reset_payloads():

    deleted = 0


    if PAYLOADS_DIR.exists():

        for file in PAYLOADS_DIR.glob("*.json"):

            file.unlink()

            deleted += 1


    print(
        f"[OK] Deleted {deleted} payload(s)"
    )



def reset_logs():

    try:

        LOG_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        with open(
            LOG_FILE,
            "w",
            encoding="utf-8"
        ):

            pass


        print(
            f"[OK] Cleared {LOG_FILE}"
        )


    except Exception as e:


        print(
            f"[SKIP] Could not clear log: {e}"
        )



def main():


    skip = (
        "--yes" in sys.argv
        or
        "-y" in sys.argv
    )


    if not skip:

        answer = input(

            "This will erase all indexed PostgreSQL vector data. Type 'yes' to continue: "

        ).strip().lower()


        if answer != "yes":

            print(
                "Cancelled."
            )

            return



    print()



    clear_vector_tables()


    reset_registry()


    reset_payloads()


    reset_logs()



    ensure_directories()



    print(
        "\nReset complete."
    )

    print(
        "Run:"
    )

    print(
        "python run_ingestion.py"
    )



if __name__ == "__main__":

    main()