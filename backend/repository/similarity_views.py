"""Similar Projects and the Similar Work Check.

This module is the boundary at which similarity scores stop being exposed.
Neither endpoint returns the raw cosine, the corpus-relative percentile or
the band label. A cosine of 0.79 reads as "79% similar", which is not what
cosine measures; a percentile reads as a proportion of shared content, which
it is not; and a band such as "Very high overlap" edges towards a claim about
duplication that embedding similarity cannot support.

Each result instead carries the subject matter the two pieces of work share,
from `repository.explanations`. Scores, bands and percentiles are still
computed unchanged and remain available to `repository.similarity` and to the
evaluation harness.
"""

from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from core.responses import success_response
from repository.models import Project
from repository.serializers import ProjectListSerializer
from repository.explanations import (
    concept_shared_concepts,
    explanations_available,
    shared_concepts,
)
from repository.similarity import check_concept, similar_projects

MAX_TITLE = 500
MAX_CONCEPT = 20000


def _present(row, request, explanations):
    """One similarity result as the interface sees it.

    Score, band and percentile are dropped here rather than never computed:
    retrieval, calibration and the evaluation harness all work in raw cosine.
    """
    project = ProjectListSerializer(row["project"], context={"request": request}).data
    return {
        "project": project,
        "shared_concepts": explanations.get(row["project"].pk, []),
    }


class SimilarProjectsView(APIView):
    """Projects semantically close to this one.

    Replaces the same-department listing that used to fill this panel.
    Department is neither a filter nor a boost: two projects from different
    departments can be closely related, and two from the same department
    routinely are not. An empty list is a real answer.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise ValidationError({"detail": "Project not found."})

        rows = similar_projects(project)
        explanations = shared_concepts(project, [row["project"] for row in rows])

        # Drop candidates the repository cannot justify: clearing the
        # embedding threshold means the vectors are close, not that there is a
        # reason a reader can check. Retrieval, threshold, ordering,
        # self-exclusion and the cap stay with `similar_projects`; surviving
        # rows keep their order.
        #
        # Skipped when the corpus is too small to judge term rarity, where an
        # empty explanation means "cannot tell" rather than "not related".
        if explanations_available():
            rows = [row for row in rows if explanations.get(row["project"].pk)]
        return success_response(
            data=[_present(row, request, explanations) for row in rows],
            message="Similar projects retrieved successfully.",
        )


class SimilarWorkCheckView(APIView):
    """Compare a proposed idea against the repository.

    Concept first. The only required input is a plain description of the
    idea; a title and a longer description are optional. Requiring a title,
    an abstract and a keyword list, as this endpoint first did, meant a
    student had to write most of a proposal before they could ask whether
    the idea already existed.

    This reports conceptual overlap. It is not a plagiarism check, and the
    wording it returns is deliberately non-committal: embedding similarity
    cannot establish copying.

    Nothing about the proposal is stored or logged.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        concept = (request.data.get("concept") or "").strip()
        title = (request.data.get("title") or "").strip()
        description = (request.data.get("description") or "").strip()

        if not concept and not title:
            raise ValidationError(
                {"concept": "Describe the project idea you want to check."}
            )
        if len(concept) > MAX_CONCEPT:
            raise ValidationError(
                {"concept": f"Keep the description under {MAX_CONCEPT} characters."}
            )
        if len(title) > MAX_TITLE:
            raise ValidationError(
                {"title": f"Keep the title under {MAX_TITLE} characters."}
            )
        if len(description) > MAX_CONCEPT:
            raise ValidationError(
                {"description": f"Keep this under {MAX_CONCEPT} characters."}
            )

        result = check_concept(
            concept=concept, title=title, description=description
        )
        closest = result["closest_below_threshold"]

        # The reader's own words are what the shared subject matter is drawn
        # against. Nothing about them is stored; they are analysed in memory
        # for this response only.
        described = " ".join(filter(None, [title, concept, description]))
        rows = result["strong"] + result["possible"]
        explanations = concept_shared_concepts(
            described, [row["project"] for row in rows]
        )

        return success_response(
            data={
                # Whether closely related work exists, as a fact about the
                # threshold rather than a score. The interface needs to
                # distinguish three outcomes and nothing finer than that.
                "threshold_met": result["threshold_met"],
                # `strong` is presented plainly; `possible` is shown
                # separately and labelled, because that range carries noise as
                # well as genuine matches the strong cut-off misses.
                "strong": [
                    _present(row, request, explanations) for row in result["strong"]
                ],
                "possible": [
                    _present(row, request, explanations) for row in result["possible"]
                ],
                # Deliberately carries no explanation. It is below the
                # threshold, so there is by definition nothing to say about
                # what it shares with the idea, and offering terms here would
                # dress up a non-match as a match.
                "closest_below_threshold": (
                    _present(closest, request, {}) if closest else None
                ),
            },
            message="Similarity check completed.",
            status=status.HTTP_200_OK,
        )
