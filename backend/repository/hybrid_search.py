"""Hybrid retrieval: lexical relevance fused with semantic similarity.

Two branches rank the same filtered candidate set and are combined by
weighted Reciprocal Rank Fusion:

    score(p) = w_lex / (k + rank_lex(p)) + w_sem / (k + rank_sem(p))

Results are the union of what the branches retrieved and nothing else -- a
project neither branch returned never enters fusion. This is what stops a
small corpus from answering every query with its whole contents.

Rank fusion rather than score blending: `ts_rank_cd` and cosine are not on
comparable scales, and cosine here does not start at zero (two unrelated
projects score about 0.64). Blending would need recalibrating as the corpus
grows; RRF reads only positions.

A project absent from one branch contributes nothing from it, so a purely
lexical query (a batch number, a surname) is carried by the lexical branch
alone and needs no threshold or normalisation.

Filters are applied to the candidate set before either branch runs, so a
filtered-out project cannot consume a candidate slot.
"""

import re

from django.conf import settings
from django.db import connection

from repository.embedding import active_model_version, embed_query


def _normalise_title(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def lexical_ranking(queryset, text, limit):
    """Ordered project ids from the full-text index."""
    from repository.search_index import lexical_queryset

    return list(
        lexical_queryset(queryset, text).values_list("id", flat=True)[:limit]
    )


def semantic_ranking(queryset, text, limit, model_version=None, min_score=None):
    """Ordered project ids by cosine against the query embedding.

    The query is encoded with the model's query convention. That matters:
    bge is trained asymmetrically, and encoding a query as though it were a
    passage measurably degrades retrieval. Project-to-project comparison in
    `repository.similarity` deliberately does not use it, because there both
    sides are documents.

    `min_score` decides candidacy. Without it this returns `limit` projects
    whatever their scores, because that is what k-nearest-neighbour means,
    and over a small corpus that is most of the repository. See
    SEARCH["SEMANTIC_MIN_SCORE"] for how the default was measured.
    """
    vector = embed_query(text)
    if vector is None:
        return []

    version = model_version or active_model_version()
    floor = settings.SEARCH["SEMANTIC_MIN_SCORE"] if min_score is None else min_score
    candidate_ids = list(queryset.values_list("id", flat=True))
    if not candidate_ids:
        return []

    literal = "[" + ",".join("%.7f" % v for v in vector) + "]"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT project_id
            FROM project_embeddings
            WHERE model_version = %s
              AND project_id = ANY(%s)
              AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            [version, candidate_ids, literal, floor, literal, limit],
        )
        return [row[0] for row in cursor.fetchall()]


def reciprocal_rank_fusion(rankings, *, k, weights=None):
    """Fuse ranked id lists into one ordered list.

    Returns the fused order and the per-branch positions, which the
    evaluation harness reads to attribute contribution.
    """
    weights = weights or {}
    scores, contributions = {}, {}
    for branch, ids in rankings.items():
        weight = weights.get(branch, 1.0)
        for position, project_id in enumerate(ids, start=1):
            scores[project_id] = scores.get(project_id, 0.0) + weight / (k + position)
            contributions.setdefault(project_id, {})[branch] = position
    ordered = sorted(scores, key=lambda pid: (-scores[pid], pid))
    return ordered, contributions


def hybrid_ranking(queryset, text, *, k=None, weights=None, pool=None,
                   model_version=None):
    """The fused ordering for one query over one filtered candidate set."""
    config = settings.SEARCH
    k = config["RRF_K"] if k is None else k
    weights = weights or {
        "lexical": config["LEXICAL_WEIGHT"],
        "semantic": config["SEMANTIC_WEIGHT"],
    }
    lexical_pool = pool or config["LEXICAL_POOL"]
    semantic_pool = pool or config["SEMANTIC_POOL"]

    lexical = lexical_ranking(queryset, text, lexical_pool)
    semantic = semantic_ranking(queryset, text, semantic_pool, model_version)

    ordered, contributions = reciprocal_rank_fusion(
        {"lexical": lexical, "semantic": semantic}, k=k, weights=weights
    )

    ordered = _pin_exact_title(queryset, text, ordered)
    return ordered, {"lexical": lexical, "semantic": semantic,
                     "contributions": contributions}


def _pin_exact_title(queryset, text, ordered):
    """Move an exact normalised title match to the front.

    RRF positions one and two differ by about 1.6% (1/61 vs 1/62), so a
    project whose title is exactly the query can be displaced by one placed
    mid-list in both branches. Pinning avoids a tunable score bonus that
    would distort everything below it.
    """
    normalised = _normalise_title(text)
    if not normalised:
        return ordered
    exact = list(
        queryset.filter(title__iexact=normalised).values_list("id", flat=True)[:1]
    )
    if not exact:
        return ordered
    pinned = exact[0]
    return [pinned] + [pid for pid in ordered if pid != pinned]
