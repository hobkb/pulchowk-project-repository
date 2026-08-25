"""Lexical, semantic and fused retrieval, plus Major/Minor filtering.

The embedding model is not loaded. Semantic ranking is exercised against
hand-built vectors and, where a query has to be encoded, `embed_query` is
stubbed, so these tests assert on fusion and filtering rather than on what a
neural network produces on a given day.
"""

import math
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from repository.evaluation import aggregate, evaluate_ranking
from repository.hybrid_search import (
    hybrid_ranking,
    lexical_ranking,
    reciprocal_rank_fusion,
    semantic_ranking,
)
from repository.models import Keyword, Project, ProjectEmbedding, ProjectKeyword
from repository.search_index import lexical_queryset, update_search_vector

MODEL_VERSION = "test-model-v1"
DIM = 384


def vector_at(angle):
    v = [0.0] * DIM
    v[0] = math.cos(angle)
    v[1] = math.sin(angle)
    return v


def vector_with_cosine(target):
    return vector_at(math.acos(max(-1.0, min(1.0, target))))


class SearchTestBase(TestCase):
    def make_project(self, title, abstract="", project_type="Major", keywords=()):
        project = Project.objects.create(
            title=title,
            abstract=abstract,
            project_type=project_type,
            academic_level="UG",
            status="Published",
        )
        for name in keywords:
            keyword, _ = Keyword.objects.get_or_create(name=name)
            ProjectKeyword.objects.create(project=project, keyword=keyword)
        project.refresh_from_db()
        update_search_vector(project)
        return project

    def embed(self, project, vector):
        ProjectEmbedding.objects.create(
            project=project,
            model_version=MODEL_VERSION,
            source_hash="x" * 64,
            embedding=vector,
        )

    def published(self):
        return Project.objects.filter(status="Published")


class LexicalSearchTests(SearchTestBase):
    """The full-text index that replaced the chained icontains search."""

    def setUp(self):
        self.solar = self.make_project(
            "Dual-axis solar tracker",
            abstract="A controller that orients photovoltaic panels toward the sun.",
            keywords=["solar", "embedded systems"],
        )
        self.vision = self.make_project(
            "Attendance system using face recognition",
            abstract="Deep learning models identify students from a camera feed.",
            keywords=["computer vision", "deep learning"],
        )
        self.traffic = self.make_project(
            "Traffic signal control with reinforcement learning",
            abstract="An agent learns signal timings in a simulated junction.",
            keywords=["reinforcement learning"],
        )

    def test_search_vector_is_populated(self):
        for project in Project.objects.all():
            self.assertIsNotNone(project.search_vector)

    def test_title_match(self):
        ids = list(lexical_queryset(self.published(), "solar tracker").values_list("id", flat=True))
        self.assertEqual(ids, [self.solar.pk])

    def test_abstract_match(self):
        ids = list(lexical_queryset(self.published(), "photovoltaic").values_list("id", flat=True))
        self.assertIn(self.solar.pk, ids)

    def test_keyword_match(self):
        ids = list(
            lexical_queryset(self.published(), "computer vision").values_list("id", flat=True)
        )
        self.assertIn(self.vision.pk, ids)

    def test_multi_term_query_does_not_explode(self):
        """Three terms used to produce a combinatorial join: 665,791 rows for
        21 projects, taking over a minute. The row count must now equal the
        number of matching projects."""
        queryset = lexical_queryset(self.published(), "deep learning models")
        self.assertEqual(queryset.count(), queryset.distinct().count())
        self.assertLessEqual(queryset.count(), Project.objects.count())

    def test_stemming_matches_inflections(self):
        ids = list(lexical_queryset(self.published(), "learn").values_list("id", flat=True))
        self.assertTrue(ids, "stemming should match 'learns' and 'learning'")

    def test_title_outranks_abstract(self):
        """Weight A over weight C: a project whose title carries the term
        should rank above one that only mentions it in the abstract."""
        ranked = list(
            lexical_queryset(self.published(), "reinforcement learning").values_list(
                "id", flat=True
            )
        )
        self.assertEqual(ranked[0], self.traffic.pk)

    def test_no_match_returns_nothing(self):
        ids = list(
            lexical_queryset(self.published(), "zzzznonexistentterm").values_list("id", flat=True)
        )
        self.assertEqual(ids, [])

    def test_index_follows_a_title_change(self):
        """The save signal keeps the vector current.

        The handler runs on commit, which a TestCase's wrapping transaction
        never reaches, so the callbacks are captured and executed explicitly.
        """
        with patch("repository.tasks.embed_project"):
            with self.captureOnCommitCallbacks(execute=True):
                self.solar.title = "Photovoltaic orientation controller"
                self.solar.save()

        ids = list(
            lexical_queryset(self.published(), "orientation controller").values_list(
                "id", flat=True
            )
        )
        self.assertIn(self.solar.pk, ids)

    def test_index_follows_a_keyword_change(self):
        keyword, _ = Keyword.objects.get_or_create(name="heliostat")
        with patch("repository.tasks.embed_project"):
            with self.captureOnCommitCallbacks(execute=True):
                ProjectKeyword.objects.create(project=self.solar, keyword=keyword)

        ids = list(lexical_queryset(self.published(), "heliostat").values_list("id", flat=True))
        self.assertIn(self.solar.pk, ids)

    def test_saving_a_project_queues_its_embedding(self):
        with patch("repository.tasks.embed_project") as task:
            with self.captureOnCommitCallbacks(execute=True):
                self.solar.abstract = "A revised abstract."
                self.solar.save()
        task.delay.assert_called_with(self.solar.pk)

    def test_a_broker_failure_does_not_break_saving(self):
        """Embedding is best-effort. A queue that is down leaves the project
        stale for the backfill command to repair, but must not make saving
        a project fail."""
        with patch("repository.tasks.embed_project") as task:
            task.delay.side_effect = RuntimeError("broker unavailable")
            with self.captureOnCommitCallbacks(execute=True):
                self.solar.abstract = "Another revision."
                self.solar.save()
        self.assertTrue(Project.objects.filter(pk=self.solar.pk).exists())


class FusionTests(TestCase):
    """Reciprocal rank fusion in isolation."""

    def test_agreement_reinforces(self):
        ordered, _ = reciprocal_rank_fusion(
            {"lexical": [1, 2, 3], "semantic": [1, 3, 2]}, k=60
        )
        self.assertEqual(ordered[0], 1)

    def test_a_document_in_one_branch_only_still_scores(self):
        ordered, _ = reciprocal_rank_fusion(
            {"lexical": [9], "semantic": [1, 2, 3]}, k=60
        )
        self.assertIn(9, ordered)

    def test_weights_shift_the_outcome(self):
        rankings = {"lexical": [1, 2], "semantic": [2, 1]}
        lexical_heavy, _ = reciprocal_rank_fusion(
            rankings, k=60, weights={"lexical": 3.0, "semantic": 1.0}
        )
        semantic_heavy, _ = reciprocal_rank_fusion(
            rankings, k=60, weights={"lexical": 1.0, "semantic": 3.0}
        )
        self.assertEqual(lexical_heavy[0], 1)
        self.assertEqual(semantic_heavy[0], 2)

    def test_contributions_record_each_branch_position(self):
        _, contributions = reciprocal_rank_fusion(
            {"lexical": [5], "semantic": [7, 5]}, k=60
        )
        self.assertEqual(contributions[5], {"lexical": 1, "semantic": 2})


class MetricTests(TestCase):
    def test_perfect_ranking(self):
        m = evaluate_ranking([1, 2, 3], {1}, k=10)
        self.assertEqual(m["p_at_1"], 1.0)
        self.assertEqual(m["reciprocal_rank"], 1.0)
        self.assertEqual(m["recall_at_k"], 1.0)
        self.assertEqual(m["ndcg_at_k"], 1.0)

    def test_relevant_document_lower_down(self):
        m = evaluate_ranking([9, 8, 1], {1}, k=10)
        self.assertEqual(m["p_at_1"], 0.0)
        self.assertAlmostEqual(m["reciprocal_rank"], 1 / 3)
        self.assertEqual(m["recall_at_k"], 1.0)

    def test_relevant_document_missing(self):
        m = evaluate_ranking([9, 8, 7], {1}, k=10)
        self.assertEqual(m["found"], 0.0)
        self.assertEqual(m["recall_at_k"], 0.0)
        self.assertEqual(m["ndcg_at_k"], 0.0)

    def test_aggregate_means(self):
        summary = aggregate([
            evaluate_ranking([1], {1}, k=10),
            evaluate_ranking([2], {1}, k=10),
        ])
        self.assertEqual(summary["queries"], 2)
        self.assertEqual(summary["p_at_1"], 0.5)


@override_settings(EMBEDDING={
    "MODEL_NAME": "test", "MODEL_VERSION": MODEL_VERSION, "DIMENSION": DIM,
    "QUERY_PREFIX": "q: ", "MAX_SEQ_LENGTH": 512, "BATCH_SIZE": 4, "NORMALIZE": True,
})
class SemanticAndHybridTests(SearchTestBase):
    def setUp(self):
        self.near = self.make_project("Alpha project", abstract="alpha text")
        self.mid = self.make_project("Beta project", abstract="beta text")
        self.far = self.make_project("Gamma project", abstract="gamma text")
        self.embed(self.near, vector_with_cosine(0.95))
        self.embed(self.mid, vector_with_cosine(0.80))
        self.embed(self.far, vector_with_cosine(0.50))

    def test_semantic_ranking_orders_by_cosine(self):
        """Ordering, and the candidacy floor.

        `far` sits at 0.50, below SEARCH["SEMANTIC_MIN_SCORE"], so it is not
        a candidate at all. That is the point of the floor: k-nearest-neighbour
        returns k results however unrelated they are, and over a small corpus
        that put most of the repository into every result set.
        """
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            ids = semantic_ranking(self.published(), "anything", 10, MODEL_VERSION)
        self.assertEqual(ids, [self.near.pk, self.mid.pk])
        self.assertNotIn(self.far.pk, ids)

        # With the floor lifted, the full ordering is still by cosine.
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            unfiltered = semantic_ranking(
                self.published(), "anything", 10, MODEL_VERSION, min_score=-1.0
            )
        self.assertEqual(unfiltered, [self.near.pk, self.mid.pk, self.far.pk])

    def test_semantic_ranking_respects_the_candidate_set(self):
        """Filters are applied before retrieval, so an excluded project must
        not occupy a candidate slot."""
        restricted = self.published().exclude(pk=self.near.pk)
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            ids = semantic_ranking(restricted, "anything", 10, MODEL_VERSION)
        self.assertNotIn(self.near.pk, ids)

    def test_hybrid_includes_lexical_only_and_semantic_only_matches(self):
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            ordered, branches = hybrid_ranking(
                self.published(), "Gamma", model_version=MODEL_VERSION
            )
        self.assertIn(self.far.pk, branches["lexical"])
        self.assertIn(self.near.pk, branches["semantic"])
        self.assertIn(self.far.pk, ordered)
        self.assertIn(self.near.pk, ordered)

    def test_exact_title_is_pinned_first(self):
        """RRF separates rank one from rank two by about 1.6%, so an exact
        title match needs pinning rather than a score bonus."""
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            ordered, _ = hybrid_ranking(
                self.published(), "Gamma project", model_version=MODEL_VERSION
            )
        self.assertEqual(ordered[0], self.far.pk)

    def test_query_uses_the_query_convention(self):
        """bge is asymmetric; a query must not be encoded as a passage."""
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)) as stub:
            semantic_ranking(self.published(), "some query", 10, MODEL_VERSION)
        stub.assert_called_once_with("some query")


class ProjectTypeFilterTests(SearchTestBase):
    def setUp(self):
        self.major_a = self.make_project("Major one", project_type="Major")
        self.major_b = self.make_project("Major two", project_type="Major")
        self.minor = self.make_project("Minor one", project_type="Minor")
        self.api = APIClient()

    def _ids(self, params):
        with override_settings(ALLOWED_HOSTS=["*"]):
            response = self.api.get(reverse("repository:project-list"), params)
        self.assertEqual(response.status_code, 200)
        return [row["id"] for row in response.json()["data"]]

    def test_major_filter(self):
        ids = self._ids({"project_type": "Major"})
        self.assertCountEqual(ids, [self.major_a.pk, self.major_b.pk])

    def test_minor_filter(self):
        self.assertEqual(self._ids({"project_type": "Minor"}), [self.minor.pk])

    def test_filter_is_case_insensitive(self):
        self.assertEqual(self._ids({"project_type": "minor"}), [self.minor.pk])

    def test_no_filter_returns_every_type(self):
        ids = self._ids({})
        self.assertCountEqual(ids, [self.major_a.pk, self.major_b.pk, self.minor.pk])

    def test_project_type_appears_in_the_facets(self):
        with override_settings(ALLOWED_HOSTS=["*"]):
            response = self.api.get(reverse("repository:project-facets"))
        data = response.json()["data"]
        self.assertIn("project_types", data)
        counts = {row["name"]: row["count"] for row in data["project_types"]}
        self.assertEqual(counts.get("Major"), 2)
        self.assertEqual(counts.get("Minor"), 1)
