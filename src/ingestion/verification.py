"""
Ingestion Verification & Similarity Diagnostics.

Runs after ingestion to verify PostgreSQL + pgvector storage.

Simplified report: for each project, shows only
Title | Domain | Score (self-match similarity)
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

    for json_path in sorted(PAYLOADS_DIR.glob("processed_*.json")):
        with open(json_path, "r", encoding="utf-8") as file:
            payloads = json.load(file)

        stem = json_path.stem.replace("processed_", "")
        backups[f"{stem}.pdf"] = payloads

    return backups


# -------------------------------------------------
# Project metrics (title + domain only)
# -------------------------------------------------

def project_level_metrics(filename, project_store):
    profile = project_store.get_project_profile(filename)

    if not profile:
        return None

    return {
        "filename": filename,
        "title": profile.get("project_title", "UNKNOWN"),
        "domain": profile.get("domain", "UNKNOWN"),
        "embedding_text": profile.get("embedding_text", ""),
    }


# -------------------------------------------------
# Self-match score
# -------------------------------------------------

def self_match_score(project_store, profile):
    """Returns a similarity score (0-1, higher = better match to itself)."""

    if not profile.get("embedding_text"):
        return None

    matches = project_store.query_similar_projects(
        profile["embedding_text"],
        top_k=1
    )

    if not matches:
        return None

    distance = matches[0].get("distance")

    if distance is None:
        return None

    # Convert cosine distance -> similarity score for readability
    return round(1 - distance, 4)


# -------------------------------------------------
# Reporting
# -------------------------------------------------

def run_verification():
    project_store = ProjectVectorStore()

    backups = load_payload_backups()
    filenames = sorted(backups.keys())

    if not filenames:
        print("No payload backups found.")
        return

    rows = []

    for filename in filenames:
        metrics = project_level_metrics(filename, project_store)

        if not metrics:
            rows.append((filename, "MISSING", "-", "-"))
            continue

        # need full profile again to get embedding_text for scoring
        profile = project_store.get_project_profile(filename)
        score = self_match_score(project_store, profile)

        rows.append((
            metrics["title"],
            metrics["domain"],
            score if score is not None else "N/A",
        ))

    title_w = max(len(str(r[0])) for r in rows) if rows else 20
    domain_w = max(len(str(r[1])) for r in rows) if rows else 10

    header = f"{'Title'.ljust(title_w)}  {'Domain'.ljust(domain_w)}  Score"
    print(header)
    print("-" * len(header))

    for title, domain, score in rows:
        print(f"{str(title).ljust(title_w)}  {str(domain).ljust(domain_w)}  {score}")


if __name__ == "__main__":
    run_verification()