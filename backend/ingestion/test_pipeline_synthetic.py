"""
End-to-end ingestion pipeline tests driven by synthetic, self-authored PDFs.

Unlike ingestion/tests.py (which mostly feeds hand-built line dicts straight
into MetadataSectionsStep / DocumentPageClassifier), these tests exercise the
*real* PDF -> layout extraction -> line reconstruction -> page classification
-> metadata extraction path, using PDFs built in-process with PyMuPDF. No
confidential project reports are read, referenced, or required.
"""

import io

import fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import User
from ingestion.models import IngestionJob
from ingestion.pipeline.runner import PipelineRunner
from ingestion.pipeline.steps.pdf_extraction import PDFExtractionStep
from ingestion.pipeline.steps.line_reconstruction import LineReconstructionStep
from ingestion.pipeline.steps.page_classification import PageClassificationStep
from ingestion.pipeline.steps.metadata_front_matter import MetadataFrontMatterStep
from ingestion.pipeline.steps.metadata_people import MetadataPeopleStep
from ingestion.pipeline.steps.metadata_sections import MetadataSectionsStep


HEADING_FONT = {"fontsize": 16, "fontname": "hebo"}
SUBHEADING_FONT = {"fontsize": 13, "fontname": "hebo"}
BODY_FONT = {"fontsize": 11, "fontname": "helv"}


def _add_block(page, rect, text, font=BODY_FONT):
    page.insert_textbox(fitz.Rect(*rect), text, **font)


def build_pdf(page_builders):
    """page_builders: list of callables(page) that draw one page's content."""
    doc = fitz.open()
    for build in page_builders:
        page = doc.new_page(width=595, height=842)  # A4
        build(page)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    buf.seek(0)
    return buf.read()


def run_extraction_stages(job):
    """Runs the real extraction stages (everything before publish) and
    returns the accumulated context, mirroring PipelineRunner.execute
    without touching job.status bookkeeping."""
    context = {"start_time": 0, "stop_pipeline": False}
    for step_cls in [
        PDFExtractionStep,
        LineReconstructionStep,
        PageClassificationStep,
        MetadataFrontMatterStep,
        MetadataPeopleStep,
        MetadataSectionsStep,
    ]:
        context = step_cls().run(job, context)
    return context


class SyntheticReportPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="ingest@example.com", password="secret123")

    def _make_job(self, pdf_bytes, filename="synthetic.pdf"):
        return IngestionJob.objects.create(
            file=SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf"),
            original_filename=filename,
            uploaded_by=self.user,
        )

    def test_full_report_extraction_end_to_end(self):
        """A realistic single-column report: cover, approval, abstract, TOC,
        a multi-page Introduction whose numbered subsection is folded into
        it, References and Appendix kept out of project_sections."""

        def cover(page):
            _add_block(page, (60, 80, 535, 130), "AUTOMATED IRRIGATION SCHEDULING SYSTEM",
                       {"fontsize": 18, "fontname": "hebo"})
            _add_block(page, (60, 200, 535, 260),
                       "Aarav Shrestha (080BCT022)\nNischal Karki (079BCT047)")
            _add_block(page, (60, 400, 535, 460),
                       "Department of Computer Engineering\nPulchowk Campus\n2081")

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 200), "Supervisor")
            _add_block(page, (60, 210, 535, 260), "Dr. Ramesh Sharma\nProfessor")

        def abstract(page):
            _add_block(page, (60, 60, 535, 90), "ABSTRACT", HEADING_FONT)
            _add_block(page, (60, 120, 535, 220),
                       "This project proposes an automated irrigation scheduling system "
                       "that reduces water wastage on campus farmland.")
            _add_block(page, (60, 240, 535, 280),
                       "Keywords: irrigation, scheduling, sensors, automation")

        def toc(page):
            _add_block(page, (60, 60, 535, 90), "Table of Contents", HEADING_FONT)
            _add_block(page, (60, 120, 535, 260),
                       "1 Introduction ............ 1\n"
                       "2 Literature Review ............ 3\n"
                       "3 Methodology ............ 5\n"
                       "References ............ 8")

        def intro_page1(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 140), "1.1 Background", SUBHEADING_FONT)
            _add_block(page, (60, 150, 535, 260),
                       "Manual irrigation on campus farmland wastes significant "
                       "amounts of water every growing season.")

        def intro_page2(page):
            _add_block(page, (60, 60, 535, 160),
                       "This continuation paragraph belongs to the Introduction "
                       "and spans onto a second page of the same section.")
            _add_block(page, (60, 200, 535, 230), "2 Literature Review", HEADING_FONT)
            _add_block(page, (60, 250, 535, 320),
                       "Prior automated systems relied on fixed schedules rather "
                       "than soil-moisture feedback.")

        def references_and_appendix(page):
            _add_block(page, (60, 60, 535, 90), "References", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160),
                       "[1] Example, A. (2020). Smart irrigation. Journal of Water.")
            _add_block(page, (60, 200, 535, 230), "Appendix A: Sensor Datasheet", HEADING_FONT)
            _add_block(page, (60, 250, 535, 300), "Sensor calibration values are listed here.")

        pdf_bytes = build_pdf([
            cover, approval, abstract, toc, intro_page1, intro_page2, references_and_appendix,
        ])
        job = self._make_job(pdf_bytes)
        context = run_extraction_stages(job)
        draft = context["draft_metadata"]

        # --- front matter ---
        self.assertIn("irrigation", (draft["project_fields"]["title"] or "").lower())
        self.assertIn("irrigation", draft["project_fields"]["abstract"].lower())
        self.assertIn("irrigation", draft["keywords"])
        # The cover page's wording is now mapped onto one of the six real
        # departments rather than stored as free text.
        self.assertEqual(
            draft["project_fields"]["department_name"],
            "Department of Electronics and Computer Engineering",
        )

        # --- people ---
        names = {p["full_name"] for p in draft["people_and_roles"]}
        self.assertIn("Aarav Shrestha", names)
        self.assertIn("Nischal Karki", names)
        rolls = {p.get("roll_number") for p in draft["people_and_roles"]}
        self.assertIn("080BCT022", rolls)
        supervisors = [p for p in draft["people_and_roles"] if p["role"] == "Supervisor"]
        self.assertTrue(any("Ramesh Sharma" in p["full_name"] for p in supervisors))

        # --- sections: exactly Introduction + Literature Review, in order.
        # "1.1 Background" is a REAL nested child of Introduction now (its
        # own tree node with heading_level 2), not text folded into the
        # parent's flat content string.
        headings = [s["heading"] for s in draft["project_sections"]]
        self.assertEqual(headings, ["Introduction", "Literature Review"])

        introduction, literature = draft["project_sections"]
        self.assertEqual(introduction["heading_level"], 1)

        self.assertEqual(len(introduction["children"]), 1)
        background = introduction["children"][0]
        self.assertEqual(background["heading"], "Background")
        self.assertEqual(background["heading_level"], 2)
        self.assertIn("wastes significant", background["content"])

        # The continuation paragraph on the following page has no heading
        # of its own, so it stays part of whatever is still deepest-open --
        # Background, since it was still open when the page break happened.
        self.assertIn("continuation paragraph", background["content"])
        self.assertEqual(introduction["content"].count("wastes significant"), 0)
        self.assertEqual(introduction["page_start"], 5)
        self.assertEqual(introduction["page_end"], 6)

        self.assertIn("soil-moisture feedback", literature["content"])

        # --- References/Appendix must not leak into project_sections or duplicate ---
        for section in draft["project_sections"]:
            self.assertNotIn("Example, A. (2020)", section["content"])
        self.assertEqual(len(draft["references"]), 1)
        self.assertIn("Example, A. (2020)", draft["references"][0]["citation"])
        self.assertEqual(draft["references"][0]["citation"].count("Example, A. (2020)"), 1)

        self.assertEqual(len(draft["appendices"]), 1)
        self.assertIn("Sensor calibration", draft["appendices"][0]["content"])

    def test_heading_style_and_synonym_variation(self):
        """Different heading spellings/casing/numbering styles must each be
        recognized as a section boundary, WITHOUT rewriting the original
        wording -- "LITERATURE SURVEY" stays "LITERATURE SURVEY", it does
        not get silently renamed to "Literature Review". The synonym
        relationship is exposed separately via semantic_role/
        canonical_section, which is additive classification, not a
        replacement for the heading actually printed in the PDF."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter1(page):
            _add_block(page, (60, 60, 535, 90), "CHAPTER 1: INTRODUCTION", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Opening context for the project.")

        def chapter2(page):
            _add_block(page, (60, 60, 535, 90), "2. LITERATURE SURVEY", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Survey of prior systems.")

        def chapter3(page):
            _add_block(page, (60, 60, 535, 90), "Requirement Analysis", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Functional and non-functional requirements.")

        def chapter4(page):
            _add_block(page, (60, 60, 535, 90), "Future Enhancements", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Planned improvements for later releases.")

        pdf_bytes = build_pdf([cover, chapter1, chapter2, chapter3, chapter4])
        job = self._make_job(pdf_bytes)
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        # Headings keep their original, as-printed wording and casing.
        self.assertEqual(
            [s["heading"] for s in sections],
            ["INTRODUCTION", "LITERATURE SURVEY", "Requirement Analysis", "Future Enhancements"],
        )
        self.assertEqual(
            [s["content"] for s in sections],
            [
                "Opening context for the project.",
                "Survey of prior systems.",
                "Functional and non-functional requirements.",
                "Planned improvements for later releases.",
            ],
        )
        # The synonym relationship is still available, just additively --
        # via canonical_section/semantic_role -- not by overwriting heading.
        self.assertEqual(sections[0]["canonical_section"], "Introduction")
        self.assertEqual(sections[1]["canonical_section"], "Literature Review")
        self.assertIn("literature_review", sections[1]["semantic_role"])
        self.assertIn("requirements_analysis", sections[2]["semantic_role"])
        self.assertIn("future_enhancement", sections[3]["semantic_role"])

    def test_hyphenated_word_wrap_is_repaired_in_final_section_content(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def content_page(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(
                page, (60, 110, 260, 260),
                "This chapter describes the overall system design and imple-\n"
                "mentation strategy used for this project.",
            )

        pdf_bytes = build_pdf([cover, content_page])
        job = self._make_job(pdf_bytes)
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(len(sections), 1)
        content = sections[0]["content"]
        self.assertIn("implementation strategy", content)
        self.assertNotIn("imple-", content)

    def test_reingestion_of_identical_file_is_marked_duplicate_not_reprocessed(self):
        def content_page(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Duplicate detection body text.")

        pdf_bytes = build_pdf([content_page])

        job1 = self._make_job(pdf_bytes, filename="first.pdf")
        PipelineRunner().execute(job1)
        job1.refresh_from_db()
        self.assertEqual(job1.status, IngestionJob.Status.EXTRACTED)
        first_payload = job1.extracted_payload

        job2 = self._make_job(pdf_bytes, filename="second.pdf")
        PipelineRunner().execute(job2)
        job2.refresh_from_db()

        self.assertEqual(job2.status, IngestionJob.Status.DUPLICATE)
        # The duplicate job must not have overwritten or duplicated the
        # original job's extracted payload.
        job1.refresh_from_db()
        self.assertEqual(job1.extracted_payload, first_payload)
        self.assertEqual(job2.extracted_payload, {})

    def test_rerunning_pipeline_on_same_job_does_not_duplicate_sections(self):
        """Simulates a Celery retry re-running the whole pipeline against a
        job that already has a status/extracted_payload from a prior run."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def content_page(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Retry safety body text.")
            _add_block(page, (60, 200, 535, 230), "2 Methodology", HEADING_FONT)
            _add_block(page, (60, 250, 535, 300), "Methodology body text.")

        pdf_bytes = build_pdf([cover, content_page])
        job = self._make_job(pdf_bytes)

        PipelineRunner().execute(job)
        job.refresh_from_db()
        first_sections = job.extracted_payload["project_sections"]
        self.assertEqual(len(first_sections), 2)

        # Re-run against the same job row, as a retry would.
        PipelineRunner().execute(job)
        job.refresh_from_db()
        second_sections = job.extracted_payload["project_sections"]

        self.assertEqual(len(second_sections), 2)
        self.assertEqual(
            [s["heading"] for s in second_sections],
            [s["heading"] for s in first_sections],
        )

    # ---------------------------------------------------------------
    # Supervisor extraction
    # ---------------------------------------------------------------

    def test_supervisor_explicit_label_with_designation_on_following_line(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Supervisor")
            _add_block(page, (60, 190, 535, 240), "Dr. Sarita Koirala\nProfessor")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Sarita Koirala")
        self.assertEqual(supervisors[0]["designation"], "Professor")

    def test_supervisor_under_the_supervision_of_phrase_with_name_after_cue(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def acknowledgement(page):
            _add_block(page, (60, 60, 535, 90), "ACKNOWLEDGEMENT", HEADING_FONT)
            _add_block(page, (60, 120, 535, 220),
                       "This project was completed under the supervision of Prof. Ram Prasad "
                       "Sharma, whose expertise guided our work from start to finish.")

        job = self._make_job(build_pdf([cover, acknowledgement]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Ram Prasad Sharma")
        self.assertEqual(supervisors[0]["designation"], "Prof.")

    def test_supervisor_detected_from_acknowledgement_sentence_context(self):
        """No standalone "Supervisor:" label anywhere -- only a supervisor
        identified through natural acknowledgement prose, as raised in the
        original bug report."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def acknowledgement(page):
            _add_block(page, (60, 60, 535, 90), "ACKNOWLEDGEMENT", HEADING_FONT)
            _add_block(
                page, (60, 120, 535, 260),
                "Our sincere thanks go to the IC Chair, Asst. Prof. Bikal Adhikari, "
                "who also serves as our supervisor, for his continuous guidance and "
                "support throughout this project.",
            )

        job = self._make_job(build_pdf([cover, acknowledgement]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Bikal Adhikari")
        self.assertEqual(supervisors[0]["designation"], "Asst. Prof.")

    def test_supervisor_context_detection_does_not_misclassify_nearby_faculty(self):
        """A department head and an IC Chair are named in the same
        acknowledgement without any supervisor cue phrase attached to them,
        and must NOT be picked up -- only the person actually tied to a
        supervisor cue phrase should be."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def acknowledgement(page):
            _add_block(page, (60, 60, 535, 90), "ACKNOWLEDGEMENT", HEADING_FONT)
            _add_block(
                page, (60, 120, 535, 180),
                "We would like to thank Prof. Ram Sharma, our Head of Department, "
                "and Dr. Sita Gurung, the IC Chair, for their continued support.",
            )
            _add_block(
                page, (60, 200, 535, 260),
                "This project was supervised by Asst. Prof. Bikal Adhikari, whose "
                "guidance was invaluable throughout.",
            )

        job = self._make_job(build_pdf([cover, acknowledgement]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Bikal Adhikari")

    def test_supervisor_with_stacked_title_designation_is_split_from_name(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Supervisor: Prof. Dr. Manoj Shrestha")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Manoj Shrestha")
        # A stacked prefix carries two different facts and they go to two
        # different fields. Keeping both in `designation` meant a rank read
        # off a following line overwrote the honorific, and the "Dr."
        # vanished from the published record.
        self.assertEqual(supervisors[0]["designation"], "Prof.")
        self.assertEqual(supervisors[0]["title"], "Dr.")

    # ---------------------------------------------------------------
    # Author / student-member extraction
    # ---------------------------------------------------------------

    def test_authors_same_line_name_and_roll_two_students(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(page, (60, 200, 535, 260),
                       "Aarav Shrestha (080BCT022)\nNischal Karki (079BCT047)")

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        authors = [
            p for p in context["draft_metadata"]["people_and_roles"] if p["role"] == "Author"
        ]

        self.assertEqual(
            [(a["full_name"], a["roll_number"]) for a in authors],
            [("Aarav Shrestha", "080BCT022"), ("Nischal Karki", "079BCT047")],
        )

    def test_authors_submitted_by_label_with_names_and_rolls_on_separate_lines(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(
                page, (60, 200, 535, 340),
                "Submitted By:\n"
                "Prabin Adhikari\n"
                "081BCT013\n"
                "Sujata Koirala\n"
                "080BCT041\n"
                "Kabin Thapa\n"
                "082BCT007",
            )

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        authors = [
            p for p in context["draft_metadata"]["people_and_roles"] if p["role"] == "Author"
        ]

        # 3 students, name-then-roll on separate lines, "Submitted By:" label
        # not itself mistaken for a fourth author.
        self.assertEqual(
            [(a["full_name"], a["roll_number"]) for a in authors],
            [
                ("Prabin Adhikari", "081BCT013"),
                ("Sujata Koirala", "080BCT041"),
                ("Kabin Thapa", "082BCT007"),
            ],
        )

    def test_authors_multiple_students_packed_onto_one_line(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(
                page, (60, 200, 535, 240),
                "Aarav Shrestha 080BCT022, Nischal Karki 079BCT047 and Prabin Adhikari 081BCT013",
            )

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        authors = [
            p for p in context["draft_metadata"]["people_and_roles"] if p["role"] == "Author"
        ]

        self.assertEqual(
            [(a["full_name"], a["roll_number"]) for a in authors],
            [
                ("Aarav Shrestha", "080BCT022"),
                ("Nischal Karki", "079BCT047"),
                ("Prabin Adhikari", "081BCT013"),
            ],
        )

    def test_authors_four_students_roll_before_name_and_letter_prefixed_roll(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(
                page, (60, 200, 535, 400),
                "Student Members\n"
                "075BEX015\n"
                "Anisha Rai\n"
                "PUL080BCT099\n"
                "Kiran Magar\n"
                "081BEI005\n"
                "Sabina Thapa\n"
                "079BCT002\n"
                "Rohit Bhandari",
            )

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        authors = [
            p for p in context["draft_metadata"]["people_and_roles"] if p["role"] == "Author"
        ]

        # Roll-before-name ordering, 4 students, and a letter-prefixed roll
        # number ("PUL080BCT099") cleaned the same way as an unprefixed one.
        self.assertEqual(
            [(a["full_name"], a["roll_number"]) for a in authors],
            [
                ("Anisha Rai", "075BEX015"),
                ("Kiran Magar", "080BCT099"),
                ("Sabina Thapa", "081BEI005"),
                ("Rohit Bhandari", "079BCT002"),
            ],
        )

    def test_authors_are_not_confused_with_supervisor_on_same_pages(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(page, (60, 200, 535, 260),
                       "Aarav Shrestha (080BCT022)\nNischal Karki (079BCT047)")

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Supervisor")
            _add_block(page, (60, 190, 535, 220), "Dr. Sarita Koirala")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        people = context["draft_metadata"]["people_and_roles"]

        authors = [p for p in people if p["role"] == "Author"]
        supervisors = [p for p in people if p["role"] == "Supervisor"]
        self.assertEqual(len(authors), 2)
        self.assertEqual(len(supervisors), 1)
        self.assertNotIn("Sarita Koirala", {a["full_name"] for a in authors})
        self.assertNotIn("Aarav Shrestha", {s["full_name"] for s in supervisors})

    # ---------------------------------------------------------------
    # Section extraction: deep numbering, unnumbered chapters, TOC leaders
    # ---------------------------------------------------------------

    def test_sections_numbered_subsections_fold_into_correct_parent_main_section(self):
        """Generic hierarchy test across multiple main sections (not just
        Introduction): each numbered subsection (1.x, 2.x, 3.x) must become
        a real nested child of its own main section -- never a top-level
        record of its own, and never a child of a different main section."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter1(page):
            y = 60
            _add_block(page, (60, y, 535, y + 30), "1 Introduction", HEADING_FONT)
            y += 45
            for n, name in [(1, "Background"), (2, "Problem Statement"), (3, "Objectives")]:
                _add_block(page, (60, y, 535, y + 26), f"1.{n} {name}", SUBHEADING_FONT)
                y += 30
                _add_block(page, (60, y, 535, y + 22), f"Section 1 body for {name}.")
                y += 30

        def chapter2(page):
            y = 60
            _add_block(page, (60, y, 535, y + 30), "2 Literature Review", HEADING_FONT)
            y += 45
            for n, name in [(1, "Existing Systems"), (2, "Related Work")]:
                _add_block(page, (60, y, 535, y + 26), f"2.{n} {name}", SUBHEADING_FONT)
                y += 30
                _add_block(page, (60, y, 535, y + 22), f"Section 2 body for {name}.")
                y += 30

        def chapter3(page):
            y = 60
            _add_block(page, (60, y, 535, y + 30), "3 Methodology", HEADING_FONT)
            y += 45
            for n, name in [(1, "Data Collection"), (2, "Data Processing"), (3, "Model Development")]:
                _add_block(page, (60, y, 535, y + 26), f"3.{n} {name}", SUBHEADING_FONT)
                y += 30
                _add_block(page, (60, y, 535, y + 22), f"Section 3 body for {name}.")
                y += 30

        job = self._make_job(build_pdf([cover, chapter1, chapter2, chapter3]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        # Exactly one top-level tree node per MAIN section -- 1.1/1.2/1.3/
        # 2.1/2.2/3.1/3.2/3.3 are now real nested children, not text folded
        # into the parent's own content.
        self.assertEqual(
            [s["heading"] for s in sections],
            ["Introduction", "Literature Review", "Methodology"],
        )
        self.assertTrue(all(s["heading_level"] == 1 for s in sections))
        introduction, literature, methodology = sections

        def child_map(node):
            return {c["heading"]: c for c in node["children"]}

        intro_children = child_map(introduction)
        for n, name in [(1, "Background"), (2, "Problem Statement"), (3, "Objectives")]:
            self.assertIn(name, intro_children)
            self.assertEqual(intro_children[name]["heading_level"], 2)
            self.assertIn(f"Section 1 body for {name}.", intro_children[name]["content"])

        lit_children = child_map(literature)
        for n, name in [(1, "Existing Systems"), (2, "Related Work")]:
            self.assertIn(name, lit_children)
            self.assertIn(f"Section 2 body for {name}.", lit_children[name]["content"])

        method_children = child_map(methodology)
        for n, name in [(1, "Data Collection"), (2, "Data Processing"), (3, "Model Development")]:
            self.assertIn(name, method_children)
            self.assertIn(f"Section 3 body for {name}.", method_children[name]["content"])

        # Section 2's subsections must not leak into section 1 (or vice
        # versa), and section 3's must not leak into either.
        self.assertNotIn("Section 2 body", str(intro_children))
        self.assertNotIn("Section 3 body", str(intro_children))
        self.assertNotIn("Section 1 body", str(lit_children))
        self.assertNotIn("Section 3 body", str(lit_children))
        self.assertNotIn("Section 1 body", str(method_children))
        self.assertNotIn("Section 2 body", str(method_children))
        self.assertEqual(introduction["content"], "")
        self.assertEqual(literature["content"], "")
        self.assertEqual(methodology["content"], "")

    def test_sections_deep_numbering_folds_into_top_level_main_section(self):
        """1.1.1 / 1.1.2 (three numbering levels) must nest three levels
        deep -- Introduction > Background > Historical Context / Current
        Landscape -- not become independent top-level records and not get
        silently dropped or flattened into their grandparent's content."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 140), "1.1 Background", SUBHEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "1.1.1 Historical Context", SUBHEADING_FONT)
            _add_block(page, (60, 190, 535, 220), "Deep subsection body text.")
            _add_block(page, (60, 240, 535, 270), "1.1.2 Current Landscape", SUBHEADING_FONT)
            _add_block(page, (60, 280, 535, 310), "Second deep subsection body text.")

        job = self._make_job(build_pdf([cover, chapter]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual([s["heading"] for s in sections], ["Introduction"])
        introduction = sections[0]
        self.assertEqual(introduction["content"], "")
        self.assertEqual(len(introduction["children"]), 1)

        background = introduction["children"][0]
        self.assertEqual(background["heading"], "Background")
        self.assertEqual(background["heading_level"], 2)
        self.assertEqual(background["content"], "")
        self.assertEqual(len(background["children"]), 2)

        historical, current = background["children"]
        self.assertEqual(historical["heading"], "Historical Context")
        self.assertEqual(historical["heading_level"], 3)
        self.assertIn("Deep subsection body text.", historical["content"])
        self.assertEqual(current["heading"], "Current Landscape")
        self.assertEqual(current["heading_level"], 3)
        self.assertIn("Second deep subsection body text.", current["content"])

    def test_sections_without_any_numbered_subsections_are_unaffected(self):
        """Regression check: a document with only main sections and no
        numbered subsections at all must extract exactly as it did before
        subsection folding was introduced."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter1(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Plain introduction body, no subsections.")

        def chapter2(page):
            _add_block(page, (60, 60, 535, 90), "2 Methodology", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Plain methodology body, no subsections.")

        job = self._make_job(build_pdf([cover, chapter1, chapter2]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual([s["heading"] for s in sections], ["Introduction", "Methodology"])
        self.assertEqual(sections[0]["content"], "Plain introduction body, no subsections.")
        self.assertEqual(sections[1]["content"], "Plain methodology body, no subsections.")

    def test_sections_toc_continuation_page_with_spaced_dots_and_underscores_is_excluded(self):
        """A ToC continuation page that doesn't repeat the "Table of
        Contents" title can get misclassified as a content page if one of
        its rows looks like a chapter start; the dot/underscore-leader
        density guard should still recognize it as ToC and exclude it --
        including spaced dots and underscore leaders, not just tight dots."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def toc(page):
            _add_block(page, (60, 60, 535, 90), "Table of Contents", HEADING_FONT)
            _add_block(page, (60, 120, 535, 160), "1 Introduction ............ 1")

        def toc_continuation(page):
            # No "Table of Contents" heading repeated here -- and this row
            # is bold/large enough, and numbered, to otherwise look like a
            # real chapter start.
            _add_block(page, (60, 60, 535, 90), "9 References . . . . . . . . . . . 39", HEADING_FONT)
            _add_block(page, (60, 100, 535, 130), "Appendix A ________________ 45", HEADING_FONT)

        def real_content(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Real introduction body text.")

        job = self._make_job(build_pdf([cover, toc, toc_continuation, real_content]))
        context = run_extraction_stages(job)
        draft = context["draft_metadata"]

        sections = draft["project_sections"]
        self.assertEqual([s["heading"] for s in sections], ["Introduction"])
        self.assertEqual(sections[0]["content"], "Real introduction body text.")
        # The ToC continuation row text must never leak into references/appendices either.
        self.assertEqual(draft["references"], [])
        self.assertEqual(draft["appendices"], [])

    def test_sections_uppercase_titlecase_and_chapter_colon_headings_together(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter1(page):
            _add_block(page, (60, 60, 535, 90), "CHAPTER 1: INTRODUCTION", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Introduction body text.")

        def chapter2(page):
            _add_block(page, (60, 60, 535, 90), "Methodology", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Methodology body text.")

        def chapter3(page):
            _add_block(page, (60, 60, 535, 90), "CONCLUSION", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Conclusion body text.")

        job = self._make_job(build_pdf([cover, chapter1, chapter2, chapter3]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        # Original casing is preserved verbatim, per section -- "CHAPTER 1:
        # INTRODUCTION" strips the "Chapter 1:" numbering prefix (structural
        # evidence, recorded separately in `numbering`) but keeps
        # "INTRODUCTION" itself uppercase, exactly as printed.
        self.assertEqual(
            [s["heading"] for s in sections],
            ["INTRODUCTION", "Methodology", "CONCLUSION"],
        )
        self.assertEqual(
            [s["content"] for s in sections],
            ["Introduction body text.", "Methodology body text.", "Conclusion body text."],
        )
        self.assertEqual([s["canonical_section"] for s in sections], ["Introduction", "Methodology", "Conclusion"])

    # ---------------------------------------------------------------
    # Regression coverage: numbered headings outside the alias table,
    # supervisor label variants, footer page numbers.
    # ---------------------------------------------------------------

    def test_sections_numbered_heading_not_in_alias_table_is_still_recognized(self):
        """A previously-failing-PDF pattern: a report whose chapter titles
        are perfectly legitimate but don't happen to be pre-registered in
        MAJOR_SECTION_ALIASES (e.g. a domain-specific title). Numbering +
        typography alone must be enough to recognize it as a section --
        requiring an alias-table hit produced zero sections for any report
        using wording outside that fixed list."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter1(page):
            _add_block(page, (60, 60, 535, 90), "1 Problem Domain Overview", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Overview body text.")

        def chapter2(page):
            _add_block(page, (60, 60, 535, 90), "2 Sensor Network Topology", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Topology body text.")

        def chapter3(page):
            _add_block(page, (60, 60, 535, 90), "3 Deployment and Field Trials", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Field trial body text.")

        job = self._make_job(build_pdf([cover, chapter1, chapter2, chapter3]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(
            [s["heading"] for s in sections],
            ["Problem Domain Overview", "Sensor Network Topology", "Deployment and Field Trials"],
        )
        self.assertEqual(
            [s["content"] for s in sections],
            ["Overview body text.", "Topology body text.", "Field trial body text."],
        )
        self.assertTrue(all(s["heading_level"] == 1 for s in sections))

    def test_trailing_footer_page_number_is_removed_from_section_content(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def content_page(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Body text on this page.")
            # A footer page number, rendered after the body text (so it's
            # the last line PyMuPDF emits for the page) -- must not end up
            # inside the section content.
            _add_block(page, (60, 780, 535, 810), "4")

        job = self._make_job(build_pdf([cover, content_page]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["content"], "Body text on this page.")
        self.assertNotIn("4", sections[0]["content"].split("\n"))

    def test_trailing_footer_page_number_removed_across_arbitrary_page_numbers(self):
        """Must generalize to any footer number, not one hardcoded value."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def make_page(n, footer):
            def _build(page):
                _add_block(page, (60, 60, 535, 90), f"{n} Chapter {n}", HEADING_FONT)
                _add_block(page, (60, 110, 535, 160), f"Body text for Chapter {n}.")
                _add_block(page, (60, 780, 535, 810), str(footer))
            return _build

        pages = [cover] + [make_page(n, footer) for n, footer in [(1, 9), (2, 10), (3, 23)]]
        job = self._make_job(build_pdf(pages))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(len(sections), 3)
        for section, n in zip(sections, [1, 2, 3]):
            self.assertEqual(section["content"], f"Body text for Chapter {n}.")

    def test_repeated_text_running_header_and_footer_are_stripped_from_section_content(self):
        """FOOTER_PAGE_NUMBER only recognizes a bare page number, which by
        definition changes on every page. A running header/footer made of
        constant TEXT (an institution name printed on every page) needs a
        different signal: it must be caught purely because it recurs as the
        first-or-last line across the document's own pages, regardless of
        its wording."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def make_page(n):
            def _build(page):
                _add_block(page, (60, 40, 535, 60), "Pulchowk Campus, IOE")
                _add_block(page, (60, 90, 535, 120), f"{n} Chapter {n}", HEADING_FONT)
                _add_block(page, (60, 140, 535, 190), f"Body text for Chapter {n}.")
                _add_block(page, (60, 780, 535, 810), "Department of Electronics and Computer Engineering")
            return _build

        pages = [cover] + [make_page(n) for n in range(1, 6)]
        job = self._make_job(build_pdf(pages))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(len(sections), 5)
        for section, n in zip(sections, range(1, 6)):
            self.assertEqual(section["content"], f"Body text for Chapter {n}.")
            self.assertNotIn("Pulchowk Campus, IOE", section["content"])
            self.assertNotIn("Department of Electronics and Computer Engineering", section["content"])

    def test_legitimate_numbered_content_is_not_removed(self):
        """Numbered headings, numbered subsections, and numbers that are
        genuinely part of body content (not the last line on the page) must
        survive -- only a standalone number as the very last line is a
        footer candidate."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def content_page(page):
            _add_block(page, (60, 60, 535, 90), "4 Results", HEADING_FONT)
            _add_block(page, (60, 110, 535, 140), "4.1 Survey Findings", SUBHEADING_FONT)
            _add_block(page, (60, 150, 535, 200), "We surveyed 42 participants across 3 departments.")
            _add_block(page, (60, 220, 535, 250), "A total of 10 responses were incomplete.")

        job = self._make_job(build_pdf([cover, content_page]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["heading"], "Results")
        self.assertEqual(sections[0]["content"], "")
        self.assertEqual(len(sections[0]["children"]), 1)

        survey_findings = sections[0]["children"][0]
        self.assertEqual(survey_findings["heading"], "Survey Findings")
        self.assertIn("We surveyed 42 participants across 3 departments.", survey_findings["content"])
        self.assertIn("A total of 10 responses were incomplete.", survey_findings["content"])

    # ---------------------------------------------------------------
    # New architectural capabilities: multi-line titles, alias-free
    # heading recognition, hierarchy clamping, chapter-marker merging.
    # ---------------------------------------------------------------

    # ---- Part 5: section detection must be structural, not cosmetic -----

    @staticmethod
    def _plain_cover(page):
        _add_block(page, (60, 60, 535, 130), "Structural Detection Sample",
                   {"fontsize": 18, "fontname": "hebo"})

    @staticmethod
    def _headings_of(sections):
        """Flattens the tree to (depth, heading) pairs in document order."""
        out = []

        def walk(nodes, depth=1):
            for node in nodes:
                out.append((depth, node["heading"]))
                walk(node.get("children") or [], depth + 1)

        walk(sections)
        return out

    def test_numbered_hierarchy_nests_by_its_own_numbering(self):
        """A. Numbering is the strongest structural signal and must drive
        the tree: 1.2.1 belongs under 1.2, which belongs under 1."""

        def body(page):
            _add_block(page, (60, 50, 535, 78), "1. INTRODUCTION", HEADING_FONT)
            _add_block(page, (60, 82, 535, 120), "Opening paragraph of the introduction section.")
            _add_block(page, (60, 130, 535, 158), "1.1 BACKGROUND", HEADING_FONT)
            _add_block(page, (60, 162, 535, 200), "Background discussion paragraph text here.")
            _add_block(page, (60, 210, 535, 238), "1.2 OBJECTIVES", HEADING_FONT)
            _add_block(page, (60, 242, 535, 280), "Objectives discussion paragraph text here.")
            _add_block(page, (60, 290, 535, 318), "1.2.1 SPECIFIC OBJECTIVES", HEADING_FONT)
            _add_block(page, (60, 322, 535, 360), "Specific objectives paragraph text here.")
            _add_block(page, (60, 380, 535, 408), "2. LITERATURE REVIEW", HEADING_FONT)
            _add_block(page, (60, 412, 535, 450), "Literature review paragraph text here.")
            _add_block(page, (60, 460, 535, 488), "2.1 RELATED WORK", HEADING_FONT)
            _add_block(page, (60, 492, 535, 530), "Related work paragraph text here.")

        job = self._make_job(build_pdf([self._plain_cover, body]))
        sections = run_extraction_stages(job)["draft_metadata"]["project_sections"]

        self.assertEqual(
            self._headings_of(sections),
            [
                (1, "INTRODUCTION"),
                (2, "BACKGROUND"),
                (2, "OBJECTIVES"),
                (3, "SPECIFIC OBJECTIVES"),
                (1, "LITERATURE REVIEW"),
                (2, "RELATED WORK"),
            ],
        )

    def test_deep_numbering_is_preserved(self):
        """D. Four levels deep, when the document genuinely has them."""

        def body(page):
            _add_block(page, (60, 50, 535, 78), "1. SYSTEM DESIGN", HEADING_FONT)
            _add_block(page, (60, 82, 535, 118), "Overview paragraph for the design section.")
            _add_block(page, (60, 128, 535, 156), "1.1 ARCHITECTURE", HEADING_FONT)
            _add_block(page, (60, 160, 535, 196), "Architecture paragraph text goes here.")
            _add_block(page, (60, 206, 535, 234), "1.1.1 DATA LAYER", HEADING_FONT)
            _add_block(page, (60, 238, 535, 274), "Data layer paragraph text goes here.")
            _add_block(page, (60, 284, 535, 312), "1.1.1.1 SCHEMA DETAIL", HEADING_FONT)
            _add_block(page, (60, 316, 535, 352), "Schema detail paragraph text goes here.")

        job = self._make_job(build_pdf([self._plain_cover, body]))
        sections = run_extraction_stages(job)["draft_metadata"]["project_sections"]

        self.assertEqual(
            self._headings_of(sections),
            [
                (1, "SYSTEM DESIGN"),
                (2, "ARCHITECTURE"),
                (3, "DATA LAYER"),
                (4, "SCHEMA DETAIL"),
            ],
        )

    def test_block_labels_stay_inside_their_section(self):
        """B. "CPU", "RAM", "Storage" are labels inside a requirements
        section, not subsections of it -- even though each is bold, short,
        capitalised and alone in its own layout block."""

        def body(page):
            _add_block(page, (60, 50, 535, 78), "4. HARDWARE REQUIREMENTS", HEADING_FONT)
            _add_block(page, (60, 84, 535, 120),
                       "The system was evaluated on the configuration below.")
            # Boxes are generously sized: insert_textbox silently drops
            # text that does not fit, which would remove the very labels
            # this test is about.
            _add_block(page, (60, 130, 535, 165), "CPU", HEADING_FONT)
            _add_block(page, (60, 170, 535, 200), "Intel Core i5 or equivalent")
            _add_block(page, (60, 210, 535, 245), "RAM", HEADING_FONT)
            _add_block(page, (60, 250, 535, 280), "8 GB minimum")
            _add_block(page, (60, 290, 535, 325), "System Memory", HEADING_FONT)
            _add_block(page, (60, 330, 535, 360), "16 GB")
            _add_block(page, (60, 370, 535, 405), "Storage", HEADING_FONT)
            _add_block(page, (60, 410, 535, 440), "512 GB SSD")

        job = self._make_job(build_pdf([self._plain_cover, body]))
        sections = run_extraction_stages(job)["draft_metadata"]["project_sections"]
        headings = self._headings_of(sections)

        self.assertEqual(len(headings), 1, f"labels became sections: {headings}")
        self.assertEqual(headings[0], (1, "HARDWARE REQUIREMENTS"))

        # The labels and their values are still present -- kept as content
        # of the section rather than discarded.
        content = sections[0]["content"]
        for label in ("CPU", "RAM", "Storage"):
            self.assertIn(label, content)

    def test_formula_fragments_never_become_sections(self):
        """C. Equation pieces are bold, isolated and oddly sized -- exactly
        the profile that used to score highest -- and must stay content."""

        def body(page):
            _add_block(page, (60, 50, 535, 78), "3. METHODOLOGY", HEADING_FONT)
            _add_block(page, (60, 84, 535, 120),
                       "The proposed model uses the following transformation.")
            _add_block(page, (60, 130, 535, 168), "FFN ( xᵢ − 1 )", HEADING_FONT)
            _add_block(page, (60, 175, 535, 213), "19FFN ( x̃′′", HEADING_FONT)
            _add_block(page, (60, 220, 535, 255), "10", HEADING_FONT)
            _add_block(page, (60, 265, 535, 305), "where x represents the input sequence.")

        job = self._make_job(build_pdf([self._plain_cover, body]))
        sections = run_extraction_stages(job)["draft_metadata"]["project_sections"]
        headings = self._headings_of(sections)

        self.assertEqual(len(headings), 1, f"formula became a section: {headings}")
        self.assertEqual(headings[0], (1, "METHODOLOGY"))

    def test_unnumbered_heading_still_detected_with_supporting_signals(self):
        """E. The parser must not become numbering-only: a genuine
        unnumbered heading with real body text behind it is still a
        section."""

        def chapter_one(page):
            _add_block(page, (60, 60, 535, 90), "Sensor Calibration Walkthrough", HEADING_FONT)
            _add_block(page, (60, 110, 535, 170),
                       "A full paragraph describing the calibration procedure in detail.")

        def chapter_two(page):
            _add_block(page, (60, 60, 535, 90), "Field Deployment Notes", HEADING_FONT)
            _add_block(page, (60, 110, 535, 170),
                       "A full paragraph describing the deployment observations.")

        job = self._make_job(build_pdf([self._plain_cover, chapter_one, chapter_two]))
        sections = run_extraction_stages(job)["draft_metadata"]["project_sections"]

        self.assertEqual(
            self._headings_of(sections),
            [(1, "Sensor Calibration Walkthrough"), (1, "Field Deployment Notes")],
        )

    def test_each_node_keeps_its_own_content_for_future_chunking(self):
        """Parents must not absorb their children's text: a chunker needs
        heading / heading_level / display_order / own content / children,
        with content stored exactly once."""

        def body(page):
            _add_block(page, (60, 50, 535, 78), "1. INTRODUCTION", HEADING_FONT)
            _add_block(page, (60, 82, 535, 120), "Parent paragraph belonging to the introduction.")
            _add_block(page, (60, 130, 535, 158), "1.1 BACKGROUND", HEADING_FONT)
            _add_block(page, (60, 162, 535, 200), "Child paragraph belonging to background only.")

        job = self._make_job(build_pdf([self._plain_cover, body]))
        sections = run_extraction_stages(job)["draft_metadata"]["project_sections"]

        parent = sections[0]
        child = parent["children"][0]

        for key in ("heading", "heading_level", "display_order", "content", "children"):
            self.assertIn(key, parent)

        self.assertIn("Parent paragraph", parent["content"])
        self.assertIn("Child paragraph", child["content"])
        # No duplication: the child's text must not also sit in the parent.
        self.assertNotIn("Child paragraph", parent["content"])

    # ---- Part 6: representative real-world cover page --------------------

    @staticmethod
    def _representative_cover(page):
        """The cover layout that broke title and supervisor extraction: the
        report marker and "On" on separate lines, the title beneath them,
        then the author block, the department, the degree statement and
        finally "Under the Supervision of" with the name below it."""
        _add_block(page, (60, 40, 535, 70), "TRIBHUVAN UNIVERSITY")
        _add_block(page, (60, 72, 535, 100), "INSTITUTE OF ENGINEERING")
        _add_block(page, (60, 102, 535, 130), "PULCHOWK CAMPUS")
        _add_block(page, (60, 150, 535, 178), "A Major Project Final Report")
        _add_block(page, (60, 180, 535, 205), "On")
        _add_block(
            page, (55, 215, 545, 275),
            "Nepali Automatic Speech Recognition\nUsing Conformer Based Architecture",
            {"fontsize": 17, "fontname": "hebo"},
        )
        _add_block(page, (60, 290, 535, 315), "Submitted By:")
        _add_block(
            page, (60, 320, 535, 445),
            "Rupesh Yadav\n078BCT065\nSijan Khadka\n078BCT088\nSudip Basnet\n078BCT092",
        )
        _add_block(page, (60, 455, 535, 480), "Submitted To:")
        _add_block(
            page, (60, 485, 535, 555),
            "Department of Electronics and Computer Engineering\nPulchowk Campus\nLalitpur, Nepal",
        )
        _add_block(page, (60, 565, 535, 590), "May, 2026")
        _add_block(
            page, (55, 600, 545, 655),
            "In partial fulfillment for the award of a Bachelor's degree in Computer Engineering",
        )
        _add_block(page, (60, 665, 535, 690), "Under the Supervision of")
        _add_block(page, (60, 695, 535, 730), "Dr. Ranju Kumari Shiwakoti")

    def test_representative_cover_title_is_the_project_not_a_student(self):
        job = self._make_job(build_pdf([self._representative_cover]))
        fields = run_extraction_stages(job)["draft_metadata"]["project_fields"]
        title = fields["title"] or ""

        self.assertIn("Nepali Automatic Speech Recognition", title)
        self.assertIn("Conformer Based Architecture", title)
        # The single most important guarantee: a student's name must never
        # be stored as the project title.
        for student in ("Rupesh Yadav", "Sijan Khadka", "Sudip Basnet"):
            self.assertNotIn(student, title)

    def test_representative_cover_supervisor_is_extracted(self):
        job = self._make_job(build_pdf([self._representative_cover]))
        people = run_extraction_stages(job)["draft_metadata"]["people_and_roles"]
        supervisors = [p for p in people if p["role"] == "Supervisor"]

        self.assertTrue(supervisors, "no supervisor extracted from the cover page")
        self.assertTrue(
            any("Shiwakoti" in p["full_name"] for p in supervisors),
            f"supervisor name not recovered: {[p['full_name'] for p in supervisors]}",
        )
        # The department and the "Submitted To" label must never be
        # mistaken for a person.
        for person in people:
            lowered = person["full_name"].lower()
            self.assertNotIn("department", lowered)
            self.assertNotIn("submitted", lowered)
            self.assertNotIn("campus", lowered)

    def test_representative_cover_students_and_department(self):
        job = self._make_job(build_pdf([self._representative_cover]))
        draft = run_extraction_stages(job)["draft_metadata"]
        authors = [p for p in draft["people_and_roles"] if p["role"] == "Author"]

        self.assertGreaterEqual(len(authors), 3)
        names = " ".join(a["full_name"] for a in authors)
        for student in ("Rupesh", "Sijan", "Sudip"):
            self.assertIn(student, names)

        self.assertEqual(
            draft["project_fields"]["department_name"],
            "Department of Electronics and Computer Engineering",
        )

    def test_supervisor_name_wrapped_across_two_lines_is_rejoined(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 100), "A Minor Project Report On",
                       {"fontsize": 14})
            _add_block(page, (60, 120, 535, 170), "Adaptive Traffic Signal Control",
                       {"fontsize": 17, "fontname": "hebo"})
            _add_block(page, (60, 300, 535, 330), "Under the Supervision of")
            # The surname wraps onto its own rendered line.
            _add_block(page, (60, 340, 535, 400), "Dr. Ranju Kumari\nShiwakoti")

        job = self._make_job(build_pdf([cover]))
        people = run_extraction_stages(job)["draft_metadata"]["people_and_roles"]
        supervisors = [p for p in people if p["role"] == "Supervisor"]

        self.assertTrue(supervisors)
        self.assertTrue(
            any("Shiwakoti" in p["full_name"] for p in supervisors),
            f"wrapped surname lost: {[p['full_name'] for p in supervisors]}",
        )

    def test_multiple_supervisors_under_one_label(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 100), "A Major Project Report On",
                       {"fontsize": 14})
            _add_block(page, (60, 120, 535, 170), "Distributed Ledger For Land Records",
                       {"fontsize": 17, "fontname": "hebo"})
            _add_block(page, (60, 300, 535, 330), "Supervised By")
            _add_block(page, (60, 340, 535, 420),
                       "Dr. Anita Sharma\nAssociate Professor\nEr. Bimal Thapa\nAssistant Professor")

        job = self._make_job(build_pdf([cover]))
        people = run_extraction_stages(job)["draft_metadata"]["people_and_roles"]
        names = [p["full_name"] for p in people if p["role"] == "Supervisor"]

        self.assertGreaterEqual(len(names), 2, f"expected two supervisors, got {names}")
        self.assertTrue(any("Anita" in n for n in names))
        self.assertTrue(any("Bimal" in n for n in names))

    def test_multi_line_title_is_merged_from_cover_page_typography(self):
        """A title wrapped across several rendered lines in the same
        layout block must be merged into one string using the cover page's
        own font-size/block information, not truncated to its first line."""

        def cover(page):
            _add_block(
                page, (60, 80, 535, 200),
                "AI-BASED UNDERGRADUATE PROJECT\nDISCOVERY AND KNOWLEDGE\nRETRIEVAL PLATFORM",
                {"fontsize": 20, "fontname": "hebo"},
            )
            _add_block(page, (60, 300, 535, 340), "Submitted By:\nAarav Shrestha (080BCT022)")
            _add_block(page, (60, 400, 535, 440), "Department of Computer Engineering\n2081")

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        title = context["draft_metadata"]["project_fields"]["title"]

        self.assertIn("AI-BASED UNDERGRADUATE PROJECT", title)
        self.assertIn("DISCOVERY AND KNOWLEDGE", title)
        self.assertIn("RETRIEVAL PLATFORM", title)

    def test_title_does_not_absorb_submitted_by_on_the_same_line(self):
        """Cover pages frequently render the title and the next piece of
        boilerplate as one line. The stored title must stop at the
        boilerplate rather than carrying "SUBMITTED BY" into the catalogue.
        """

        def cover(page):
            _add_block(page, (60, 40, 535, 70), "TRIBHUVAN UNIVERSITY")
            _add_block(page, (60, 80, 535, 110), "A PROJECT REPORT ON")
            _add_block(
                page, (60, 130, 535, 190),
                "SMART IRRIGATION CONTROL SYSTEM SUBMITTED BY",
                {"fontsize": 18, "fontname": "hebo"},
            )
            _add_block(page, (60, 220, 535, 260), "Aarav Shrestha 080BCT022")

        job = self._make_job(build_pdf([cover]))
        title = run_extraction_stages(job)["draft_metadata"]["project_fields"]["title"]

        self.assertIn("SMART IRRIGATION CONTROL SYSTEM", title)
        self.assertNotIn("SUBMITTED", title.upper())

    def test_title_stops_before_a_degree_statement(self):
        """"In partial fulfilment of ... Bachelor of ..." is the degree
        statement, not part of the project's name."""

        def cover(page):
            _add_block(page, (60, 80, 535, 110), "A MAJOR PROJECT REPORT ON")
            _add_block(
                page, (60, 130, 535, 200),
                "NEPALI SIGN LANGUAGE RECOGNITION",
                {"fontsize": 18, "fontname": "hebo"},
            )
            _add_block(
                page, (60, 220, 535, 300),
                "In partial fulfilment of the requirements for the degree of\n"
                "Bachelor of Engineering in Computer Engineering",
            )

        job = self._make_job(build_pdf([cover]))
        title = run_extraction_stages(job)["draft_metadata"]["project_fields"]["title"]

        self.assertIn("NEPALI SIGN LANGUAGE RECOGNITION", title)
        for phrase in ("partial fulfil", "bachelor of", "degree of"):
            self.assertNotIn(phrase, title.lower())

    def test_title_stops_before_author_roll_numbers_in_the_same_block(self):
        """When the largest-font block runs on into the author list, the
        roll number ends the title."""

        def cover(page):
            _add_block(
                page, (60, 80, 535, 220),
                "AUTOMATED FARE COLLECTION SYSTEM\nSujan Karki 078BCT045",
                {"fontsize": 19, "fontname": "hebo"},
            )

        job = self._make_job(build_pdf([cover]))
        title = run_extraction_stages(job)["draft_metadata"]["project_fields"]["title"]

        self.assertIn("AUTOMATED FARE COLLECTION SYSTEM", title)
        self.assertNotIn("078BCT045", title)
        self.assertNotIn("Sujan", title)

    def test_institution_header_alone_is_never_stored_as_the_title(self):
        """A cover whose largest font is the institution header must not
        yield the institution name as the project title."""

        def cover(page):
            _add_block(
                page, (60, 40, 535, 90), "TRIBHUVAN UNIVERSITY",
                {"fontsize": 22, "fontname": "hebo"},
            )
            _add_block(page, (60, 100, 535, 130), "INSTITUTE OF ENGINEERING")
            _add_block(page, (60, 140, 535, 170), "PULCHOWK CAMPUS")
            _add_block(page, (60, 190, 535, 220), "A PROJECT REPORT ON")
            _add_block(
                page, (60, 240, 535, 300), "CAMPUS NAVIGATION AND EVENT PLATFORM",
                {"fontsize": 18, "fontname": "hebo"},
            )

        job = self._make_job(build_pdf([cover]))
        title = run_extraction_stages(job)["draft_metadata"]["project_fields"]["title"]

        self.assertIn("CAMPUS NAVIGATION AND EVENT PLATFORM", title)
        self.assertNotIn("TRIBHUVAN", title.upper())
        self.assertNotIn("INSTITUTE OF ENGINEERING", title.upper())

    def test_multi_word_title_containing_campus_is_not_over_trimmed(self):
        """"Campus" is a legitimate word in a project title; only the
        institutional phrase "Pulchowk Campus" is boilerplate. The trimmer
        must not eat a title that merely contains the word."""

        def cover(page):
            _add_block(page, (60, 80, 535, 110), "A PROJECT REPORT ON")
            _add_block(
                page, (60, 130, 535, 200),
                "SMART CAMPUS ENERGY MONITORING SYSTEM",
                {"fontsize": 18, "fontname": "hebo"},
            )

        job = self._make_job(build_pdf([cover]))
        title = run_extraction_stages(job)["draft_metadata"]["project_fields"]["title"]

        self.assertIn("SMART CAMPUS ENERGY MONITORING SYSTEM", title)

    def test_title_extracted_from_project_report_on_marker_not_university_header(self):
        """The real-world Pulchowk/IOE cover template renders the
        institution header ("TRIBHUVAN UNIVERSITY"), the "A PROJECT REPORT
        ON" marker, and the actual title all in the SAME largest font on
        the page (sometimes even the same layout block) -- pure font-size
        tiering has no way to tell them apart and was picking the
        institution header as the title. The "...PROJECT REPORT ON"
        marker is a much stronger, template-specific anchor: whatever
        immediately follows it is the title, regardless of its font size
        relative to the header above it."""

        def cover(page):
            _add_block(page, (60, 40, 535, 90), "TRIBHUVAN UNIVERSITY", {"fontsize": 20, "fontname": "hebo"})
            _add_block(page, (60, 95, 535, 145), "INSTITUTE OF ENGINEERING", {"fontsize": 20, "fontname": "hebo"})
            _add_block(page, (60, 150, 535, 200), "PULCHOWK CAMPUS", {"fontsize": 20, "fontname": "hebo"})
            _add_block(page, (60, 230, 535, 270), "A", {"fontsize": 14, "fontname": "hebo"})
            _add_block(page, (60, 275, 535, 315), "PROJECT REPORT", {"fontsize": 14, "fontname": "hebo"})
            _add_block(page, (60, 320, 535, 360), "ON", {"fontsize": 14, "fontname": "hebo"})
            _add_block(
                page, (60, 390, 535, 480),
                "Adaptive Indoor Noise Cancellation using PPO-Reinforcement Learning and\nGenetic Algorithm Benchmarking",
                {"fontsize": 20, "fontname": "hebo"},
            )
            _add_block(page, (60, 550, 535, 620), "SUBMITTED BY:\nAnurag Sah (078BEI004)")
            _add_block(page, (60, 650, 535, 700), "DEPARTMENT OF ELECTRONICS & COMPUTER ENGINEERING")

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        title = context["draft_metadata"]["project_fields"]["title"]

        self.assertIn("Adaptive Indoor Noise Cancellation", title)
        self.assertNotIn("TRIBHUVAN UNIVERSITY", title)

    def test_unnumbered_novel_wording_heading_recognized_without_alias_hit(self):
        """A heading whose wording is deliberately NOT in
        MAJOR_SECTION_ALIASES, and has no numbering, must still be
        recognized purely from typography (bold + a real font-size lift
        over body text) -- this is the direct fix for "any report using
        section wording outside a fixed list produced zero sections for
        that heading, and its content silently leaked into whatever
        section was still open."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter1(page):
            _add_block(page, (60, 60, 535, 90), "Sensor Calibration Walkthrough", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Body text describing calibration steps.")

        def chapter2(page):
            _add_block(page, (60, 60, 535, 90), "Field Deployment Notes", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Body text describing deployment.")

        job = self._make_job(build_pdf([cover, chapter1, chapter2]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(
            [s["heading"] for s in sections],
            ["Sensor Calibration Walkthrough", "Field Deployment Notes"],
        )
        # No alias hit for either -- semantic_role stays empty rather than
        # being forced into an unrelated bucket.
        self.assertEqual(sections[0]["semantic_role"], [])
        self.assertEqual(sections[1]["semantic_role"], [])
        self.assertNotIn("Body text describing deployment.", sections[0]["content"])
        self.assertNotIn("Body text describing calibration steps.", sections[1]["content"])

    def test_declaration_page_with_no_prose_is_not_torn_into_sections(self):
        """A declaration/title-block page (institution name, "SUBMITTED
        BY:", author names) is made of several short, bold, larger-than-
        body lines -- heading-shaped by typography alone, exactly like a
        real chapter heading. Without a genuine sentence of body prose
        following it, it must NOT be promoted to "content" and torn into
        garbage nested sections; it must be skipped entirely so only the
        real chapter below shows up in project_sections."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def declaration(page):
            _add_block(page, (60, 60, 535, 90), "TRIBHUVAN UNIVERSITY", HEADING_FONT)
            _add_block(page, (60, 100, 535, 130), "INSTITUTE OF ENGINEERING", HEADING_FONT)
            _add_block(page, (60, 140, 535, 170), "SUBMITTED BY", HEADING_FONT)
            _add_block(page, (60, 180, 535, 210), "Aarav Shrestha", HEADING_FONT)

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "This chapter introduces the project in detail.")

        job = self._make_job(build_pdf([cover, declaration, chapter]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual([s["heading"] for s in sections], ["Introduction"])
        self.assertEqual(sections[0]["content"], "This chapter introduces the project in detail.")

    def test_body_sentence_mentioning_approval_or_recommendation_is_not_misread_as_front_matter(self):
        """APPROVAL/COPYRIGHT front-matter detection must be anchored to a
        whole title line ("CERTIFICATE OF APPROVAL", "APPROVAL"), not a
        substring search -- a real content page whose body prose happens to
        use the ordinary English words "approval" or "recommendation" (e.g.
        a genuine "Recommendations" chapter) must still be classified as
        content and extracted, not silently swallowed as a front-matter
        page and lost."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "5 Conclusion and Recommendation", HEADING_FONT)
            _add_block(
                page, (60, 110, 535, 170),
                "We recommend further testing before deployment approval is granted.",
            )

        job = self._make_job(build_pdf([cover, chapter]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["heading"], "Conclusion and Recommendation")
        self.assertEqual(
            sections[0]["content"],
            "We recommend further testing before deployment approval is granted.",
        )

    def test_orphan_deep_numbering_is_clamped_and_recorded_as_warning(self):
        """A "1.1.1" heading appearing with no "1.1" ever having been seen
        must be demoted to the deepest legal level (a child of "1", not an
        orphaned level-3 node), and the demotion must be recorded as a
        processing warning rather than silently reshaping the document."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 140), "1.1.1 Skipped Level Heading", SUBHEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Body text under the orphaned heading.")

        job = self._make_job(build_pdf([cover, chapter]))
        context = run_extraction_stages(job)
        draft = context["draft_metadata"]
        sections = draft["project_sections"]

        self.assertEqual(len(sections), 1)
        self.assertEqual(len(sections[0]["children"]), 1)
        child = sections[0]["children"][0]
        self.assertEqual(child["heading"], "Skipped Level Heading")
        self.assertEqual(child["heading_level"], 2)  # clamped from 3 down to 2
        self.assertIn("Body text under the orphaned heading.", child["content"])

        self.assertTrue(
            any("Skipped Level Heading" in w and "demoted" in w for w in draft["processing_warnings"])
        )

    def test_chapter_marker_and_title_on_separate_lines_are_merged(self):
        """A standalone "CHAPTER I" marker rendered on its own line, with
        the actual title ("INTRODUCTION") on the next line, must be
        reconstructed into one heading line before section extraction --
        not silently dropped, and not left as an orphaned title-less
        marker."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "CHAPTER I", HEADING_FONT)
            _add_block(page, (60, 100, 535, 130), "INTRODUCTION", HEADING_FONT)
            _add_block(page, (60, 150, 535, 200), "Introduction body text.")

        job = self._make_job(build_pdf([cover, chapter]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        self.assertEqual(len(sections), 1)
        # The two lines are merged into one before section extraction ever
        # runs, so the heading is recognized at all (numbering="1" from
        # "Chapter I", stripped out into the separate `numbering` field the
        # same way "1 Introduction" would be) rather than "CHAPTER I" being
        # silently dropped and "INTRODUCTION" alone becoming the heading.
        self.assertEqual(sections[0]["heading"], "INTRODUCTION")
        self.assertEqual(sections[0]["numbering"], "1")
        self.assertEqual(sections[0]["canonical_section"], "Introduction")
        self.assertEqual(sections[0]["content"], "Introduction body text.")

    def test_multi_word_ordinal_date_fragment_is_not_promoted_to_a_heading(self):
        """A page-position typography accident: an ordinal date rendered
        with the day number and its suffix as two separate text runs (e.g.
        "13" then "th April, 2023") must not have the suffix fragment
        accepted as a section heading just because it happens to be bold,
        large, and capitalized."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "CERTIFICATE OF APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "DATE OF APPROVAL:", HEADING_FONT)
            _add_block(page, (60, 190, 535, 220), "th April, 2023", HEADING_FONT)

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Real introduction body text.")

        job = self._make_job(build_pdf([cover, approval, chapter]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        headings = [s["heading"] for s in sections]
        self.assertEqual(headings, ["Introduction"])
        self.assertNotIn("th April, 2023", headings)

    def test_supervisor_sentence_context_name_does_not_absorb_trailing_department_text(self):
        """The captured name near a supervisor cue phrase must stop at the
        person's actual name -- not run on into an adjacent capitalized
        institutional phrase that happens to immediately follow it in the
        same sentence."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def acknowledgement(page):
            _add_block(page, (60, 60, 535, 90), "ACKNOWLEDGEMENT", HEADING_FONT)
            _add_block(
                page, (60, 120, 535, 220),
                "This project was completed under the supervision of Dr. Bikal Adhikari "
                "Department Of Electronics And Computer Engineering, whose guidance was invaluable.",
            )

        job = self._make_job(build_pdf([cover, acknowledgement]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Bikal Adhikari")

    def test_supervisor_sentence_context_rejects_pure_institutional_capture(self):
        """When no real name is actually present near the cue phrase and
        only capitalized institutional text follows the title token, no
        supervisor candidate should be produced at all -- a non-name must
        not be kept just because it was captured."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def acknowledgement(page):
            _add_block(page, (60, 60, 535, 90), "ACKNOWLEDGEMENT", HEADING_FONT)
            _add_block(
                page, (60, 120, 535, 220),
                "This project was completed under the supervision of Dr. Department Of "
                "Electronics, whose guidance was invaluable throughout.",
            )

        job = self._make_job(build_pdf([cover, acknowledgement]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(supervisors, [])

    def test_supervisor_blank_name_field_does_not_absorb_next_committee_members_label(self):
        """The exact reported real-world case: the source PDF's own
        Supervisor signature line was left blank (no name was ever typed
        in), so scanning forward from the "Supervisor:" label runs
        straight into the NEXT committee member's own label/block
        ("Project Co-ordinator: Er."). That block belongs to a different
        role and must never be captured as the supervisor's name -- the
        correct outcome here is no supervisor at all, not a wrong one."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "CERTIFICATE OF APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Supervisor:")
            _add_block(page, (60, 220, 535, 250), "External Examiner:")
            _add_block(page, (60, 290, 535, 320), "Project Co-ordinator:  Er.")
            _add_block(page, (60, 330, 535, 360), "Department of Electronics and Computer Engineering")
            _add_block(page, (60, 400, 535, 430), "Head of Department:  Er.")
            _add_block(page, (60, 440, 535, 470), "Department of Electronics and Computer Engineering")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        people = context["draft_metadata"]["people_and_roles"]

        # None of the committee-role labels/institutional lines should
        # ever be captured as a person's name for any role.
        for person in people:
            self.assertNotIn("Co-ordinator", person["full_name"])
            self.assertNotIn("Department", person["full_name"])

    def test_supervisory_label_on_title_page_is_not_promoted_to_a_section_heading(self):
        """A "Under the Supervision of" front-matter label -- common on
        title pages that combine the title, authors, and supervisor
        acknowledgement onto one page -- must never be mistaken for a
        chapter heading, even though it's short, capitalized, and often
        styled prominently just like a real one."""

        def cover(page):
            _add_block(page, (60, 60, 535, 120), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(page, (60, 400, 535, 430), "Under the Supervision of", HEADING_FONT)
            _add_block(page, (60, 440, 535, 470), "Dr. Ramesh Sharma")

        def chapter(page):
            _add_block(page, (60, 60, 535, 90), "1 Introduction", HEADING_FONT)
            _add_block(page, (60, 110, 535, 160), "Real introduction body text.")

        job = self._make_job(build_pdf([cover, chapter]))
        context = run_extraction_stages(job)
        sections = context["draft_metadata"]["project_sections"]

        headings = [s["heading"] for s in sections]
        self.assertNotIn("Under the Supervision of", headings)
        self.assertNotIn("under the supervision of", [h.lower() for h in headings])

    def test_supervisor_positional_fallback_name_and_designation_no_label(self):
        """No "Supervisor" label, no cue phrase anywhere -- just a name
        immediately followed by a designation line on the approval page,
        exactly the bare signature-block pattern real reports commonly
        use. Must still produce a (low-confidence) supervisor rather than
        none at all."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "CERTIFICATE OF APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Dr. Kabita Shrestha")
            _add_block(page, (60, 190, 535, 220), "Associate Professor")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Kabita Shrestha")
        self.assertEqual(supervisors[0]["confidence_source"], "positional_name_and_designation")
        self.assertLess(supervisors[0]["confidence"], 0.7)

    def test_positional_fallback_does_not_capture_a_role_label_as_the_name(self):
        """Regression for a real extraction seen in the repository: an
        approval page whose signature block prints the ROLE LABEL on one
        line and a designation on the next, with no name typed in at all.

        "External Examiner" satisfies the same capitalized-two-words shape
        a real name does, and the designation line beneath it used to
        complete the positional match -- so the project was published with
        a supervisor literally named "External Examiner". A role label must
        never become a person.
        """

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "CERTIFICATE OF APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "External Examiner")
            _add_block(page, (60, 190, 535, 220), "Assistant Professor")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        people = context["draft_metadata"]["people_and_roles"]
        names = [p["full_name"].lower() for p in people]

        self.assertNotIn("external examiner", names)
        for person in people:
            self.assertNotIn("examiner", person["full_name"].lower())
            self.assertNotIn("supervisor", person["full_name"].lower())

    def test_real_name_below_a_role_label_is_still_captured(self):
        """The guard above must reject only the label itself -- when the
        block does carry a real name under the label, that name is still
        extracted."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "CERTIFICATE OF APPROVAL", HEADING_FONT)
            _add_block(page, (60, 140, 535, 170), "Supervisor")
            _add_block(page, (60, 180, 535, 210), "Dr. Ramesh Bhattarai")
            _add_block(page, (60, 220, 535, 250), "Associate Professor")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        # The synthetic page is short enough that the sentence-context
        # detector also fires, so this asserts what the guard is actually
        # about: the real name survives, and no role label became a person.
        names = [p["full_name"] for p in supervisors]
        self.assertTrue(
            any("Ramesh Bhattarai" in name for name in names),
            f"expected the real name to be extracted, got {names}",
        )
        for name in names:
            self.assertNotIn("supervisor", name.lower())
            self.assertNotIn("examiner", name.lower())

    def test_supervisor_positional_fallback_named_only_in_thanks_with_no_cue(self):
        """A titled person thanked in acknowledgement prose with no
        "supervisor"/"guided by"/"advisor" wording attached to them at
        all. Weakest evidence in the pipeline -- still produces a
        supervisor candidate (at the lowest confidence) rather than
        nothing, since this is only ever tried as an absolute last resort
        when no other detector found anything."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def acknowledgement(page):
            _add_block(page, (60, 60, 535, 90), "ACKNOWLEDGEMENT", HEADING_FONT)
            _add_block(
                page, (60, 120, 535, 220),
                "We would like to thank Prof. Narayan Bhattarai for his continuous support "
                "throughout this project.",
            )

        job = self._make_job(build_pdf([cover, acknowledgement]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"]
            if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Narayan Bhattarai")
        self.assertEqual(supervisors[0]["confidence_source"], "positional_first_named_in_acknowledgement")
        self.assertLess(supervisors[0]["confidence"], 0.5)

    def test_batch_derived_from_author_roll_number_when_not_stated_explicitly(self):
        """No explicit "Batch" mention anywhere on the cover page -- the
        batch must be derived from a student author's roll number, in the
        3-digit format the rest of the system expects, not left null."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(page, (60, 200, 535, 260), "Aarav Shrestha (078BCT022)")
            _add_block(page, (60, 400, 535, 440), "Department of Computer Engineering\nPulchowk Campus")

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        self.assertEqual(context["draft_metadata"]["project_fields"]["batch"], "078")

    def test_batch_explicit_mention_is_preferred_over_roll_number(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(page, (60, 200, 535, 260), "Aarav Shrestha (079BCT022)")
            _add_block(page, (60, 300, 535, 330), "Batch: 078")

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        self.assertEqual(context["draft_metadata"]["project_fields"]["batch"], "078")

    def test_batch_stays_null_when_neither_explicit_mention_nor_roll_number_exists(self):
        """No roll numbers at all (e.g. a faculty project) and no explicit
        batch mention -- batch must stay null rather than guessing from an
        unrelated 4-digit calendar year, which would produce a value in
        the wrong format anyway."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
            _add_block(page, (60, 400, 535, 440), "Department of Computer Engineering\n2081")

        job = self._make_job(build_pdf([cover]))
        context = run_extraction_stages(job)
        self.assertIsNone(context["draft_metadata"]["project_fields"]["batch"])

    def test_supervisor_label_with_colon_is_recognized(self):
        """The exact reported bug: a "Supervisor:" label (with a colon) was
        being missed entirely because the old check required the line to
        equal the bare word "supervisor" with nothing else."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Supervisor:")
            _add_block(page, (60, 190, 535, 220), "Prof. Anita Rana")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"] if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Anita Rana")
        self.assertEqual(supervisors[0]["designation"], "Prof.")

    def test_supervisor_name_of_supervisor_label_variant_is_recognized(self):
        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def approval(page):
            _add_block(page, (60, 60, 535, 90), "APPROVAL", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Name of Supervisor:")
            _add_block(page, (60, 190, 535, 220), "Dr. Kamala Thapa")

        job = self._make_job(build_pdf([cover, approval]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"] if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Kamala Thapa")

    def test_supervisor_found_on_recommendation_page(self):
        """A "Letter of Recommendation" page (common in Nepali/IOE-style
        theses) must be classified the same way an approval page is, so its
        supervisor label is actually scanned."""

        def cover(page):
            _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})

        def recommendation(page):
            _add_block(page, (60, 60, 535, 90), "LETTER OF RECOMMENDATION", HEADING_FONT)
            _add_block(page, (60, 150, 535, 180), "Supervisor")
            _add_block(page, (60, 190, 535, 220), "Prof. Bina Karki")

        job = self._make_job(build_pdf([cover, recommendation]))
        context = run_extraction_stages(job)
        supervisors = [
            p for p in context["draft_metadata"]["people_and_roles"] if p["role"] == "Supervisor"
        ]

        self.assertEqual(len(supervisors), 1)
        self.assertEqual(supervisors[0]["full_name"], "Bina Karki")

    def test_working_and_previously_failing_layouts_side_by_side(self):
        """A single test exercising both a 'working' style document (chapter
        titles that happen to be in the alias table, explicit bare
        "Supervisor" label) and the previously-failing style (chapter titles
        outside the alias table, "Supervisor:" label with a colon), proving
        both now extract sections/authors/supervisors correctly."""

        def make_report(chapter_heading, supervisor_label):
            def cover(page):
                _add_block(page, (60, 60, 535, 130), "Sample Report Title", {"fontsize": 18, "fontname": "hebo"})
                _add_block(page, (60, 200, 535, 260),
                           "Aarav Shrestha (080BCT022)\nNischal Karki (079BCT047)")

            def approval(page):
                _add_block(page, (60, 60, 535, 90), "APPROVAL", HEADING_FONT)
                _add_block(page, (60, 150, 535, 180), supervisor_label)
                _add_block(page, (60, 190, 535, 220), "Dr. Ramesh Sharma")

            def content(page):
                _add_block(page, (60, 60, 535, 90), chapter_heading, HEADING_FONT)
                _add_block(page, (60, 110, 535, 160), "Chapter body text.")

            return build_pdf([cover, approval, content])

        working_pdf = make_report("1 Introduction", "Supervisor")
        previously_failing_pdf = make_report("1 Novel Contribution Summary", "Supervisor:")

        for label, pdf_bytes in [("working", working_pdf), ("previously_failing", previously_failing_pdf)]:
            job = self._make_job(pdf_bytes, filename=f"{label}.pdf")
            context = run_extraction_stages(job)
            draft = context["draft_metadata"]

            self.assertTrue(draft["project_sections"], f"{label}: sections should not be empty")
            self.assertTrue(
                [p for p in draft["people_and_roles"] if p["role"] == "Author"],
                f"{label}: authors should not be empty",
            )
            self.assertTrue(
                [p for p in draft["people_and_roles"] if p["role"] == "Supervisor"],
                f"{label}: supervisor should not be empty",
            )
