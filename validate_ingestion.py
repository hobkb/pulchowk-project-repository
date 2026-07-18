#!/usr/bin/env python

"""
Post-ingestion integrity checker for the Pulchowk Project Repository.

Runs read-only checks against the live database to catch the kinds of
problems that don't throw an exception during ingestion but silently
produce bad data:

  PROJECT LEVEL (project_profiles):
    - every document has exactly one project profile (1:1 with documents)
    - domain / task are never NULL or empty
    - domain_scores / task_scores are populated, and their top entry
      actually agrees with the `domain` / `task` columns (catches drift if
      someone edits one without the other)
    - keywords is never an empty array
    - embedding_text isn't suspiciously short (a sign upstream extraction
      fell back to "Not found" for everything)
    - embedding is present and has the expected dimensionality

  CONTENT LEVEL (document_chunks):
    - every chunk has non-empty content and a non-null embedding
    - embedding dimensionality matches config.EMBEDDING_DIM
    - no chunk_index gaps/duplicates per document (catches partial/failed
      re-ingestion runs)
    - content-page chunks (page_type == 'content') have a non-empty
      section_title, since AcademicSemanticChunker always sets one

Usage:

    python validate_ingestion.py
    python validate_ingestion.py --verbose

Exit code is 0 if no problems were found, 1 otherwise -- safe to use in a
CI step or a cron job after run_ingestion.py.
"""

import sys
import argparse

import psycopg

from src.ingestion import config


EXPECTED_EMBEDDING_DIM = 384


def get_embedding_dimension(embedding):
    """
    Get pgvector embedding dimension safely.

    psycopg may return pgvector values as a string representation
    rather than a Python list. Counting len(embedding) directly would
    count characters instead of vector dimensions.
    """
    if embedding is None:
        return None

    if isinstance(embedding, list):
        return len(embedding)

    return len(str(embedding).strip("[]").split(","))


def connect():
    return psycopg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )


def check_document_project_parity(cur, problems, verbose):
    cur.execute(
        """
        SELECT d.id, d.filename
        FROM documents d
        LEFT JOIN project_profiles pp ON pp.document_id = d.id
        WHERE pp.id IS NULL
        """
    )
    missing = cur.fetchall()

    if missing:
        problems.append(
            f"{len(missing)} document(s) have NO project profile: "
            + ", ".join(f"{fn} (id={did})" for did, fn in missing[:10])
            + (" ..." if len(missing) > 10 else "")
        )
    elif verbose:
        print("  [ok] every document has a project profile")

    cur.execute(
        """
        SELECT document_id, COUNT(*) c
        FROM project_profiles
        GROUP BY document_id
        HAVING COUNT(*) > 1
        """
    )

    dupes = cur.fetchall()

    if dupes:
        problems.append(
            f"{len(dupes)} document(s) have MORE THAN ONE project profile "
            f"(unique_project_profile constraint should prevent this -- "
            f"check for a bypassed constraint or raw SQL insert): {dupes}"
        )


def check_domain_task_integrity(cur, problems, verbose):

    cur.execute(
        """
        SELECT id, project_title, domain, task, domain_scores, task_scores,
               keywords, embedding_text, embedding
        FROM project_profiles
        """
    )

    rows = cur.fetchall()

    empty_domain = []
    empty_task = []
    missing_domain_scores = []
    missing_task_scores = []
    domain_drift = []
    task_drift = []
    empty_keywords = []
    short_embedding_text = []
    null_embedding = []
    wrong_dim = []

    for (
        pid, title, domain, task, domain_scores, task_scores,
        keywords, embedding_text, embedding
    ) in rows:

        if not domain or not domain.strip():
            empty_domain.append((pid, title))

        if not task or not task.strip():
            empty_task.append((pid, title))

        if not domain_scores:
            missing_domain_scores.append((pid, title))
        elif domain_scores[0].get("domain") != domain:
            domain_drift.append(
                (pid, title, domain, domain_scores[0].get("domain"))
            )

        if not task_scores:
            missing_task_scores.append((pid, title))
        elif task_scores[0].get("task") != task:
            task_drift.append(
                (pid, title, task, task_scores[0].get("task"))
            )

        if not keywords:
            empty_keywords.append((pid, title))

        if not embedding_text or len(embedding_text.split()) < 15:
            short_embedding_text.append((pid, title))

        if embedding is None:
            null_embedding.append((pid, title))
        else:
            dim = get_embedding_dimension(embedding)

            if dim != EXPECTED_EMBEDDING_DIM:
                wrong_dim.append((pid, title, dim))

    def report(label, items, fmt=lambda x: f"id={x[0]} '{x[1]}'"):

        if items:
            problems.append(
                f"{len(items)} project profile(s) {label}: "
                + "; ".join(fmt(x) for x in items[:10])
                + (" ..." if len(items) > 10 else "")
            )
        elif verbose:
            print(f"  [ok] no profiles {label}")

    report("have an empty domain", empty_domain)
    report("have an empty task", empty_task)
    report("are missing domain_scores", missing_domain_scores)
    report("are missing task_scores", missing_task_scores)

    report(
        "have domain_scores[0] disagreeing with the domain column",
        domain_drift,
        fmt=lambda x:
            f"id={x[0]} '{x[1]}': domain='{x[2]}' but top score='{x[3]}'",
    )

    report(
        "have task_scores[0] disagreeing with the task column",
        task_drift,
        fmt=lambda x:
            f"id={x[0]} '{x[1]}': task='{x[2]}' but top score='{x[3]}'",
    )

    report("have empty keywords", empty_keywords)

    report(
        "have suspiciously short embedding_text (<15 words -- likely a "
        "fallback-to-nothing extraction)",
        short_embedding_text,
    )

    report("have a NULL embedding", null_embedding)

    report(
        "have the wrong embedding dimensionality",
        wrong_dim,
        fmt=lambda x: f"id={x[0]} '{x[1]}': dim={x[2]}",
    )


def check_chunk_integrity(cur, problems, verbose):

    cur.execute(
        """
        SELECT id, document_id, chunk_index, content, embedding,
               page_type, section_title
        FROM document_chunks
        """
    )

    rows = cur.fetchall()

    empty_content = []
    null_embedding = []
    wrong_dim = []
    missing_section_title = []

    per_doc_indices = {}

    for cid, document_id, chunk_index, content, embedding, page_type, section_title in rows:

        if not content or not content.strip():
            empty_content.append((cid, document_id))

        if embedding is None:
            null_embedding.append((cid, document_id))

        else:
            dim = get_embedding_dimension(embedding)

            if dim != EXPECTED_EMBEDDING_DIM:
                wrong_dim.append((cid, document_id, dim))

        if page_type == "content" and not (section_title or "").strip():
            missing_section_title.append((cid, document_id))

        per_doc_indices.setdefault(document_id, []).append(chunk_index)

    def report(label, items, fmt=lambda x: f"chunk_id={x[0]} document_id={x[1]}"):

        if items:
            problems.append(
                f"{len(items)} chunk(s) {label}: "
                + "; ".join(fmt(x) for x in items[:10])
                + (" ..." if len(items) > 10 else "")
            )

        elif verbose:
            print(f"  [ok] no chunks {label}")

    report("have empty content", empty_content)
    report("have a NULL embedding", null_embedding)

    report(
        "have the wrong embedding dimensionality",
        wrong_dim,
        fmt=lambda x:
            f"chunk_id={x[0]} document_id={x[1]} dim={x[2]}",
    )

    report(
        "are content pages with no section_title "
        "(AcademicSemanticChunker should always set one)",
        missing_section_title,
    )

    gap_docs = []
    dup_docs = []

    for document_id, indices in per_doc_indices.items():

        sorted_idx = sorted(indices)
        expected = list(range(len(sorted_idx)))

        if len(set(sorted_idx)) != len(sorted_idx):
            dup_docs.append(document_id)

        elif sorted_idx != expected:
            gap_docs.append(document_id)

    if dup_docs:
        problems.append(
            f"{len(dup_docs)} document(s) have DUPLICATE chunk_index values "
            f"(unique_document_chunk constraint should prevent this): {dup_docs[:10]}"
        )

    if gap_docs:
        problems.append(
            f"{len(gap_docs)} document(s) have GAPS in chunk_index sequence "
            f"(possible partial re-ingestion failure): {gap_docs[:10]}"
        )

    elif verbose:
        print("  [ok] no chunk_index gaps or duplicates")


def check_indexes_exist(cur, problems, verbose):

    cur.execute(
        """
        SELECT indexname FROM pg_indexes
        WHERE tablename IN ('document_chunks', 'project_profiles')
        """
    )

    existing = {row[0] for row in cur.fetchall()}

    expected = {
        "document_chunks_embedding_idx",
        "project_profiles_embedding_idx",
        "project_profiles_domain_idx",
        "project_profiles_task_idx",
        "project_profiles_keywords_idx",
        "project_profiles_domain_scores_idx",
        "project_profiles_task_scores_idx",
    }

    missing = expected - existing

    if missing:
        problems.append(
            f"Missing expected index(es): {sorted(missing)} -- "
            f"queries relying on them will silently fall back to a "
            f"sequential scan instead of failing loudly, so this is easy "
            f"to miss. Re-run schema.sql / migration_add_domain_scores.sql."
        )

    elif verbose:
        print("  [ok] all expected indexes are present")


def main():

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="also print passing checks"
    )

    args = parser.parse_args()

    problems = []

    with connect() as conn:

        with conn.cursor() as cur:

            print("Checking documents <-> project_profiles parity...")
            check_document_project_parity(
                cur,
                problems,
                args.verbose
            )

            print("Checking domain/task integrity on project_profiles...")
            check_domain_task_integrity(
                cur,
                problems,
                args.verbose
            )

            print("Checking document_chunks integrity...")
            check_chunk_integrity(
                cur,
                problems,
                args.verbose
            )

            print("Checking expected indexes exist...")
            check_indexes_exist(
                cur,
                problems,
                args.verbose
            )

    print()

    if not problems:
        print("All checks passed. No inconsistencies found.")
        sys.exit(0)

    print(f"Found {len(problems)} issue(s):\n")

    for i, problem in enumerate(problems, 1):
        print(f"{i}. {problem}\n")

    sys.exit(1)


if __name__ == "__main__":
    main()