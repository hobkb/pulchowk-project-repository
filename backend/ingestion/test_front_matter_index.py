"""
Preliminary-pages index titles ("List of Figures", "List of Tables", ...)
must never become sections, no matter where in the document they appear
or how they are phrased.
"""

from django.test import SimpleTestCase

from ingestion.pipeline.utils.heading_scoring import (
    looks_like_front_matter_index,
    score_heading_candidate,
)


def line(text, *, font_size=16.0, is_bold=True, line_number=0):
    return {"text": text, "font_size": font_size, "is_bold": is_bold, "line_number": line_number}


class FrontMatterIndexDetectionTests(SimpleTestCase):
    def test_common_titles_are_recognised(self):
        for text in [
            "List of Figures", "LIST OF FIGURES", "List of Tables",
            "Table of Contents", "Contents", "List of Abbreviations",
            "List of Acronyms", "List of Symbols", "Index",
        ]:
            self.assertTrue(looks_like_front_matter_index(text), text)

    def test_a_combined_title_is_recognised(self):
        self.assertTrue(looks_like_front_matter_index("List of Figures and Tables"))
        self.assertTrue(looks_like_front_matter_index("List of Tables & Figures"))

    def test_a_dot_leader_or_page_number_tail_does_not_hide_the_title(self):
        self.assertTrue(looks_like_front_matter_index("List of Figures ....... iii"))
        self.assertTrue(looks_like_front_matter_index("List of Tables................12"))

    def test_a_real_chapter_heading_is_not_flagged(self):
        for text in ["Introduction", "1. Introduction", "1.1 Background",
                     "Methodology", "3. System Design"]:
            self.assertFalse(looks_like_front_matter_index(text), text)

    def test_a_figure_or_table_caption_is_not_flagged(self):
        """"Figure 3.1: ..." is a caption inside a chapter, not the index."""
        self.assertFalse(
            looks_like_front_matter_index("Figure 3.1: System Architecture")
        )
        self.assertFalse(
            looks_like_front_matter_index("Table 4.2 Results Summary")
        )


class ScoringRejectsFrontMatterIndexTests(SimpleTestCase):
    """The same guarantee as the artifact filter: never a heading,
    regardless of numbering, boldness, or font size."""

    def test_never_scored_as_a_heading_even_when_styled_like_one(self):
        for text in ["List of Figures", "List of Tables", "Table of Contents"]:
            candidate = score_heading_candidate(
                line(text, font_size=24.0, is_bold=True), body_font_size=12.0
            )
            self.assertIsNone(candidate, text)

    def test_still_rejected_when_numbered(self):
        candidate = score_heading_candidate(
            line("2. List of Figures", font_size=24.0, is_bold=True), body_font_size=12.0
        )
        self.assertIsNone(candidate)

    def test_a_real_numbered_heading_still_scores(self):
        candidate = score_heading_candidate(
            line("1. Introduction", font_size=24.0, is_bold=True), body_font_size=12.0
        )
        self.assertIsNotNone(candidate)
