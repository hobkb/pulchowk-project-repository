"""
The Table of Contents as the authoritative section outline.

The failure these exist for: a numbered list inside a subsection was being
promoted to sibling subsections. "4.4.1 Functional Requirements" containing
items "1. 2. 3. 4." produced 4.4.2, 4.4.3, 4.4.4 -- silently overwriting the
real 4.4.2, and destroying the hierarchy that semantic search and RAG
retrieval depend on. Nothing typographic separates a bold numbered list item
from a bold numbered heading; the ToC does, because only one of them is
listed in it.
"""

from django.test import SimpleTestCase

from ingestion.pipeline.utils.section_tree import build_section_tree
from ingestion.pipeline.utils.toc_outline import (
    TocOutline,
    parse_toc_outline,
    split_numbered_heading,
)


def heading(text, size=13):
    return {"text": text, "is_bold": True, "font_size": size}


def body(text):
    return {"text": text, "is_bold": False, "font_size": 10}


def toc_page(rows, page_number=5):
    lines = [heading("Table of Contents", 16)]
    lines += [body(row) for row in rows]
    return {"page_number": page_number, "page_type": "toc", "lines": lines}


def content_page(lines, page_number=10):
    return {"page_number": page_number, "page_type": "content", "lines": lines}


def flatten(nodes, depth=1, out=None):
    """[(heading, depth)] for the whole tree, in document order."""
    if out is None:
        out = []
    for node in nodes:
        out.append((node["heading"], depth))
        flatten(node["children"], depth + 1, out)
    return out


# The ToC shape the user supplied, trimmed to the part that matters.
REPORT_TOC = [
    "Acknowledgements ii",
    "Abstract iii",
    "Contents vii",
    "List of Figures viii",
    "1 Introduction 1",
    "1.1 Background . . . . . . . . . . . . 1",
    "1.2 Problem statements . . . . . . . . 1",
    "4 Experimental Setup 23",
    "4.4 Backend Development . . . . . . . 31",
    "4.4.1 Functional Requirements . . . . 31",
    "4.4.2 Swagger UI . . . . . . . . . . . 31",
    "4.5 Version Control . . . . . . . . . . 32",
]


class ParseTocOutlineTests(SimpleTestCase):
    def test_only_numbered_entries_become_outline_entries(self):
        entries = parse_toc_outline([toc_page(REPORT_TOC)])
        numbers = [e["numbering"] for e in entries]

        self.assertIn((1,), numbers)
        self.assertIn((4, 4, 1), numbers)
        # Front matter is unnumbered, so it is absent without a special case.
        self.assertEqual(len(entries), 8)

    def test_the_outline_starts_at_the_first_numbered_chapter(self):
        entries = parse_toc_outline([toc_page(REPORT_TOC)])
        self.assertEqual(entries[0]["numbering"], (1,))
        self.assertEqual(entries[0]["title"], "Introduction")

    def test_depth_comes_from_the_numbering(self):
        entries = {e["numbering"]: e for e in parse_toc_outline([toc_page(REPORT_TOC)])}
        self.assertEqual(entries[(1,)]["depth"], 1)
        self.assertEqual(entries[(1, 1)]["depth"], 2)
        self.assertEqual(entries[(4, 4, 1)]["depth"], 3)

    def test_the_page_number_is_captured(self):
        entries = {e["numbering"]: e for e in parse_toc_outline([toc_page(REPORT_TOC)])}
        self.assertEqual(entries[(4, 5)]["page"], 32)

    def test_a_title_wrapped_across_two_lines_is_rejoined(self):
        entries = parse_toc_outline([toc_page([
            "2 Literature Review 3",
            "2.1.3 Automatic Building Detection based on Supervised Classification using",
            "High Resolution Google Earth Images . . . . . . 4",
            "2.2 Related theory . . . . . . . 5",
        ])])
        by_number = {e["numbering"]: e for e in entries}
        self.assertIn("High Resolution", by_number[(2, 1, 3)]["title"])
        self.assertEqual(by_number[(2, 1, 3)]["page"], 4)
        # The wrap must not swallow the row that follows it.
        self.assertIn((2, 2), by_number)

    def test_a_toc_running_onto_a_second_page_is_still_read(self):
        """Page classification only recognises the ToC by its title line."""
        first = toc_page(["1 Introduction . . . . . 1", "1.1 Background . . . . . 1"], 5)
        # The continuation reverts to "content" because its rows look like
        # chapter starts -- it must still be picked up.
        second = {
            "page_number": 6,
            "page_type": "content",
            "lines": [
                body("4 Experimental Setup . . . . . 23"),
                body("4.4 Backend Development . . . . . 31"),
                body("4.5 Version Control . . . . . 32"),
            ],
        }
        entries = parse_toc_outline([first, second])
        self.assertIn((4, 5), [e["numbering"] for e in entries])

    def test_no_toc_yields_no_outline(self):
        self.assertEqual(parse_toc_outline([content_page([heading("1 Introduction")])]), [])


class TocOutlineMatchingTests(SimpleTestCase):
    def setUp(self):
        self.outline = TocOutline(parse_toc_outline([toc_page(REPORT_TOC)]))

    def test_a_real_heading_matches_its_row(self):
        numbering, title = split_numbered_heading("4.4.1 Functional Requirements")
        self.assertIsNotNone(self.outline.match(numbering, title))

    def test_a_numbered_list_item_does_not_match_a_chapter(self):
        """The whole point: list item "1." is not chapter "1 Introduction"."""
        numbering, title = split_numbered_heading("1. The system shall allow user login")
        self.assertIsNone(self.outline.match(numbering, title))

    def test_a_heading_absent_from_the_toc_never_matches(self):
        numbering, title = split_numbered_heading("9.9 Invented Section")
        self.assertIsNone(self.outline.match(numbering, title))

    def test_each_entry_is_claimed_only_once(self):
        """A running header repeating a heading is not a second section."""
        numbering, title = split_numbered_heading("4.4.1 Functional Requirements")
        self.assertIsNotNone(self.outline.match(numbering, title))
        self.assertIsNone(self.outline.match(numbering, title))

    def test_a_chapter_word_prefix_still_finds_its_row(self):
        numbering, title = split_numbered_heading("Chapter 1 Introduction")
        self.assertIsNotNone(self.outline.match(numbering, title))

    def test_case_and_punctuation_differences_are_tolerated(self):
        numbering, title = split_numbered_heading("4.4.1  FUNCTIONAL REQUIREMENTS:")
        self.assertIsNotNone(self.outline.match(numbering, title))

    def test_a_short_toc_is_not_treated_as_authoritative(self):
        outline = TocOutline(parse_toc_outline([toc_page(["1 Introduction 1"])]))
        self.assertFalse(outline.is_authoritative)


class TocDrivenSectionTreeTests(SimpleTestCase):
    """End to end: the reported bug, through the real tree builder."""

    def _pages(self):
        return [
            toc_page(REPORT_TOC, page_number=5),
            content_page([
                heading("4.4 Backend Development", 14),
                body("The backend is built as described below."),
                heading("4.4.1 Functional Requirements", 13),
                body("The system must satisfy the following:"),
                # The list that used to become 4.4.2, 4.4.3, 4.4.4.
                heading("1. The system shall allow user login"),
                heading("2. The system shall store project reports"),
                heading("3. The system shall support search"),
                heading("4. The system shall export records"),
                heading("4.4.2 Swagger UI", 13),
                body("Interactive API documentation is served."),
                heading("4.5 Version Control", 14),
                body("Git is used throughout."),
            ], page_number=31),
        ]

    def test_a_numbered_list_does_not_become_sections(self):
        tree = build_section_tree(self._pages())
        headings = [h for h, _ in flatten(tree)]

        for item in ["The system shall allow user login",
                     "The system shall store project reports",
                     "The system shall support search",
                     "The system shall export records"]:
            self.assertNotIn(item, headings)

    def test_the_list_stays_as_content_of_its_own_subsection(self):
        tree = build_section_tree(self._pages())
        flat = {h: n for h, n in _walk(tree)}
        content = flat["Functional Requirements"]["content"]

        self.assertIn("The system shall allow user login", content)
        self.assertIn("The system shall export records", content)

    def test_the_real_next_subsection_survives_at_the_right_depth(self):
        tree = build_section_tree(self._pages())
        self.assertEqual(
            flatten(tree),
            [
                # Chapter 4 is retained as the parent the ToC says it is,
                # even though its heading is not on this page -- otherwise
                # 4.4 and 4.5 would float at the root.
                ("Experimental Setup", 1),
                ("Backend Development", 2),
                ("Functional Requirements", 3),
                ("Swagger UI", 3),
                ("Version Control", 2),
            ],
        )

    def test_headings_carry_a_marker_saying_the_toc_decided_them(self):
        tree = build_section_tree(self._pages())
        self.assertTrue(tree[0]["signals"].get("from_toc"))


def _walk(nodes, out=None):
    if out is None:
        out = []
    for node in nodes:
        out.append((node["heading"], node))
        _walk(node["children"], out)
    return out


class FallbackWithoutTocTests(SimpleTestCase):
    """A report with no usable ToC keeps the previous typographic behaviour
    rather than losing its sections entirely."""

    def test_sections_are_still_found_without_a_toc(self):
        tree = build_section_tree([
            content_page([
                heading("1 Introduction", 14),
                body("Opening context for the report goes here."),
                heading("1.1 Background", 13),
                body("Background details for the report go here."),
                heading("2 Methodology", 14),
                body("Method details for the report go here."),
            ])
        ])
        self.assertEqual(
            flatten(tree),
            [
                ("Introduction", 1),
                ("Background", 2),
                ("Methodology", 1),
            ],
        )


class UnnumberedChapterUnderTocTests(SimpleTestCase):
    """
    A chapter the report leaves unnumbered ("Conclusion") is still listed
    in the ToC, so it still becomes a section. Front matter is excluded not
    because it is unnumbered but because it sits above the first numbered
    row, which is what makes the outline start at "1 Introduction".
    """

    def test_an_unnumbered_chapter_listed_in_the_toc_becomes_a_section(self):
        tree = build_section_tree([
            toc_page(REPORT_TOC + ["Conclusion . . . . . . . 48"], page_number=5),
            content_page([
                heading("4.4 Backend Development", 14),
                body("The backend is described here in some detail."),
                heading("Conclusion", 15),
                body("The project met its stated objectives overall."),
            ], page_number=31),
        ])
        headings = [h for h, _ in flatten(tree)]
        self.assertIn("Conclusion", headings)

    def test_a_numbered_list_item_is_still_not_readmitted(self):
        """The safety net must not undo the fix it sits beside."""
        tree = build_section_tree([
            toc_page(REPORT_TOC, page_number=5),
            content_page([
                heading("4.4.1 Functional Requirements", 13),
                body("The system must satisfy the following requirements:"),
                heading("1. The system shall allow user login"),
                heading("2. The system shall store project reports"),
            ], page_number=31),
        ])
        headings = [h for h, _ in flatten(tree)]
        self.assertNotIn("The system shall allow user login", headings)
        self.assertNotIn("The system shall store project reports", headings)


class HeadingsPrintedWithoutNumbersTests(SimpleTestCase):
    """
    Many reports set a heading in a large face and leave its number to the
    ToC alone. Matching on numbering only found nothing in such a document,
    and every real subsection was swallowed into the chapter above it.
    """

    def _pages(self):
        toc_rows = [
            "5 Implementation . . . . 22",
            "5.1 Backend Development . . . . 22",
            "5.2 Frontend Development . . . . 24",
            "5.3 Data Preparation and Preprocessing . . . . 26",
            "5.3.1 Data Collection . . . . 26",
            "5.3.2 Data Cleaning . . . . 27",
        ]
        return [
            toc_page(toc_rows, page_number=4),
            content_page([
                heading("Implementation", 16),
                body("The implementation proceeds in several stages."),
                heading("Backend Development", 14),
                body("Records are stored in a structured format."),
                # Absent from the ToC -- must stay as content.
                heading("Index Building", 13),
                body("The index is built from the generated embeddings."),
                heading("Frontend Development", 14),
                body("The interface is a single page application."),
                heading("Data Collection", 13),
                body("Source documents are gathered from public archives."),
            ], page_number=22),
        ]

    def test_unnumbered_headings_are_matched_by_title(self):
        tree = build_section_tree(self._pages())
        headings = [h for h, _ in flatten(tree)]
        self.assertIn("Backend Development", headings)
        self.assertIn("Frontend Development", headings)

    def test_depth_still_comes_from_the_toc(self):
        tree = build_section_tree(self._pages())
        depths = dict((h, d) for h, d in flatten(tree))
        self.assertEqual(depths["Implementation"], 1)
        self.assertEqual(depths["Backend Development"], 2)
        self.assertEqual(depths["Data Collection"], 3)

    def test_a_heading_absent_from_the_toc_is_still_excluded(self):
        tree = build_section_tree(self._pages())
        self.assertNotIn("Index Building", [h for h, _ in flatten(tree)])

    def test_ordinary_body_text_matching_a_toc_title_is_not_promoted(self):
        """Title-only matching requires the line to look like a heading."""
        pages = [
            toc_page([
                "5 Implementation . . . . 22",
                "5.1 Backend Development . . . . 22",
                "5.2 Frontend Development . . . . 24",
                "5.3 Testing . . . . 26",
                "5.4 Deployment . . . . 28",
            ], page_number=4),
            content_page([
                heading("Implementation", 16),
                # Same words, but plain body type -- a sentence, not a heading.
                body("Backend Development"),
                body("continued across the following pages of the report."),
            ], page_number=22),
        ]
        self.assertNotIn("Backend Development", [h for h, _ in flatten(build_section_tree(pages))])


class MissingIntermediateHeadingTests(SimpleTestCase):
    """
    The reported failure: "5.3.4 FAISS Indexing" appeared as a child of
    "5.1 Backend Development". Its own subsection heading (5.3) was never
    found on the page, so the old body-driven builder attached it to
    whichever section happened to be open. The ToC plainly said otherwise.
    """

    TOC = [
        "5 Implementation . . . . 22",
        "5.1 Backend Development . . . . 22",
        "5.2 Frontend Development . . . . 24",
        "5.3 Data Preparation and Preprocessing . . . . 26",
        "5.3.1 Data Collection . . . . 26",
        "5.3.2 Data Cleaning . . . . 27",
        "5.3.4 FAISS Indexing . . . . 29",
    ]

    def _tree(self):
        return build_section_tree([
            toc_page(self.TOC, page_number=4),
            content_page([
                heading("Implementation", 16),
                body("The implementation proceeds in several stages."),
                heading("Backend Development", 14),
                body("Records are stored in a structured format."),
                # 5.3 itself is never seen on the page.
                heading("Data Collection", 13),
                body("Source documents are gathered from public archives."),
                heading("FAISS Indexing", 13),
                body("The index is built from the generated embeddings."),
            ], page_number=22),
        ])

    def test_a_subsection_attaches_to_the_parent_the_toc_names(self):
        parents = {}

        def walk(nodes, parent=None):
            for node in nodes:
                parents[node["heading"]] = parent
                walk(node["children"], node["heading"])

        walk(self._tree())
        self.assertEqual(parents["FAISS Indexing"], "Data Preparation and Preprocessing")
        self.assertNotEqual(parents["FAISS Indexing"], "Backend Development")

    def test_the_unseen_intermediate_parent_is_retained(self):
        headings = [h for h, _ in flatten(self._tree())]
        self.assertIn("Data Preparation and Preprocessing", headings)

    def test_a_toc_entry_absent_from_the_body_is_dropped(self):
        """5.2 is in the ToC but nowhere in this extract -- an empty card
        for it would be noise, and it has no children to keep it alive."""
        self.assertNotIn("Frontend Development", [h for h, _ in flatten(self._tree())])

    def test_no_depth_is_invented_between_siblings(self):
        depths = dict(flatten(self._tree()))
        self.assertEqual(depths["Backend Development"], 2)
        self.assertEqual(depths["Data Preparation and Preprocessing"], 2)
        self.assertEqual(depths["Data Collection"], 3)
        self.assertEqual(depths["FAISS Indexing"], 3)


class TocTitleCleanlinessTests(SimpleTestCase):
    """
    A ToC row's page number must never end up inside the section heading.
    Layout extraction often puts it on its own line when the dot leader is
    wide, which was being treated as a wrapped title and produced headings
    reading "Backend Development 12".
    """

    def _titles(self, rows):
        return {e["numbering"]: e["title"] for e in parse_toc_outline([toc_page(rows)])}

    def test_a_page_number_on_its_own_line_completes_the_row(self):
        titles = self._titles([
            "5.1 Backend Development . . . . . . . . . .", "12",
            "5.2 Frontend Development . . . . . . . . . .", "14",
            "5.3 Data Preparation and Preprocessing . . .", "15",
            "6 Results . . . . 20", "7 Conclusion . . . . 25",
        ])
        self.assertEqual(titles[(5, 1)], "Backend Development")
        self.assertEqual(titles[(5, 2)], "Frontend Development")
        self.assertEqual(titles[(5, 3)], "Data Preparation and Preprocessing")

    def test_the_page_number_is_still_captured_when_split_off(self):
        entries = {e["numbering"]: e for e in parse_toc_outline([toc_page([
            "5.1 Backend Development . . . . . .", "12",
            "5.2 Frontend Development . . . . . .", "14",
            "6 Results . . . . 20", "7 Conclusion . . . . 25",
            "8 Future Work . . . . 30",
        ])])}
        self.assertEqual(entries[(5, 1)]["page"], 12)

    def test_unicode_leaders_are_stripped(self):
        titles = self._titles([
            "1.3 Objectives ……… 1",
            "1.4 Scope · · · · 2",
            "2 Literature Review . . . . 3",
            "3 Methodology . . . . 5",
            "4 Results . . . . 8",
        ])
        self.assertEqual(titles[(1, 3)], "Objectives")
        self.assertEqual(titles[(1, 4)], "Scope")

    def test_a_title_ending_in_a_real_number_is_not_truncated_wrongly(self):
        """A page reference is stripped; a title's own trailing token is
        only lost when it is genuinely a bare number, which is the same
        shape a page reference has -- documented rather than silently odd."""
        titles = self._titles([
            "2.2.6 Global Positioning System(GPS) . . . . 12",
            "2.2.7 Vector Stores . . . . 13",
            "3 Methodology . . . . 15",
            "4 Results . . . . 20",
            "5 Conclusion . . . . 25",
        ])
        self.assertEqual(titles[(2, 2, 6)], "Global Positioning System(GPS)")


class MultiPageTocFooterTests(SimpleTestCase):
    """
    A ToC spanning several pages carries a roman-numeral footer on each
    ("iv", "v", "vi"). Those are the contents pages' own page numbers, not
    entries -- one became a top-level section titled "vi" that adopted the
    chapters following it.
    """

    ROWS = [
        "1 Introduction 1",
        "1.1 Background . . . . 1",
        "2 Literature Review . . . . 3",
        "iv",
        "3 Methodology . . . . 13",
        "3.7 Deployment . . . . 20",
        "3.8 Challenges and Limitations . . . . 21",
        "v",
        "4 Experimental Setup . . . . 23",
        "4.1 Hardware Requirements . . . . 23",
        "4.2 Software Environment . . . . 24",
        "vi",
        "8 Limitations and Future enhancement . . . . 50",
    ]

    def test_a_roman_footer_never_becomes_an_entry(self):
        titles = [e["title"] for e in parse_toc_outline([toc_page(self.ROWS)])]
        for footer in ("iv", "v", "vi"):
            self.assertNotIn(footer, titles)

    def test_chapters_keep_their_toc_order_across_page_breaks(self):
        numbers = [e["numbering"] for e in parse_toc_outline([toc_page(self.ROWS)])
                   if e["numbering"] and len(e["numbering"]) == 1]
        self.assertEqual(numbers, [(1,), (2,), (3,), (4,), (8,)])

    def test_a_footer_does_not_steal_the_chapters_after_it(self):
        """The tree must put 4 at the root, not inside a phantom section."""
        tree = build_section_tree([
            toc_page(self.ROWS, page_number=6),
            content_page([
                heading("Challenges and Limitations", 13),
                body("Several limitations were encountered during development."),
                heading("Experimental Setup", 16),
                body("The experiments were run on the hardware described below."),
                heading("Hardware Requirements", 13),
                body("A workstation with a discrete graphics card was used."),
            ], page_number=21),
        ])
        top_level = [node["heading"] for node in tree]
        self.assertIn("Experimental Setup", top_level)
        self.assertNotIn("vi", top_level)

    def test_a_split_roman_page_reference_still_completes_its_row(self):
        entries = {e["numbering"]: e for e in parse_toc_outline([toc_page([
            "1 Introduction . . . . . . . . . .", "iv",
            "2 Literature Review . . . . 3",
            "3 Methodology . . . . 5",
            "4 Results . . . . 8",
            "5 Conclusion . . . . 12",
        ])])}
        self.assertEqual(entries[(1,)]["title"], "Introduction")


class MergedPageRefAndFooterTests(SimpleTestCase):
    """
    Layout reconstruction merges a row's page number with the ToC page's
    own footer into a single line -- "8 vi". That parses as chapter 8
    titled "vi", which became a top-level section and adopted every
    chapter after it, so the document jumped from 3.8 straight to a
    phantom chapter and only then reached 4.
    """

    ROWS = [
        "1 Introduction 1",
        "2 Literature Review . . . . 3",
        "3 Methodology . . . . 5",
        "3.7 Deployment . . . . 20",
        "3.8 Challenges and Limitations . . . . .",
        "8 vi",                                  # page 8, then footer "vi"
        "4 Experimental Setup . . . . 23",
        "4.1 Hardware Requirements . . . . 23",
        "4.2 Software Environment . . . . 24",
    ]

    def test_a_merged_page_ref_and_footer_is_not_a_chapter(self):
        entries = parse_toc_outline([toc_page(self.ROWS)])
        self.assertNotIn("vi", [e["title"] for e in entries])

    def test_it_completes_the_row_it_belongs_to(self):
        entries = {e["numbering"]: e for e in parse_toc_outline([toc_page(self.ROWS)])}
        self.assertEqual(entries[(3, 8)]["title"], "Challenges and Limitations")
        self.assertEqual(entries[(3, 8)]["page"], 8)

    def test_the_chapter_after_it_stays_at_the_top_level(self):
        entries = parse_toc_outline([toc_page(self.ROWS)])
        chapters = [e["numbering"] for e in entries if e["numbering"] and len(e["numbering"]) == 1]
        self.assertEqual(chapters, [(1,), (2,), (3,), (4,)])

    def test_no_entry_is_ever_titled_only_a_page_reference(self):
        entries = parse_toc_outline([toc_page(self.ROWS + ["9 42", "iv"])])
        for entry in entries:
            self.assertFalse(
                entry["title"].strip().isdigit(),
                "an entry was titled with a bare number",
            )
