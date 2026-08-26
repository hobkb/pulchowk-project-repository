
from django.test import SimpleTestCase

from repository.serializers import build_section_tree, numbering_depth


def rows(*pairs):
    """(heading, stored_level) pairs in document order."""
    return [
        {"heading": heading, "heading_level": level, "id": index}
        for index, (heading, level) in enumerate(pairs, start=1)
    ]


def shape(nodes):
    """The tree as (heading, [children]) tuples, for readable assertions."""
    return [(n["heading"], shape(n["children"])) for n in nodes]


class NumberingDepthTests(SimpleTestCase):
    def test_depth_comes_from_the_number_of_components(self):
        self.assertEqual(numbering_depth("1. Introduction"), 1)
        self.assertEqual(numbering_depth("1.2 Problem Statement"), 2)
        self.assertEqual(numbering_depth("1.1.1 Scope"), 3)
        self.assertEqual(numbering_depth("2.3.4.1 Detail"), 4)

    def test_unnumbered_headings_have_no_implied_depth(self):
        for heading in ("Abstract", "", None, "Conclusion"):
            self.assertIsNone(numbering_depth(heading), heading)

    def test_a_leading_year_does_parse_and_is_handled_by_the_threshold(self):
        """
        "2024 in review" is indistinguishable from a section number by
        shape alone, so the parser reports depth 1. What stops it
        restructuring a report is the rule that numbering is only trusted
        when most headings carry it -- see the tree tests below.
        """
        self.assertEqual(numbering_depth("2024 in review"), 1)


class BuildSectionTreeTests(SimpleTestCase):
    def test_a_third_level_heading_does_not_detach_the_next_subsection(self):
        """
        The reported bug: after 1.1.1 and 1.1.2, the heading 1.2 was
        recorded at level 1 by the font heuristic and became a chapter of
        its own, taking the rest of the document with it.
        """
        tree = build_section_tree(rows(
            ("1. Introduction", 1),
            ("1.1 Background", 2),
            ("1.1.1 History", 3),
            ("1.1.2 Prior Work", 3),
            ("1.2 Problem Statement", 1),   # wrong stored level
            ("1.3 Objectives", 1),          # wrong stored level
            ("2. Literature Review", 1),
        ))

        self.assertEqual(shape(tree), [
            ("1. Introduction", [
                ("1.1 Background", [
                    ("1.1.1 History", []),
                    ("1.1.2 Prior Work", []),
                ]),
                ("1.2 Problem Statement", []),
                ("1.3 Objectives", []),
            ]),
            ("2. Literature Review", []),
        ])

    def test_only_top_level_chapters_sit_at_the_root(self):
        tree = build_section_tree(rows(
            ("1. Introduction", 1),
            ("1.1 Background", 1),
            ("2. Methodology", 1),
            ("2.1 Dataset", 1),
            ("2.2 Model", 1),
        ))
        self.assertEqual([n["heading"] for n in tree],
                         ["1. Introduction", "2. Methodology"])
        self.assertEqual(len(tree[1]["children"]), 2)

    def test_an_unnumbered_document_still_uses_its_stored_levels(self):
        tree = build_section_tree(rows(
            ("Abstract", 1),
            ("Introduction", 1),
            ("Background", 2),
            ("Conclusion", 1),
        ))
        self.assertEqual(shape(tree), [
            ("Abstract", []),
            ("Introduction", [("Background", [])]),
            ("Conclusion", []),
        ])

    def test_one_stray_number_does_not_restructure_an_unnumbered_report(self):
        tree = build_section_tree(rows(
            ("Abstract", 1),
            ("Introduction", 1),
            ("2024 in review", 2),
            ("Conclusion", 1),
        ))
        self.assertEqual([n["heading"] for n in tree],
                         ["Abstract", "Introduction", "Conclusion"])

    def test_a_gap_in_levels_is_clamped_rather_than_dropping_a_section(self):
        tree = build_section_tree(rows(
            ("1. Introduction", 1),
            ("1.1.1 Orphaned Detail", 3),   # no 1.1 above it
        ))
        self.assertEqual(shape(tree),
                         [("1. Introduction", [("1.1.1 Orphaned Detail", [])])])

    def test_every_row_survives_the_rebuild(self):
        source = rows(
            ("1. A", 1), ("1.1 B", 2), ("1.1.1 C", 3), ("1.1.2 D", 3),
            ("1.2 E", 1), ("2. F", 1), ("2.1 G", 4), ("3. H", 1),
        )
        tree = build_section_tree(source)

        seen = []
        def walk(nodes):
            for node in nodes:
                seen.append(node["heading"])
                walk(node["children"])
        walk(tree)

        self.assertEqual(seen, [row["heading"] for row in source])

    def test_no_rows_gives_an_empty_tree(self):
        self.assertEqual(build_section_tree([]), [])
