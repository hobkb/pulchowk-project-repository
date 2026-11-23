"""
Locating the real PDF page for a heading typed by hand during review.

Built on the same synthetic-PDF harness as the extraction pipeline tests --
no confidential report is read or referenced. The one case that matters
most here is the ToC trap: "System Design ......... 34" in the table of
contents must never be mistaken for the real chapter start.
"""

import fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import User
from ingestion.models import IngestionJob
from ingestion.pipeline.utils.heading_locator import locate_heading_page
from ingestion.test_pipeline_synthetic import HEADING_FONT, SUBHEADING_FONT, _add_block, build_pdf


class LocateHeadingPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="locate@example.com", password="secret123")

    def _job(self, pdf_bytes):
        return IngestionJob.objects.create(
            file=SimpleUploadedFile("report.pdf", pdf_bytes, content_type="application/pdf"),
            original_filename="report.pdf",
            uploaded_by=self.user,
        )

    def _report(self):
        def cover(page):
            _add_block(page, (60, 80, 535, 130), "A REPORT ON SOMETHING",
                       {"fontsize": 18, "fontname": "hebo"})

        def toc(page):
            _add_block(page, (60, 60, 535, 90), "Table of Contents", HEADING_FONT)
            _add_block(page, (60, 120, 535, 260),
                       "1 Introduction ............ 3\n"
                       "2 System Design ............ 5\n"
                       "3 Conclusion ............ 9")

        def introduction(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 120, 535, 400),
                       "This report describes a project. " * 20)

        def blank(page):
            _add_block(page, (60, 60, 535, 90), "", HEADING_FONT)

        def system_design(page):
            _add_block(page, (60, 60, 535, 90), "2 System Design", HEADING_FONT)
            _add_block(page, (60, 120, 535, 400),
                       "The overall architecture consists of several components. " * 20)

        def conclusion(page):
            _add_block(page, (60, 60, 535, 90), "3 Conclusion", HEADING_FONT)
            _add_block(page, (60, 120, 535, 400), "This report concludes here. " * 20)

        return build_pdf([cover, toc, introduction, blank, system_design, conclusion])

    def test_finds_the_real_chapter_page_not_the_toc_entry(self):
        job = self._job(self._report())
        page = locate_heading_page(job, "System Design")
        self.assertEqual(page, 5)

    def test_is_case_and_numbering_insensitive(self):
        job = self._job(self._report())
        self.assertEqual(locate_heading_page(job, "system design"), 5)
        self.assertEqual(locate_heading_page(job, "2. System Design"), 5)

    def test_a_heading_that_is_not_in_the_document_returns_none(self):
        job = self._job(self._report())
        self.assertIsNone(locate_heading_page(job, "Quantum Cryptography Analysis"))

    def test_a_stray_mention_in_body_text_does_not_count_as_a_match(self):
        """"system design" appearing mid-paragraph on an unrelated page
        must not outrank the real heading -- it is not bold/large enough
        to be treated as a heading candidate at all."""
        def cover(page):
            _add_block(page, (60, 80, 535, 130), "COVER", HEADING_FONT)

        def mentions_it(page):
            _add_block(page, (60, 60, 535, 90), "1 Discussion", HEADING_FONT)
            _add_block(page, (60, 120, 535, 400),
                       "Our system design choices are discussed further below. " * 15)

        def real_heading(page):
            _add_block(page, (60, 60, 535, 90), "2 System Design", HEADING_FONT)
            _add_block(page, (60, 120, 535, 400), "Architecture details follow. " * 15)

        job = self._job(build_pdf([cover, mentions_it, real_heading]))
        self.assertEqual(locate_heading_page(job, "System Design"), 3)

    def test_a_numbered_subsection_heading_is_found_too(self):
        def cover(page):
            _add_block(page, (60, 80, 535, 130), "COVER", HEADING_FONT)

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "1 Methodology", HEADING_FONT)
            _add_block(page, (60, 110, 535, 140), "1.1 Data Collection", SUBHEADING_FONT)
            _add_block(page, (60, 160, 535, 400), "Details of the survey. " * 15)

        job = self._job(build_pdf([cover, chapter]))
        self.assertEqual(locate_heading_page(job, "Data Collection"), 2)

    def test_an_empty_query_finds_nothing(self):
        job = self._job(self._report())
        self.assertIsNone(locate_heading_page(job, ""))
        self.assertIsNone(locate_heading_page(job, "   "))
