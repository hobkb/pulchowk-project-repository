#!/usr/bin/env python

"""
Entry point for the PDF ingestion pipeline.

Pipeline flow:

PDF
 |
 +--> Layout extraction
 |
 +--> Line reconstruction
 |
 +--> Page classification
 |
 +--> Academic semantic chunking
 |
 +--> Content-level payload generation
 |        |
 |        +--> PostgreSQL + pgvector
 |             document_chunks table
 |
 +--> Project profile generation
          |
          +--> PostgreSQL + pgvector
               project_profiles table


Usage:

    python run_ingestion.py

    python run_ingestion.py /path/to/pdf/folder


For Django integration, do not call this script directly.

Import the pipeline function:

    from src.ingestion.pipeline import run_full_pipeline

    run_full_pipeline()
"""


import sys
import warnings


warnings.filterwarnings(
    "ignore"
)


from src.ingestion.pipeline import run_full_pipeline



if __name__ == "__main__":


    folder = (
        sys.argv[1]
        if len(sys.argv) > 1
        else None
    )


    run_full_pipeline(
        folder
    )