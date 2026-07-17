#!/usr/bin/env python

"""
Verification entry point for the PostgreSQL + pgvector ingestion system.

Runs after ingestion to validate:

CONTENT-LEVEL STORAGE:
    - document chunk payload generation
    - chunk ordering and metadata
    - document_chunks table indexing
    - content embedding storage

PROJECT-LEVEL STORAGE:
    - project profile generation
    - project_profiles table indexing
    - metadata completeness
    - project embedding storage

SIMILARITY DIAGNOSTICS:
    - project self-match verification
    - pairwise project similarity analysis


Usage:

    python verify_ingestion.py


The verification module only reads existing data.
It does not extract PDFs or modify indexes.
"""


import warnings


warnings.filterwarnings(
    "ignore"
)


from src.ingestion.verification import run_verification



if __name__ == "__main__":


    run_verification()