"""Similarity calibration, banding and the two similarity endpoints.

The embedding model is never loaded here. Vectors are constructed by hand so
that every cosine in these tests is exact and the assertions are about the
calibration and interpretation logic rather than about what a neural network
happens to produce on a given day.
"""

import math
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from repository.models import (
    Project,
    ProjectEmbedding,
    SimilarityCalibration,
)
from repository.similarity import (
    band_for,
    calibration,
    check_concept,
    percentile_for,
    similar_projects,
)

MODEL_VERSION = "test-model-v1"
DIM = 384


def unit_vector_at(angle_from_base):
    """A unit vector whose cosine with `base_vector()` is cos(angle).

    Built in the first two coordinates so the remaining 382 stay zero; the
    dot product is then exactly cos(angle) and the test can assert on a
    number it chose rather than one it measured.
    """
    vector = [0.0] * DIM
    vector[0] = math.cos(angle_from_base)
    vector[1] = math.sin(angle_from_base)
    return vector


def base_vector():
    return unit_vector_at(0.0)


def vector_with_cosine(target):
    """Unit vector whose cosine against the base vector is `target`.

    Every vector this produces lies in the plane of the first two
    coordinates, so two of them are only as far apart as the difference of
    their angles. That is fine for asserting one project's score, and wrong
    for building a set of mutually unrelated projects: 0.60 and 0.66 against
    the base are 0.997 against each other. Use `axis_vector` for that.
    """
    target = max(-1.0, min(1.0, target))
    return unit_vector_at(math.acos(target))


def axis_vector(index):
    """The `index`-th basis vector.

    Any two are orthogonal, so a set of them is a set of projects that are
    genuinely unrelated to each other and to anything built from a different
    axis.
    """
    vector = [0.0] * DIM
    vector[index] = 1.0
    return vector


class SimilarityTestBase(TestCase):
    def make_project(self, title, **kwargs):
        defaults = {
            "abstract": "abstract text",
            "project_type": "Major",
            "academic_level": "UG",
            "status": "Published",
        }
        defaults.update(kwargs)
        return Project.objects.create(title=title, **defaults)

    def embed(self, project, vector):
        return ProjectEmbedding.objects.create(
            project=project,
            model_version=MODEL_VERSION,
            source_hash="x" * 64,
            embedding=vector,
        )

    def make_calibration(self, breakpoints=None):
        return SimilarityCalibration.objects.create(
            model_version=MODEL_VERSION,
            corpus_size=95,
            pair_count=4465,
            sampled=False,
            breakpoints=breakpoints
            or [
                [1, 0.52],
                [50, 0.64],
                [95, 0.756],
                [97, 0.78],
                [99, 0.822],
                [99.9, 0.90],
            ],
        )


class BandTests(SimilarityTestBase):
    """Band selection, which is what a reader is actually shown."""

    def setUp(self):
        self.document_bands = [
            (0.95, "very_high_overlap", "Very high overlap"),
            (0.86, "high_similarity", "High similarity"),
            (0.78, "related_work", "Related work exists"),
            (None, "distinct", "Appears distinct"),
        ]
        self.title_bands = [
            (0.87, "potentially_similar", "Potentially similar"),
            (0.82, "uncertain", "Uncertain — review"),
            (None, "likely_distinct", "Likely distinct"),
        ]

    def test_title_abstract_bands_at_each_boundary(self):
        cases = [
            (0.99, "very_high_overlap"),
            (0.95, "very_high_overlap"),
            (0.949, "high_similarity"),
            (0.86, "high_similarity"),
            (0.859, "related_work"),
            (0.78, "related_work"),
            (0.779, "distinct"),
            (0.10, "distinct"),
        ]
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(band_for(score, self.document_bands)[0], expected)

    def test_title_only_bands_are_more_conservative(self):
        cases = [
            (0.95, "potentially_similar"),
            (0.87, "potentially_similar"),
            (0.869, "uncertain"),
            (0.82, "uncertain"),
            (0.819, "likely_distinct"),
        ]
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(band_for(score, self.title_bands)[0], expected)

    def test_title_only_never_claims_more_than_potential_similarity(self):
        """The conservatism of the title-only ladder is in what it is willing
        to assert. However high a title-only score goes it stops at
        "potentially similar", while a document comparison can reach "very
        high overlap"."""
        self.assertEqual(band_for(0.999, self.title_bands)[1], "Potentially similar")
        self.assertEqual(band_for(0.999, self.document_bands)[1], "Very high overlap")

    def test_the_ladders_disagree_in_the_middle(self):
        """0.84 is already 'uncertain' from a title alone but only 'related
        work' with an abstract behind it."""
        self.assertEqual(band_for(0.84, self.title_bands)[0], "uncertain")
        self.assertEqual(band_for(0.84, self.document_bands)[0], "related_work")


class PercentileTests(SimilarityTestBase):
    def test_percentile_interpolates_between_breakpoints(self):
        calib = self.make_calibration()
        # Exactly on a breakpoint.
        self.assertAlmostEqual(calib.percentile_for(0.78), 97.0, places=1)
        self.assertAlmostEqual(calib.percentile_for(0.822), 99.0, places=1)
        # Halfway between 0.78 (97) and 0.822 (99) is about 98.
        midpoint = calib.percentile_for(0.801)
        self.assertGreater(midpoint, 97.0)
        self.assertLess(midpoint, 99.0)

    def test_percentile_is_clamped_outside_the_measured_range(self):
        calib = self.make_calibration()
        self.assertEqual(calib.percentile_for(0.10), 1.0)
        self.assertEqual(calib.percentile_for(0.999), 99.9)

    def test_percentile_is_none_without_a_calibration(self):
        self.assertIsNone(percentile_for(0.9))

    def test_calibration_is_looked_up_by_model_version(self):
        self.make_calibration()
        self.assertIsNotNone(calibration(MODEL_VERSION))
        self.assertIsNone(calibration("some-other-model"))

    def test_calibration_records_the_corpus_it_was_measured_on(self):
        """A calibration taken over 95 projects must remain visibly a
        calibration over 95 projects once the repository is larger."""
        calib = self.make_calibration()
        self.assertEqual(calib.corpus_size, 95)
        self.assertEqual(calib.pair_count, 4465)


class SimilarProjectsTests(SimilarityTestBase):
    def setUp(self):
        self.make_calibration()
        self.subject = self.make_project("Subject project")
        self.embed(self.subject, base_vector())

    def test_threshold_excludes_everything_below_it(self):
        near = self.make_project("Just above the threshold")
        far = self.make_project("Just below the threshold")
        self.embed(near, vector_with_cosine(0.80))
        self.embed(far, vector_with_cosine(0.76))

        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        returned = [r["project"].pk for r in rows]
        self.assertIn(near.pk, returned)
        self.assertNotIn(far.pk, returned)

    def test_boundary_score_is_included(self):
        edge = self.make_project("Exactly at the threshold")
        self.embed(edge, vector_with_cosine(0.78))
        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        self.assertEqual([r["project"].pk for r in rows], [edge.pk])

    def test_subject_project_is_excluded(self):
        other = self.make_project("Another project")
        self.embed(other, vector_with_cosine(0.90))
        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        self.assertNotIn(self.subject.pk, [r["project"].pk for r in rows])

    def test_results_are_capped_at_five(self):
        for index in range(9):
            project = self.make_project(f"Neighbour {index}")
            self.embed(project, vector_with_cosine(0.90))
        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        self.assertEqual(len(rows), 5)

    def test_empty_when_nothing_reaches_the_threshold(self):
        """An honest empty answer. The panel this replaced padded itself with
        same-department projects regardless of whether they were related."""
        for index in range(4):
            project = self.make_project(f"Unrelated {index}")
            self.embed(project, vector_with_cosine(0.60))
        self.assertEqual(similar_projects(self.subject, model_version=MODEL_VERSION), [])

    def test_results_are_ordered_by_similarity(self):
        closest = self.make_project("Closest")
        middle = self.make_project("Middle")
        furthest = self.make_project("Furthest")
        self.embed(closest, vector_with_cosine(0.95))
        self.embed(middle, vector_with_cosine(0.88))
        self.embed(furthest, vector_with_cosine(0.80))
        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        self.assertEqual(
            [r["project"].pk for r in rows], [closest.pk, middle.pk, furthest.pk]
        )

    def test_raw_cosine_is_available_internally(self):
        near = self.make_project("Neighbour")
        self.embed(near, vector_with_cosine(0.90))
        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        self.assertAlmostEqual(rows[0]["score"], 0.90, places=4)
        self.assertEqual(rows[0]["band"], "high_similarity")
        self.assertIsNotNone(rows[0]["percentile"])

    def test_department_does_not_influence_selection(self):
        """Two projects in different departments must be able to match, and
        sharing a department must not be enough on its own."""
        same_department_unrelated = self.make_project("Same department, unrelated")
        self.embed(same_department_unrelated, vector_with_cosine(0.62))
        cross_department_related = self.make_project("Other department, related")
        self.embed(cross_department_related, vector_with_cosine(0.91))

        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        returned = [r["project"].pk for r in rows]
        self.assertEqual(returned, [cross_department_related.pk])

    def test_minor_and_major_are_compared_against_each_other(self):
        minor = self.make_project("A minor project", project_type="Minor")
        self.embed(minor, vector_with_cosine(0.92))
        rows = similar_projects(self.subject, model_version=MODEL_VERSION)
        self.assertIn(minor.pk, [r["project"].pk for r in rows])


class SimilarWorkCheckTests(SimilarityTestBase):
    """Concept-first checking, and the threshold that decides what is shown."""

    def setUp(self):
        self.make_calibration()
        self.existing = self.make_project("An existing project")
        self.embed(self.existing, base_vector())

    def _check(self, *, concept="", title="", description="", cosine=0.90):
        """Run a check with the concept vector pinned, so the assertions are
        about the threshold and the banding rather than about the encoder."""
        with patch(
            "repository.similarity.embed_concept",
            return_value=(vector_with_cosine(cosine), "text"),
        ):
            return check_concept(
                concept=concept,
                title=title,
                description=description,
                model_version=MODEL_VERSION,
            )

    def test_a_concept_alone_is_enough(self):
        """No title, no abstract, no keywords. A student weighing up an idea
        has none of those yet."""
        result = self._check(concept="An app that tracks calories.", cosine=0.90)
        self.assertTrue(result["threshold_met"])
        self.assertEqual(len(result["strong"]), 1)

    def test_optional_title_and_description_are_accepted(self):
        result = self._check(
            concept="An app that tracks calories.",
            title="NutriTrack",
            description="Recommends meals against a nutrition goal.",
            cosine=0.90,
        )
        self.assertTrue(result["threshold_met"])

    def test_concept_goes_through_the_concept_encoder(self):
        """bge is asymmetric: an idea is a query against a corpus of
        documents, so it must not take the document path."""
        with patch(
            "repository.similarity.embed_concept",
            return_value=(vector_with_cosine(0.9), "t"),
        ) as stub:
            check_concept(concept="an idea", model_version=MODEL_VERSION)
        stub.assert_called_once_with(concept="an idea", title="", description="")

    def test_below_threshold_candidates_are_not_listed_as_related(self):
        """The failure this replaced: the check returned its nearest
        neighbours whatever their scores, so unrelated projects appeared
        beside the one real match."""
        # Each on its own axis, so they are unrelated to one another as well
        # as to the concept, which is what "a corpus of unrelated work" means.
        for index in (2, 3, 4):
            project = self.make_project("Unrelated %d" % index)
            self.embed(project, axis_vector(index))

        with patch(
            "repository.similarity.embed_concept",
            return_value=(axis_vector(5), "text"),
        ):
            result = check_concept(
                concept="something else entirely", model_version=MODEL_VERSION
            )

        self.assertFalse(result["threshold_met"])
        self.assertEqual(result["strong"], [])
        self.assertEqual(result["possible"], [])

    def test_only_above_threshold_work_is_returned(self):
        near = self.make_project("Genuinely related")
        far = self.make_project("Not related")
        self.embed(near, vector_with_cosine(0.88))
        self.embed(far, vector_with_cosine(0.60))

        with patch(
            "repository.similarity.embed_concept",
            return_value=(base_vector(), "text"),
        ):
            result = check_concept(concept="idea", model_version=MODEL_VERSION)

        returned = [row["project"].pk for row in result["strong"]]
        self.assertIn(near.pk, returned)
        self.assertNotIn(far.pk, returned)

    def test_the_single_closest_candidate_is_offered_when_nothing_qualifies(self):
        result = self._check(concept="unrelated idea", cosine=0.55)
        self.assertFalse(result["threshold_met"])
        self.assertEqual(result["strong"], [])
        closest = result["closest_below_threshold"]
        self.assertIsNotNone(closest)
        self.assertEqual(closest["project"].pk, self.existing.pk)
        self.assertEqual(closest["band"], "distinct")

    def test_boundary_score_counts_as_related(self):
        result = self._check(concept="idea", cosine=0.78)
        self.assertTrue(result["threshold_met"])
        self.assertEqual(result["overall_band"], "related_work")

    def test_just_below_the_boundary_does_not(self):
        result = self._check(concept="idea", cosine=0.779)
        self.assertFalse(result["threshold_met"])

    def test_bands_across_the_ladder(self):
        for cosine, expected in (
            (0.97, "very_high_overlap"),
            (0.90, "high_similarity"),
            (0.80, "related_work"),
        ):
            with self.subTest(cosine=cosine):
                result = self._check(concept="idea", cosine=cosine)
                self.assertEqual(result["overall_band"], expected)

    def test_percentile_is_attached(self):
        result = self._check(concept="idea", cosine=0.90)
        self.assertIsNotNone(result["strong"][0]["percentile"])

    # ------------------------------------------------------------------
    # The standout band
    #
    # A concept is a weaker signal than a full document, so the 0.78 cut-off
    # misses genuine matches. Lowering it is not the fix: a concept for work
    # absent from the corpus scored 0.7738 against its nearest project, above
    # a genuine match at 0.7402. The rule below the cut-off is therefore about
    # separation, not level -- one project, only when it leads the field.
    # ------------------------------------------------------------------

    def _corpus(self, *cosines):
        """Replace the corpus with projects at exactly these cosines against
        the concept vector, and run a check."""
        ProjectEmbedding.objects.all().delete()
        projects = []
        for index, cosine in enumerate(cosines):
            project = self.make_project("Project %d" % index)
            self.embed(project, vector_with_cosine(cosine))
            projects.append(project)
        with patch(
            "repository.similarity.embed_concept",
            return_value=(base_vector(), "text"),
        ):
            return projects, check_concept(
                concept="an idea", model_version=MODEL_VERSION
            )

    def test_a_standout_below_the_cut_off_is_offered(self):
        projects, result = self._corpus(0.76, 0.60)
        self.assertEqual(result["strong"], [])
        self.assertEqual(len(result["possible"]), 1)
        self.assertEqual(result["possible"][0]["project"].pk, projects[0].pk)

    def test_a_flat_cluster_offers_nothing(self):
        """The absent-subject case. Nothing here leads the field, so the
        corpus holds nothing in particular and the band stays empty."""
        _projects, result = self._corpus(0.76, 0.74, 0.73)
        self.assertEqual(result["strong"], [])
        self.assertEqual(result["possible"], [])
        self.assertIsNotNone(result["closest_below_threshold"])

    def test_a_standout_below_the_floor_is_not_offered(self):
        """Leading the field is not enough on its own. Below the floor the
        leader is only the nearest of several unrelated things."""
        _projects, result = self._corpus(0.68, 0.40)
        self.assertEqual(result["possible"], [])

    def test_the_standout_band_holds_at_most_one_project(self):
        """The test is a statement about the leader against the rest, so it
        has no meaning applied to a second row."""
        _projects, result = self._corpus(0.77, 0.76, 0.50)
        self.assertLessEqual(len(result["possible"]), 1)

    def test_the_standout_band_is_empty_when_strong_matches_exist(self):
        _projects, result = self._corpus(0.90, 0.75)
        self.assertEqual(len(result["strong"]), 1)
        self.assertEqual(result["possible"], [])

    def test_a_standout_is_not_reported_as_related_work(self):
        """It is offered for a look, not asserted as a match, so the flag the
        interface keys its verdict off stays false."""
        _projects, result = self._corpus(0.76, 0.60)
        self.assertFalse(result["threshold_met"])

    def test_a_standout_carries_its_own_band_label(self):
        """Without a rung for this range the row would be labelled "Appears
        distinct" while sitting under a heading calling it possibly related."""
        _projects, result = self._corpus(0.76, 0.60)
        self.assertEqual(result["possible"][0]["band"], "possibly_related")
        self.assertEqual(result["overall_band"], "possibly_related")
        self.assertNotIn("distinct", result["overall_band_label"].lower())

    def test_the_standout_margin_decides_either_side_of_itself(self):
        """Not asserted at the margin exactly: pgvector stores a vector as
        float4, so a cosine reconstructed from an angle lands a few parts in
        ten million away from the value the test asked for, which is enough to
        make an equality test on the boundary flip."""
        for lead, expected in ((0.09, 1), (0.07, 0)):
            with self.subTest(lead=lead):
                _projects, result = self._corpus(0.76, 0.76 - lead)
                self.assertEqual(len(result["possible"]), expected)

    def test_high_overlap_is_never_called_duplication(self):
        result = self._check(concept="idea", cosine=0.97)
        label = result["overall_band_label"].lower()
        self.assertNotIn("duplicate", label)
        self.assertNotIn("plagiar", label)
        self.assertNotIn("copied", label)


class SimilarityEndpointTests(SimilarityTestBase):
    """The API boundary, where the raw cosine must stop."""

    def setUp(self):
        self.make_calibration()
        self.subject = self.make_project("Subject project")
        self.embed(self.subject, base_vector())
        self.neighbour = self.make_project("Neighbour project")
        self.embed(self.neighbour, vector_with_cosine(0.90))

        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="reader@example.com", password="pw12345!"
        )
        # Authentication here is cookie-borne JWT, so a Django session login
        # would not authenticate a DRF view.
        self.api = APIClient()

    def _similar_url(self):
        return reverse("repository:project-similar", args=[self.subject.pk])

    def settings_embedding(self):
        from django.conf import settings as django_settings

        return {**django_settings.EMBEDDING, "MODEL_VERSION": MODEL_VERSION}

    def test_similar_projects_response_carries_no_number_about_the_match(self):
        """Not the cosine, and not the band or percentile that used to stand
        in for it. All three describe the size of a number rather than the
        relationship, and the percentile in particular reads as a percentage
        of shared content. A result carries what it shares, or nothing."""
        with self.settings(EMBEDDING=self.settings_embedding()):
            response = self.api.get(self._similar_url())
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(len(payload), 1)
        entry = payload[0]
        self.assertEqual(set(entry), {"project", "shared_concepts"})
        for absent in ("score", "cosine", "similarity", "band", "band_label",
                       "percentile"):
            self.assertNotIn(absent, entry)

    def test_similar_projects_endpoint_caps_at_five(self):
        """The detail page renders whatever the endpoint returns, so the cap
        has to hold at the API boundary and not only in the service."""
        for index in range(9):
            project = self.make_project("Neighbour %d" % index)
            self.embed(project, vector_with_cosine(0.90))
        with self.settings(EMBEDDING=self.settings_embedding()):
            response = self.api.get(self._similar_url())
        self.assertEqual(len(response.json()["data"]), 5)

    def test_similar_projects_endpoint_returns_an_empty_list_not_an_error(self):
        """A third of the catalogue has no project above the threshold. The
        page shows an empty state for that, which needs a 200 and [], not a
        404 and not a fallback list."""
        distant = self.make_project("Nothing like it")
        self.embed(distant, vector_with_cosine(0.40))
        self.neighbour.delete()

        with self.settings(EMBEDDING=self.settings_embedding()):
            response = self.api.get(self._similar_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])

    def test_similar_projects_endpoint_preserves_similarity_order(self):
        closer = self.make_project("Closer")
        self.embed(closer, vector_with_cosine(0.95))
        with self.settings(EMBEDDING=self.settings_embedding()):
            response = self.api.get(self._similar_url())
        returned = [row["project"]["id"] for row in response.json()["data"]]
        self.assertEqual(returned, [closer.pk, self.neighbour.pk])

    def test_similar_projects_endpoint_excludes_the_subject(self):
        with self.settings(EMBEDDING=self.settings_embedding()):
            response = self.api.get(self._similar_url())
        returned = [row["project"]["id"] for row in response.json()["data"]]
        self.assertNotIn(self.subject.pk, returned)

    def test_similar_projects_carries_the_type_badge_the_page_renders(self):
        """project_type lived on the detail serializer only, so the badge on
        these cards rendered as undefined even though the value existed."""
        with self.settings(EMBEDDING=self.settings_embedding()):
            response = self.api.get(self._similar_url())
        entry = response.json()["data"][0]
        self.assertIn("project_type", entry["project"])
        self.assertEqual(entry["project"]["project_type"], "Major")

    def test_similarity_check_requires_some_input(self):
        self.api.force_authenticate(user=self.user)
        response = self.api.post(
            reverse("repository:similarity-check"),
            {"concept": "   ", "title": "  "},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_similarity_check_requires_authentication(self):
        response = self.api.post(
            reverse("repository:similarity-check"),
            {"concept": "an idea"},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_similarity_check_response_hides_the_raw_cosine(self):
        self.api.force_authenticate(user=self.user)
        with self.settings(EMBEDDING=self.settings_embedding()), patch(
            "repository.similarity.embed_concept",
            return_value=(vector_with_cosine(0.90), "text"),
        ):
            response = self.api.post(
                reverse("repository:similarity-check"),
                {"concept": "an app that tracks calories"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertTrue(payload["threshold_met"])
        self.assertNotIn("overall_band", payload)
        self.assertNotIn("overall_band_label", payload)
        for entry in payload["strong"] + payload["possible"]:
            self.assertEqual(set(entry), {"project", "shared_concepts"})
            for absent in ("score", "cosine", "band", "band_label", "percentile"):
                self.assertNotIn(absent, entry)

    def test_endpoint_reports_no_related_work_below_the_threshold(self):
        self.api.force_authenticate(user=self.user)
        with self.settings(EMBEDDING=self.settings_embedding()), patch(
            "repository.similarity.embed_concept",
            return_value=(vector_with_cosine(0.10), "text"),
        ):
            response = self.api.post(
                reverse("repository:similarity-check"),
                {"concept": "something unrelated"},
                format="json",
            )
        payload = response.json()["data"]
        self.assertFalse(payload["threshold_met"])
        self.assertEqual(payload["strong"], [])
        self.assertEqual(payload["possible"], [])
        self.assertIsNotNone(payload["closest_below_threshold"])
        self.assertNotIn("score", payload["closest_below_threshold"])
