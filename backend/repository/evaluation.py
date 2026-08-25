"""Retrieval evaluation: query sets, metrics and the branch comparison.

Ground truth
------------
The repository holds no relevance judgements. Nothing records that a given
query ought to return a given project, and none is invented here. What is
available instead is *known-item retrieval*: a query is derived from a
project, so the one correct answer is known without any labelling.

That supports honest Precision@1, Recall@k, MRR and nDCG, and it is enough to
compare lexical, semantic and fused ranking against each other. It is not a
measurement of general relevance, and it must not be reported as one: it says
whether the system can find a specific project from a description of it, not
whether the other nine results were any good.

Three query strategies, because each favours a different branch and reporting
only one would be misleading:

    title          the exact title. Trivial for lexical search; included to
                   confirm exact-match behaviour rather than to compare.
    keywords       the project's own keyword list. Wording that overlaps the
                   document but is not the title.
    title_subset   a contiguous run of words from the middle of the title,
                   which is closer to how somebody half-remembers a project.

A labelled query set can be supplied instead once one exists, as JSON:

    [{"query": "...", "relevant_ids": [12, 41]}, ...]

kept outside the database so evaluation data never mixes with project data.
"""

import json
import math
import random

from repository.models import Project, ProjectKeyword


def _tokens(text):
    return [t for t in (text or "").split() if t]


def build_known_item_queries(strategy, *, limit=None, seed=12345):
    """(query, relevant_ids) pairs derived from projects.

    The query text is returned to the caller for encoding and is never
    printed by the harness.
    """
    rng = random.Random(seed)
    projects = list(
        Project.objects.filter(status="Published").only("id", "title").order_by("id")
    )
    if limit:
        projects = projects[:limit]

    keyword_map = {}
    if strategy == "keywords":
        rows = ProjectKeyword.objects.filter(
            project__in=projects
        ).select_related("keyword")
        for row in rows:
            keyword_map.setdefault(row.project_id, []).append(row.keyword.name)

    queries = []
    for project in projects:
        if strategy == "title":
            text = project.title
        elif strategy == "keywords":
            words = keyword_map.get(project.pk, [])
            text = " ".join(words)
        elif strategy == "title_subset":
            words = _tokens(project.title)
            if len(words) <= 4:
                text = " ".join(words)
            else:
                span = min(4, len(words))
                start = rng.randrange(0, len(words) - span + 1)
                text = " ".join(words[start : start + span])
        else:
            raise ValueError("unknown strategy: %s" % strategy)

        if text and text.strip():
            queries.append((text.strip(), {project.pk}))
    return queries


def load_query_set(path):
    """A labelled query set from disk, if one has been curated."""
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [(row["query"], set(row["relevant_ids"])) for row in payload]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def evaluate_ranking(ranked_ids, relevant_ids, k=10):
    """Metrics for one query's ranked result list."""
    top = ranked_ids[:k]
    hits = [i for i, pid in enumerate(top, start=1) if pid in relevant_ids]

    first_rank = hits[0] if hits else None
    precision_at_1 = 1.0 if top and top[0] in relevant_ids else 0.0
    recall_at_k = len(set(top) & relevant_ids) / len(relevant_ids) if relevant_ids else 0.0
    reciprocal_rank = 1.0 / first_rank if first_rank else 0.0

    dcg = sum(1.0 / math.log2(rank + 1) for rank in hits)
    ideal = sum(
        1.0 / math.log2(i + 1) for i in range(1, min(len(relevant_ids), k) + 1)
    )
    ndcg = dcg / ideal if ideal else 0.0

    return {
        "p_at_1": precision_at_1,
        "recall_at_k": recall_at_k,
        "reciprocal_rank": reciprocal_rank,
        "ndcg_at_k": ndcg,
        "found": 1.0 if first_rank else 0.0,
    }


def aggregate(per_query):
    """Mean of each metric across queries."""
    if not per_query:
        return {"queries": 0}
    keys = per_query[0].keys()
    out = {"queries": len(per_query)}
    for key in keys:
        out[key] = round(sum(row[key] for row in per_query) / len(per_query), 4)
    return out
