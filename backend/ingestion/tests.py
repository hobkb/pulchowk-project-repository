from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ingestion.models import IngestionJob
from ingestion.pipeline.steps.page_classification import DocumentPageClassifier
from ingestion.pipeline.steps.metadata_sections import MetadataSectionsStep
from ingestion.pipeline.utils.text_cleaners import normalize_line
from organization.models import Campus, Department, ResearchGroup
from repository.models import Project


class JobPublishAPIViewTests(TestCase):
    def test_normalize_line_removes_nul_characters(self):
        self.assertEqual(normalize_line("LANCZOS\x00 kernel"), "LANCZOS kernel")

    def test_job_detail_returns_review_payload(self):
        user = User.objects.create_user(
            email="review@example.com", password="secret123", is_staff=True
        )
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="report.pdf",
            uploaded_by=user,
            status=IngestionJob.Status.EXTRACTED,
            extracted_payload={
                "project_fields": {"title": "Review Test"},
                "people_and_roles": [{"full_name": "Jane Doe", "role": "Author"}],
            },
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(reverse("ingestion:job-detail", args=[job.id]))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["people_and_roles"][0]["full_name"], "Jane Doe")

    def test_publish_creates_project_relationships_and_people(self):
        user = User.objects.create_user(
            email="user@example.com", password="secret123", is_staff=True
        )
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="report.pdf",
            uploaded_by=user,
            status=IngestionJob.Status.EXTRACTED,
            extracted_payload={
                "project_fields": {
                    "title": "AI for Healthcare",
                    "abstract": "A study on applying AI in healthcare.",
                    "project_type": "Thesis",
                    "academic_level": "Masters",
                    "batch": "2024",
                    "department_name": "Computer Engineering",
                    "campus_name": "Pulchowk Campus",
                    "research_group_name": "AI Lab",
                    "repository_url": "https://example.com/repo",
                    "language": "English",
                    "doi_url": "https://doi.org/10.1234/example",
                    "publication_url": "https://example.com/paper",
                },
                "people_and_roles": [
                    {
                        "full_name": "Alice Example",
                        "email": "alice@example.com",
                        "role": "Author",
                        "display_order": 1,
                    },
                    {
                        "full_name": "Bob Supervisor",
                        "email": "bob@example.com",
                        "role": "Supervisor",
                        "display_order": 2,
                    },
                ],
                "keywords": ["django", "machine learning"],
                "project_sections": [
                    {
                        "heading": "Introduction",
                        "canonical_section": "introduction",
                        "heading_level": 1,
                        "display_order": 1,
                        "content": "This is the introduction.",
                        "children": [
                            {
                                "heading": "Problem statement",
                                "canonical_section": "Problem statement",
                                "heading_level": 2,
                                "display_order": 2,
                                "content": "This is the problem statement.",
                            }
                        ],
                    }
                ],
                "references": [{"title": "References", "citation": "[1] Example reference"}],
                "appendices": [{"title": "Appendix A"}],
                "document_metadata": {"processing_time_ms": 100},
                "processing_warnings": ["minor warning"],
                "domains": ["Machine Learning"],
            },
        )

        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(reverse("ingestion:job-publish", args=[job.id]))

        self.assertEqual(response.status_code, 200, response.data)
        job.refresh_from_db()

        self.assertIsNotNone(job.published_project)
        project = job.published_project
        self.assertEqual(project.title, "AI for Healthcare")
        self.assertEqual(project.department.name, "Computer Engineering")
        self.assertEqual(project.research_group.name, "AI Lab")
        self.assertEqual(project.project_people.count(), 2)
        self.assertEqual(project.project_keywords.count(), 2)
        self.assertEqual(project.project_domains.count(), 1)
        self.assertEqual(project.sections.count(), 2)
        introduction = project.sections.get(heading="Introduction")
        subsection = project.sections.get(heading="Problem statement")
        self.assertIsNone(introduction.parent)
        self.assertEqual(subsection.parent, introduction)
        self.assertEqual(project.references.get().citation, "[1] Example reference")
        self.assertEqual(project.assets.count(), 1)
        self.assertEqual(project.status, "Published")
        self.assertEqual(job.status, IngestionJob.Status.VERIFIED)

    def test_flat_section_extraction_ignores_subheadings(self):
        pages = [
            {
                "page_number": 1,
                "page_type": "content",
                "lines": [
                    {"text": "1 Introduction", "is_bold": True, "font_size": 12},
                    {"text": "Opening context."},
                    {"text": "1.1 Background", "is_bold": True, "font_size": 12},
                    {"text": "Background details."},
                    {"text": "1.2 Motivation", "is_bold": True, "font_size": 12},
                    {"text": "Motivation details."},
                    {"text": "More introduction context."},
                    {"text": "2 Methodology", "is_bold": True, "font_size": 12},
                    {"text": "Method details."},
                    {"text": "References", "is_bold": True, "font_size": 12},
                    {"text": "[1] This must not be part of Methodology."},
                ],
            }
        ]

        sections = MetadataSectionsStep.extract_project_sections(pages)

        introduction, methodology = sections
        self.assertEqual(introduction["heading"], "Introduction")
        self.assertEqual(introduction["heading_level"], 1)
        self.assertEqual(introduction["display_order"], 1)
        self.assertNotIn("children", introduction)
        self.assertIn("Background details.", introduction["content"])
        self.assertIn("Motivation details.", introduction["content"])
        self.assertEqual(methodology["heading"], "Methodology")
        self.assertEqual(methodology["display_order"], 2)
        self.assertEqual(methodology["content"], "Method details.")
        self.assertEqual(methodology["word_count"], 2)

    def test_section_step_exposes_raw_references_for_publish(self):
        user = User.objects.create_user(email="references@example.com", password="secret123")
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="report.pdf",
            uploaded_by=user,
        )
        context = {
            "classified_pages": [
                {
                    "page_number": 1,
                    "page_type": "content",
                    "lines": [
                        {"text": "References", "is_bold": True, "font_size": 12},
                        {"text": "[1] A preserved citation."},
                    ],
                }
            ],
            "file_hash": "a" * 64,
        }

        result = MetadataSectionsStep().run(job, context)

        self.assertEqual(
            result["draft_metadata"]["references"],
            [{"title": "References", "citation": "References\n[1] A preserved citation."}],
        )
        self.assertNotIn("back_matter", result["draft_metadata"])

    def test_section_extraction_accepts_unnumbered_and_chapter_headings(self):
        pages = [
            {
                "page_number": 1,
                "page_type": "content",
                "lines": [
                    {"text": "CHAPTER I", "is_bold": True, "font_size": 14},
                    {"text": "INTRODUCTION", "is_bold": True, "font_size": 14},
                    {"text": "Introduction text."},
                    {"text": "CHAPTER 2: METHODOLOGY", "is_bold": True, "font_size": 14},
                    {"text": "Method text."},
                ],
            }
        ]

        sections = MetadataSectionsStep.extract_project_sections(pages)

        self.assertEqual([section["heading"] for section in sections], [
            "Introduction", "Methodology",
        ])
        self.assertEqual([section["content"] for section in sections], [
            "Introduction text.", "Method text.",
        ])

    def test_back_matter_is_not_returned_twice_or_added_as_a_section(self):
        pages = [
            {
                "page_number": 1,
                "page_type": "content",
                "lines": [
                    {"text": "1 Introduction", "is_bold": True, "font_size": 12},
                    {"text": "Body text."},
                    {"text": "6 References", "is_bold": True, "font_size": 12},
                    {"text": "[1] A citation."},
                    {"text": "Appendix A: Survey", "is_bold": True, "font_size": 12},
                    {"text": "Survey content."},
                ],
            }
        ]

        sections = MetadataSectionsStep.extract_project_sections(pages)
        back_matter = MetadataSectionsStep.extract_back_matter(pages)

        self.assertEqual([section["heading"] for section in sections], ["Introduction"])
        self.assertEqual(back_matter["references"]["content"], "6 References\n[1] A citation.")
        self.assertEqual(back_matter["appendices"], [{
            "title": "Appendix A: Survey",
            "page_start": 1,
            "page_end": 1,
            "content": "Appendix A: Survey\nSurvey content.",
        }])

    def test_toc_continuation_pages_are_not_promoted_to_content(self):
        pages = [
            {"lines": [{"text": "Cover"}]},
            {"lines": [{"text": "Table of Contents"}, {"text": "Introduction .... 1"}]},
            {"lines": [{"text": "Methodology .... 15"}, {"text": "References .... 39"}]},
            {"lines": [{"text": "Appendix A .... 45"}]},
            {"lines": [{"text": "List of Figures"}]},
            {"lines": [{"text": "1 Introduction"}]},
        ]

        classified = DocumentPageClassifier.classify(pages)

        self.assertEqual([page["page_type"] for page in classified], [
            "cover", "toc", "toc", "toc", "list_of_figures", "content",
        ])

    def test_toc_reference_row_does_not_stop_flat_section_extraction(self):
        pages = [
            {
                "page_number": 1,
                "page_type": "toc",
                "lines": [{"text": "Table of Contents"}],
            },
            {
                "page_number": 2,
                "page_type": "content",
                "lines": [
                    {"text": "39 References .... 39", "is_bold": True, "font_size": 14},
                ],
            },
            {
                "page_number": 3,
                "page_type": "content",
                "lines": [
                    {"text": "2 Methodology", "is_bold": True, "font_size": 14},
                    {"text": "Method body."},
                ],
            },
            {
                "page_number": 4,
                "page_type": "content",
                "lines": [
                    {"text": "3 Results", "is_bold": True, "font_size": 14},
                    {"text": "Results body."},
                ],
            },
        ]

        sections = MetadataSectionsStep.extract_project_sections(pages)

        self.assertEqual([section["heading"] for section in sections], ["Methodology", "Results"])
        self.assertEqual(sections[0]["content"], "Method body.")
        self.assertEqual(sections[1]["content"], "Results body.")
