"""
Shared scoring engine for weighted positive/negative keyword ontologies.

Both domain_classifier.py (which domain does this project belong to) and
task_classifier.py (what kind of AI/CS task is it doing) score text against
a dict of {category: {"positive": {term: weight}, "negative": {term: weight}}}
the exact same way. Previously that scoring logic was duplicated -- this is
the one copy both import.

Scoring approach: positive term weights get diminishing returns per repeat
occurrence (so one word repeated 20 times can't single-handedly dominate).
Negative term weights are a flat penalty triggered by presence, not
frequency-scaled -- a domain's negative list exists to veto categories that
share superficial vocabulary with a totally different field (e.g. "pixel"
showing up in an audio-processing paper's one aside about a spectrogram
plot shouldn't make it get classified as Computer Vision).
"""

from collections import defaultdict


def score_ontology(text: str, ontology: dict) -> dict:
    """
    Returns {category: score} for every category whose net score (positive
    minus negative) came out above zero. Categories that scored <= 0 aren't
    included at all.
    """
    text_lower = text.lower()
    scores = defaultdict(float)

    for category, rules in ontology.items():
        pos_score = 0.0
        for term, weight in rules.get("positive", {}).items():
            occurrences = text_lower.count(term)
            if occurrences > 0:
                pos_score += weight * (1 + (occurrences - 1) * 0.2)

        neg_score = 0.0
        for term, weight in rules.get("negative", {}).items():
            if text_lower.count(term) > 0:
                neg_score += weight * 3.0

        final_score = pos_score - neg_score
        if final_score > 0:
            scores[category] = final_score

    return dict(scores)


def rank_categories(scores: dict, top_k: int = None) -> list:
    """
    Turns a {category: score} dict into a [(category, score), ...] list
    sorted by score descending. Ties broken by category name for stable
    output. Optionally capped to the top_k highest scorers.
    """
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))

    if top_k is not None:
        ranked = ranked[:top_k]

    return ranked


def classify(text: str, ontology: dict, default: str, logger=None, label: str = "Category") -> str:
    """
    Picks the single highest-scoring category, or `default` if nothing
    scored above zero.
    """
    scores = score_ontology(text, ontology)
    if not scores:
        return default

    assigned = max(scores, key=scores.get)
    if logger:
        logger.info(f"{label} Scores: {scores} -> Assigned: '{assigned}'")
    return assigned


def classify_with_scores(
    text: str,
    ontology: dict,
    default: str,
    logger=None,
    label: str = "Category",
    top_k: int = 5,
):
    """
    Same decision as classify(), but also returns the full ranked list of
    every category that scored above zero (capped at top_k), so a caller
    can persist secondary/related categories instead of forcing a project
    into exactly one bucket.

    Returns:
        (assigned_category, ranked) where ranked is
        [(category, score), ...] sorted descending. `ranked` is [] when
        nothing scored above zero (assigned_category is `default` then).
    """
    scores = score_ontology(text, ontology)
    ranked = rank_categories(scores, top_k=top_k)

    if not ranked:
        if logger:
            logger.info(f"{label} Scores: {{}} -> Assigned: '{default}' (no match)")
        return default, []

    assigned = ranked[0][0]
    if logger:
        logger.info(f"{label} Scores: {dict(ranked)} -> Assigned: '{assigned}'")
    return assigned, ranked
