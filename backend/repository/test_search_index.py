

from django.test import TestCase

from repository.models import Keyword, Project, ProjectKeyword
from repository.search_index import _expressions, lexical_queryset


class SearchIndexTestBase(TestCase):
    def make_project(self, title, abstract="", keywords=(),
                     status="Published"):
        project = Project.objects.create(
            title=title,
            abstract=abstract,
            project_type="Major",
            academic_level="UG",
            status=status,
        )
        for name in keywords:
            keyword, _ = Keyword.objects.get_or_create(name=name)
            ProjectKeyword.objects.create(project=project, keyword=keyword)
        project.refresh_from_db()
        from repository.search_index import update_search_vector

        update_search_vector(project)
        return project

    def published(self):
        return Project.objects.filter(status="Published")

    def ranked(self, text):
        return list(lexical_queryset(self.published(), text).values_list(
            "id", flat=True
        ))


class RarityWeightedRankingTests(SearchIndexTestBase):
    """A common query term must not carry the same authority as a rare one."""

    def setUp(self):
        # "platform" now describes most of the corpus; "sentiment" describes
        # almost none of it.
        for index in range(20):
            self.make_project(
                "Filler %d platform" % index,
                abstract="A platform assembled for coursework.",
            )

    def test_the_rare_term_decides_the_order(self):
        """Both projects match both terms, so the difference is only which
        term each one puts in its title. The distinctive term is the one that
        expresses what the reader was looking for, so the project titled by it
        must come first."""
        common_in_title = self.make_project(
            "A platform for review collection",
            abstract="Sentiment is derived from the collected reviews.",
        )
        rare_in_title = self.make_project(
            "Sentiment scoring of written reviews",
            abstract="Delivered as a platform for coursework.",
        )
        order = self.ranked("sentiment platform")
        self.assertEqual(order[0], rare_in_title.pk)
        self.assertIn(common_in_title.pk, order)

    def test_both_terms_are_still_required(self):
        """Weighting changes the order, not the result set: a project holding
        only the common term is not a match for a two-term query."""
        only_common = self.make_project("A platform for scheduling")
        self.assertNotIn(only_common.pk, self.ranked("sentiment platform"))

    def test_a_ubiquitous_term_still_contributes(self):
        """Its weight is floored rather than zeroed, so it does not silently
        stop being part of the query."""
        self.assertTrue(self.ranked("platform"))


class PrefixExpansionTests(SearchIndexTestBase):
    """`term:*` is for an unfinished word, not for every word."""

    def setUp(self):
        self.exact = self.make_project("Systems engineering practice")
        self.longer = self.make_project("Systematic review methodology")

    def test_a_complete_word_is_not_expanded(self):
        """The search box no longer searches as the reader types, so the final
        term is normally a word they have finished. Expanding it anyway only
        widens the query: "system" would drag in "systematic" for no gain."""
        expressions, _counts, _corpus = _expressions("system")
        self.assertEqual([e for e, _df in expressions], ["system"])
        self.assertNotIn(self.longer.pk, self.ranked("system"))

    def test_an_unfinished_word_is_expanded(self):
        """Which is what keeps partial-word searching working -- the case a
        prefix actually exists for."""
        expressions, _counts, _corpus = _expressions("systema")
        self.assertEqual([e for e, _df in expressions], ["systema:*"])
        self.assertIn(self.longer.pk, self.ranked("systema"))

    def test_only_the_final_term_is_ever_expanded(self):
        expressions, _counts, _corpus = _expressions("systema review")
        self.assertEqual([e for e, _df in expressions][0], "systema")

    def test_a_term_matching_nothing_at_all_matches_nothing(self):
        """A prefix is a fallback for an incomplete word, not a way to make
        every failed query return something."""
        self.assertEqual(self.ranked("zzzznonexistentterm"), [])

    def test_an_empty_query_matches_nothing(self):
        self.assertEqual(self.ranked("   "), [])

    def test_tsquery_operators_in_the_box_do_not_raise(self):
        """Ordinary typing can contain a colon or a bracket, and it must not
        reach the parser as syntax."""
        for text in ["a:b", "(cats", "one & two", "!", "'quoted'"]:
            with self.subTest(text=text):
                self.ranked(text)
