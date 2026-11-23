

import math
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from repository.hybrid_search import hybrid_ranking, semantic_ranking
from repository.indexing import defer_indexing, queue_project_indexing
from repository.models import Keyword, Project, ProjectEmbedding, ProjectKeyword
from repository.search_index import update_search_vector

MODEL_VERSION = "test-model-v1"
DIM = 384

EMBEDDING_SETTINGS = {
    "MODEL_NAME": "test",
    "MODEL_VERSION": MODEL_VERSION,
    "DIMENSION": DIM,
    "QUERY_PREFIX": "q: ",
    "MAX_SEQ_LENGTH": 512,
    "BATCH_SIZE": 4,
    "NORMALIZE": True,
    "PREWARM": False,
}


def axis_vector(index):
    vector = [0.0] * DIM
    vector[index] = 1.0
    return vector


def vector_at(angle):
    vector = [0.0] * DIM
    vector[0] = math.cos(angle)
    vector[1] = math.sin(angle)
    return vector


def vector_with_cosine(target):
    return vector_at(math.acos(max(-1.0, min(1.0, target))))


class IndexingTestBase(TestCase):
    def make_project(self, title, abstract="", project_type="Major", keywords=(),
                     status="Published"):
        project = Project.objects.create(
            title=title,
            abstract=abstract,
            project_type=project_type,
            academic_level="UG",
            status=status,
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


@override_settings(EMBEDDING=EMBEDDING_SETTINGS)
class CandidateUnionTests(IndexingTestBase):
    """Only what a branch retrieved may appear in the results."""

    def setUp(self):
        # Matches the words but not the meaning of the query vector.
        self.lexical_only = self.make_project(
            "Photovoltaic tracker", abstract="Orients panels toward the sun."
        )
        self.embed(self.lexical_only, axis_vector(7))

        # Matches the query vector but shares no vocabulary with it.
        self.semantic_only = self.make_project(
            "Junction timing agent", abstract="An agent learns signal timings."
        )
        self.embed(self.semantic_only, vector_with_cosine(0.95))

        # Matches neither.
        self.unrelated = self.make_project(
            "Mesh routing protocol", abstract="Routing in ad hoc networks."
        )
        self.embed(self.unrelated, axis_vector(9))

    def _rank(self, query):
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            return hybrid_ranking(self.published(), query, model_version=MODEL_VERSION)

    def test_a_lexical_only_match_is_returned(self):
        ordered, branches = self._rank("photovoltaic")
        self.assertIn(self.lexical_only.pk, branches["lexical"])
        self.assertIn(self.lexical_only.pk, ordered)

    def test_a_semantic_only_match_is_returned(self):
        ordered, branches = self._rank("photovoltaic")
        self.assertIn(self.semantic_only.pk, branches["semantic"])
        self.assertIn(self.semantic_only.pk, ordered)

    def test_a_project_matching_neither_branch_is_excluded(self):
        """The bug this covers: the semantic branch returned its k nearest
        whatever the scores, so over a small corpus every project entered the
        candidate set and appeared in the results."""
        ordered, branches = self._rank("photovoltaic")
        self.assertNotIn(self.unrelated.pk, branches["lexical"])
        self.assertNotIn(self.unrelated.pk, branches["semantic"])
        self.assertNotIn(self.unrelated.pk, ordered)

    def test_the_result_set_is_exactly_the_union(self):
        ordered, branches = self._rank("photovoltaic")
        union = set(branches["lexical"]) | set(branches["semantic"])
        self.assertEqual(set(ordered), union)

    def test_a_query_matching_nothing_returns_nothing(self):
        with patch(
            "repository.hybrid_search.embed_query", return_value=axis_vector(200)
        ):
            ordered, branches = hybrid_ranking(
                self.published(), "zzzznonexistentterm", model_version=MODEL_VERSION
            )
        self.assertEqual(branches["lexical"], [])
        self.assertEqual(branches["semantic"], [])
        self.assertEqual(ordered, [])

    def test_the_semantic_floor_excludes_distant_vectors(self):
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            ids = semantic_ranking(
                self.published(), "anything", 50, MODEL_VERSION
            )
        self.assertIn(self.semantic_only.pk, ids)
        self.assertNotIn(self.unrelated.pk, ids)

    def test_the_floor_can_be_overridden_for_evaluation(self):
        """The harness needs to measure the branch without the candidacy
        filter, so the floor is a parameter rather than a constant."""
        with patch("repository.hybrid_search.embed_query", return_value=vector_at(0.0)):
            ids = semantic_ranking(
                self.published(), "anything", 50, MODEL_VERSION, min_score=-1.0
            )
        self.assertIn(self.unrelated.pk, ids)


@override_settings(EMBEDDING=EMBEDDING_SETTINGS)
class SearchEndpointTests(IndexingTestBase):
    """The list endpoint must not pad its results."""

    def setUp(self):
        self.match = self.make_project(
            "Solar tracker", abstract="Photovoltaic orientation."
        )
        self.embed(self.match, vector_with_cosine(0.95))
        self.other = self.make_project(
            "Mesh routing", abstract="Ad hoc network routing."
        )
        self.embed(self.other, axis_vector(9))
        self.api = APIClient()

    def _ids(self, params):
        with override_settings(ALLOWED_HOSTS=["*"]), patch(
            "repository.hybrid_search.embed_query", return_value=vector_at(0.0)
        ):
            response = self.api.get(reverse("repository:project-list"), params)
        self.assertEqual(response.status_code, 200)
        return [row["id"] for row in response.json()["data"]]

    def test_only_matching_projects_are_listed(self):
        self.assertEqual(self._ids({"q": "photovoltaic"}), [self.match.pk])

    def test_a_query_with_no_matches_returns_an_empty_list(self):
        with override_settings(ALLOWED_HOSTS=["*"]), patch(
            "repository.hybrid_search.embed_query", return_value=axis_vector(200)
        ):
            response = self.api.get(
                reverse("repository:project-list"), {"q": "zzzznonexistentterm"}
            )
        self.assertEqual(response.json()["data"], [])

    def test_an_empty_query_still_lists_the_catalogue(self):
        self.assertCountEqual(self._ids({}), [self.match.pk, self.other.pk])


class AutomaticIndexingTests(IndexingTestBase):
    """Publication has to make a project findable on its own."""

    def test_creating_a_project_builds_its_lexical_vector_immediately(self):
        project = Project.objects.create(
            title="Newly created project",
            abstract="An abstract.",
            project_type="Minor",
            academic_level="UG",
            status="Published",
        )
        project.refresh_from_db()
        self.assertIsNotNone(project.search_vector)

    def test_queue_project_indexing_fires_after_commit(self):
        project = self.make_project("Queued project")
        with patch("repository.tasks.embed_project") as task:
            with self.captureOnCommitCallbacks(execute=True):
                queue_project_indexing(project.pk)
        task.delay.assert_called_once_with(project.pk)

    def test_defer_indexing_suppresses_the_per_save_task(self):
        """A publication writes the project, then its people, sections,
        keywords and references. Without deferral each of those queues its own
        embedding task for the same project, and each loads the model."""
        with patch("repository.tasks.embed_project") as task:
            with self.captureOnCommitCallbacks(execute=True):
                with defer_indexing():
                    project = Project.objects.create(
                        title="Deferred project",
                        abstract="An abstract.",
                        project_type="Major",
                        academic_level="UG",
                        status="Published",
                    )
                    project.abstract = "Revised."
                    project.save()
        task.delay.assert_not_called()

    def test_deferral_still_maintains_the_lexical_vector(self):
        """Only the embedding is deferred. The lexical vector is one UPDATE
        inside the same transaction and is always current."""
        with self.captureOnCommitCallbacks(execute=True):
            with defer_indexing():
                project = Project.objects.create(
                    title="Deferred lexical project",
                    abstract="Distinctive phrasing here.",
                    project_type="Major",
                    academic_level="UG",
                    status="Published",
                )
        project.refresh_from_db()
        self.assertIsNotNone(project.search_vector)

    def test_a_broker_failure_during_queueing_is_not_fatal(self):
        project = self.make_project("Unqueueable project")
        with patch("repository.tasks.embed_project") as task:
            task.delay.side_effect = RuntimeError("broker unavailable")
            with self.captureOnCommitCallbacks(execute=True):
                queue_project_indexing(project.pk)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_queueing_twice_is_harmless(self):
        """The task compares digests before encoding, so a duplicate queue
        costs one hash."""
        project = self.make_project("Twice queued")
        with patch("repository.tasks.embed_project") as task:
            with self.captureOnCommitCallbacks(execute=True):
                queue_project_indexing(project.pk)
                queue_project_indexing(project.pk)
        self.assertEqual(task.delay.call_count, 2)
