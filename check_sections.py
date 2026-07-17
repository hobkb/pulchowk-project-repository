#!/usr/bin/env python
"""
Checks whether content-level chunking captured every standard thesis
section (Abstract, Introduction, Literature Review, Methodology, Results,
Discussion) for each ingested document.

Usage:
    python check_sections.py
"""

import warnings

warnings.filterwarnings("ignore")

from src.ingestion.section_coverage import run_section_coverage_report

if __name__ == "__main__":
    run_section_coverage_report()