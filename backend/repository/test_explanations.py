"""Why a recommendation says what it says.

Similar Projects and the Similar Work Check no longer report a band or a
percentile. They report the subject matter two pieces of work share, and the
value of that is entirely in what it refuses to say: a term has to be genuine
subject matter, rare enough to distinguish this pair from any other, and
recorded on the project rather than inferred. Where nothing qualifies the
answer is silence.

Every fixture here is invented. The corpus these tests build has nothing to
do with the real one, so a failure diff can only ever print terms written in
this file.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from repository.explanations import (
    MAX_TERMS,
    concept_shared_concepts,
    shared_concepts,
)
from organization.models import Campus, Department
from repository.models import Keyword, Project, ProjectKeyword
from repository.search_index import update_search_vector

# The rarity cut-off is a share of the corpus, so the corpus has to be big
# enough for "rare" to mean anything. At this size the cut-off lands at two
# projects, which makes every fixture below easy to reason about.
CORPUS = 25


class ExplanationTestBase(TestCase):
    def make_project(self, title, abstract="", keywords=(), status="Published",
                     **kwargs):
        project = Project.objects.create(
            title=title,
            abstract=abstract,
            project_type="Major",
            academic_level="UG",
            status=status,
            **kwargs,
        )
        for name in keywords:
            keyword, _ = Keyword.objects.get_or_create(name=name)
            ProjectKeyword.objects.create(project=project, keyword=keyword)
        project.refresh_from_db()
        update_search_vector(project)
        return project

    def fill_corpus(self, count=CORPUS, term="platform"):
        """Background projects, all sharing one word.

        That word is then common by construction, which is how these tests
        check that frequency does the filtering rather than a word list.
        """
        for index in range(count):
            self.make_project(
                "Filler %d %s" % (index, term),
                abstract="A %s built for coursework." % term,
            )

    def explain(self, subject, other):
        return shared_concepts(subject, [other])[other.pk]


class SharedConceptTests(ExplanationTestBase):
    def setUp(self):
        self.fill_corpus()

    def test_a_shared_keyword_is_offered_as_the_reason(self):
        left = self.make_project("Hiding data in images",
                                 keywords=["Steganography"])
        right = self.make_project("Recovering hidden payloads",
                                  keywords=["Steganography"])
        self.assertEqual(self.explain(left, right), ["Steganography"])

    def test_a_common_word_is_never_offered(self):
        """The filler corpus makes "platform" common. Two projects that share
        it share nothing worth saying, and the rarity rule has to work that
        out from the corpus rather than from a list of banned words."""
        left = self.make_project("A platform for scheduling")
        right = self.make_project("A platform for messaging")
        self.assertEqual(self.explain(left, right), [])

    def test_a_rare_term_survives_alongside_a_common_one(self):
        """Both projects share "platform", which the corpus makes common, and
        "Steganography", which it does not. Only the second is a reason."""
        left = self.make_project("A platform for hiding messages",
                                 keywords=["Steganography"])
        right = self.make_project("A platform for finding hidden messages",
                                  keywords=["Steganography"])
        terms = self.explain(left, right)
        self.assertIn("Steganography", terms)
        self.assertNotIn("Platform", terms)

    def test_terms_are_capped(self):
        shared = ["Steganography", "Cryptography", "Watermarking",
                  "Obfuscation", "Ciphertext"]
        left = self.make_project("Left", keywords=shared)
        right = self.make_project("Right", keywords=shared)
        self.assertEqual(len(self.explain(left, right)), MAX_TERMS)

    def test_a_multi_word_keyword_stays_whole(self):
        """"Secure Communication" is one concept. Split into two chips it
        reads as two, and "Secure" on its own says nothing."""
        left = self.make_project("Left", keywords=["Secure Communication"])
        right = self.make_project("Right", keywords=["Secure Communication"])
        self.assertEqual(self.explain(left, right), ["Secure Communication"])

    def test_inflections_of_a_term_are_recognised_as_one_concept(self):
        """Terms are matched as lexemes, so a keyword and a title word that
        differ only by inflection count as the same concept. This is
        inflection and not derivation: the analyser unifies "encryption" with
        "encrypting", and would not unify it with "cryptographic"."""
        left = self.make_project("Left", keywords=["Encryption"])
        right = self.make_project("Encrypting telemetry at the sensor")
        self.assertEqual(self.explain(left, right), ["Encryption"])

    def test_a_curated_keyword_is_preferred_to_a_title_word(self):
        """Both projects record the concept, one as a keyword and one only in
        its title. The keyword is what an author chose to call the subject, so
        it is the better label for it."""
        left = self.make_project("Left", keywords=["Encryption"])
        right = self.make_project("Encrypting telemetry at the sensor")
        self.assertEqual(self.explain(left, right), ["Encryption"])

    def test_nothing_in_common_yields_no_explanation(self):
        """A recommendation with no stated reason is honest. This is the case
        the empty list exists for, and it must not be filled."""
        left = self.make_project("Bridge deflection under load",
                                 keywords=["Structural Analysis"])
        right = self.make_project("Yeast fermentation kinetics",
                                  keywords=["Microbiology"])
        self.assertEqual(self.explain(left, right), [])

    def test_a_term_shared_only_by_two_abstracts_is_not_enough(self):
        """Without the anchor, pairs get explained by whatever incidental
        vocabulary two abstracts happen to share."""
        left = self.make_project(
            "Bridge deflection under load",
            abstract="Measurements were logged with a calibrated interferometer.",
            keywords=["Structural Analysis"],
        )
        right = self.make_project(
            "Yeast fermentation kinetics",
            abstract="Growth was tracked using a calibrated interferometer.",
            keywords=["Microbiology"],
        )
        self.assertEqual(self.explain(left, right), [])

    def test_an_anchored_term_confirmed_by_an_abstract_is_enough(self):
        """The other half of the same rule: subject matter for one project,
        discussed in the other, is a real relationship."""
        left = self.make_project("Left", keywords=["Interferometer"])
        right = self.make_project(
            "Bridge deflection under load",
            abstract="Displacement was measured with an interferometer.",
        )
        self.assertEqual(self.explain(left, right), ["Interferometer"])

    def test_a_shared_supervisor_or_department_is_not_a_reason(self):
        """Department, cluster and intake year live in weight D of the search
        vector along with people's names. Sharing any of them says nothing
        about subject matter, and surfacing a person as the reason two
        projects are related would also disclose them."""
        campus = Campus.objects.create(name="Quorvex Campus", location="Nowhere")
        department = Department.objects.create(name="Zephyrics", campus=campus)
        left = self.make_project("Bridge deflection under load",
                                 department=department, cluster="Quorvex",
                                 batch="2078")
        right = self.make_project("Yeast fermentation kinetics",
                                  department=department, cluster="Quorvex",
                                  batch="2078")
        self.assertEqual(self.explain(left, right), [])

    def test_the_rarest_term_comes_first(self):
        for index in range(4):
            self.make_project("Bystander %d" % index, keywords=["Cryptography"])
        left = self.make_project("Left",
                                 keywords=["Cryptography", "Steganography"])
        right = self.make_project("Right",
                                  keywords=["Cryptography", "Steganography"])
        self.assertEqual(self.explain(left, right)[0], "Steganography")

    def test_an_unpublished_project_does_not_count_towards_rarity(self):
        for index in range(6):
            self.make_project("Draft %d" % index, keywords=["Steganography"],
                              status="Processing")
        left = self.make_project("Left", keywords=["Steganography"])
        right = self.make_project("Right", keywords=["Steganography"])
        self.assertEqual(self.explain(left, right), ["Steganography"])

    def test_casing_recorded_on_the_keyword_is_preserved(self):
        """Acronyms must not be flattened, and a lower-case keyword should not
        be shouted back at the reader."""
        left = self.make_project("Left", keywords=["LoRa telemetry"])
        right = self.make_project("Right", keywords=["LoRa telemetry"])
        self.assertEqual(self.explain(left, right), ["LoRa Telemetry"])


class SmallCorpusTests(ExplanationTestBase):
    def test_no_explanation_is_offered_from_a_corpus_too_small_to_judge(self):
        """With a handful of projects every term looks rare, so rarity carries
        no information and any explanation drawn from it would be an
        accident."""
        left = self.make_project("Left", keywords=["Steganography"])
        right = self.make_project("Right", keywords=["Steganography"])
        self.assertEqual(shared_concepts(left, [right])[right.pk], [])


class ConceptExplanationTests(ExplanationTestBase):
    def setUp(self):
        self.fill_corpus()

    def test_a_described_idea_is_explained_against_a_project(self):
        project = self.make_project("Hiding data in images",
                                    keywords=["Steganography"])
        result = concept_shared_concepts(
            "I want to build a steganography tool for photographs", [project]
        )
        self.assertEqual(result[project.pk], ["Steganography"])

    def test_a_common_word_in_the_description_explains_nothing(self):
        project = self.make_project("A platform for scheduling")
        result = concept_shared_concepts(
            "I want to build a platform", [project]
        )
        self.assertEqual(result[project.pk], [])

    def test_a_description_matching_only_an_abstract_is_not_enough(self):
        """On this side the anchor can only be the project's, because a typed
        idea has no curated keywords of its own."""
        project = self.make_project(
            "Bridge deflection under load",
            abstract="Measured with a calibrated interferometer.",
        )
        result = concept_shared_concepts(
            "something involving an interferometer", [project]
        )
        self.assertEqual(result[project.pk], [])

    def test_an_empty_description_explains_nothing(self):
        project = self.make_project("Left", keywords=["Steganography"])
        self.assertEqual(concept_shared_concepts("", [project])[project.pk], [])


class ExplanationEndpointTests(ExplanationTestBase):
    """The explanation has to survive to the interface, and the numbers that
    used to stand in for it must not."""

    def setUp(self):
        self.fill_corpus()
        self.subject = self.make_project("Hiding data in images",
                                         keywords=["Steganography"])
        self.neighbour = self.make_project("Recovering hidden payloads",
                                           keywords=["Steganography"])
        self.api = APIClient()

    def _payload(self):
        response = self.api.get(
            reverse("repository:project-similar",
                    kwargs={"project_id": str(self.subject.pk)}),
            HTTP_HOST="testserver",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_every_row_carries_the_field_even_when_it_is_empty(self):
        """The interface renders nothing for an empty list, so the key has to
        be present rather than conditionally omitted."""
        for row in self._payload():
            self.assertIn("shared_concepts", row)
            self.assertIsInstance(row["shared_concepts"], list)

    def test_no_row_carries_a_score_band_or_percentile(self):
        for row in self._payload():
            self.assertEqual(set(row), {"project", "shared_concepts"})
