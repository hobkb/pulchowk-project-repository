#!/usr/bin/env python
"""
Entry point for the ingestion pipeline.

Usage:
    python run_ingestion.py
    python run_ingestion.py /path/to/other/pdf/folder

For Django integration, don't call this script directly -- import and call
the pipeline function instead, e.g. from a management command:

    from src.ingestion.pipeline import run_full_pipeline
    run_full_pipeline()
"""

import sys
import warnings

warnings.filterwarnings("ignore")

from src.ingestion.pipeline import run_full_pipeline

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else None
    run_full_pipeline(folder)
