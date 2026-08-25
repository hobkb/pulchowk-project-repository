"""Similar Projects and the Similar Work Check.

Two layers, kept apart on purpose.

Retrieval works in raw cosine, because that is what the vectors hold and what
the HNSW index orders by. Nothing here transforms a stored embedding, and
nothing re-ranks on a derived score.

Interpretation is applied afterwards. A raw cosine is not shown to a reader,
because in this corpus it does not mean what it looks like: every project is
an undergraduate engineering report from one department in a similar house
style, so two unrelated projects still score around 0.64 and reach 0.82 at
the ninety-ninth percentile. A reader is given a band, and the percentile the
score occupies in this corpus, which is a statement about relative position
rather than about percentage of shared content.

Thresholds and bands come from settings.SIMILARITY; the percentile mapping
comes from the SimilarityCalibration row that `manage.py search_eval` writes.
Neither is hard-coded here.

Both features apply the same calibrated floor. Nearest is not the same as
related: with a small corpus the nearest neighbour of anything is some
project, and showing it regardless of score is how a similarity check ends up
listing four unrelated projects under a percentile that reads like a
percentage.
"""

from django.conf import settings
from django.db import connection

from repository.embedding import active_model_version, embed_concept
from repository.models import Project, SimilarityCalibration


def _config():
    return settings.SIMILARITY


def band_for(score, bands):
    """The first band whose threshold the score meets.

    Bands are ordered highest first and the last entry is the floor, with a
    threshold of None. Returns (key, label).
    """
    for threshold, key, label in bands:
        if threshold is None or score >= threshold:
            return key, label
    last = bands[-1]
    return last[1], last[2]


def calibration(model_version=None):
    """The stored calibration for a model, or None if never measured."""
    version = model_version or active_model_version()
    return SimilarityCalibration.objects.filter(model_version=version).first()


def percentile_for(score, calib=None):
    """Where a raw cosine sits in the measured random-pair distribution.

    None when no calibration has been recorded, which callers must treat as
    "unknown" rather than as zero.
    """
    calib = calib if calib is not None else calibration()
    if calib is None:
        return None
    return calib.percentile_for(score)


def interpret(score, bands, calib=None):
    """Turn one raw cosine into what a reader is shown.

    `score` stays in the payload for internal callers; the public serializer
    is responsible for dropping it.
    """
    key, label = band_for(score, bands)
    return {
        "score": score,
        "band": key,
        "band_label": label,
        "percentile": percentile_for(score, calib),
    }


def _neighbours(vector_sql_source, params, *, exclude_project_id, limit, min_score,
                model_version):
    """Nearest projects by raw cosine, above a floor.

    One query. `vector_sql_source` is the SQL expression that yields the
    query vector, so the same routine serves both a stored project vector and
    a freshly encoded proposal without materialising either in Python.
    """
    exclusion = "AND e.project_id <> %s" if exclude_project_id is not None else ""
    sql = f"""
        SELECT e.project_id, 1 - (e.embedding <=> {vector_sql_source}) AS score
        FROM project_embeddings e
        WHERE e.model_version = %s
          {exclusion}
          AND 1 - (e.embedding <=> {vector_sql_source}) >= %s
        ORDER BY e.embedding <=> {vector_sql_source}
        LIMIT %s
    """
    args = list(params) + [model_version]
    if exclude_project_id is not None:
        args.append(exclude_project_id)
    args += list(params) + [min_score] + list(params) + [limit]

    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        return [(row[0], float(row[1])) for row in cursor.fetchall()]


def _vector_literal(vector):
    return "[" + ",".join("%.7f" % v for v in vector) + "]"


def _attach_projects(pairs, bands, calib):
    """Turn (project_id, score) pairs into interpreted rows, preserving the
    similarity order that the database returned."""
    if not pairs:
        return []
    ids = [pid for pid, _ in pairs]
    projects = {
        p.pk: p
        for p in Project.objects.filter(pk__in=ids).select_related("department")
    }
    rows = []
    for pid, score in pairs:
        project = projects.get(pid)
        if project is None:
            continue
        row = interpret(score, bands, calib)
        row["project"] = project
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Similar Projects
# ---------------------------------------------------------------------------
def similar_projects(project, *, limit=None, min_score=None, model_version=None):
    """Projects genuinely close to this one.

    Excludes the project itself, applies the calibrated floor, and caps the
    result. An empty list is a real answer: when nothing clears the floor the
    honest outcome is to show nothing rather than to pad the list with the
    nearest unrelated work, which is what the department-based list it
    replaces used to do.
    """
    config = _config()
    version = model_version or active_model_version()
    limit = config["SIMILAR_PROJECTS_LIMIT"] if limit is None else limit
    min_score = config["SIMILAR_PROJECTS_MIN"] if min_score is None else min_score

    source = (
        "(SELECT embedding FROM project_embeddings "
        "WHERE project_id = %s AND model_version = %s)"
    )
    params = [project.pk, version]
    pairs = _neighbours(
        source,
        params,
        exclude_project_id=project.pk,
        limit=limit,
        min_score=min_score,
        model_version=version,
    )
    return _attach_projects(pairs, config["SIMILAR_PROJECTS_BANDS"], calibration(version))


# ---------------------------------------------------------------------------
# Similar Work Check
# ---------------------------------------------------------------------------
def check_concept(*, concept, title="", description="", model_version=None):
    """Compare a proposed idea against the repository.

    Concept first: one or two sentences describing the idea is a complete
    input. A title and a longer description are accepted but neither is
    required, because a student weighing up an idea rarely has them yet.

    A concept is a weaker signal than a full document, so the
    project-to-project cut-off of 0.78 is wrong for it: measured over ninety
    known-item concept queries it surfaces only 72% of the projects the
    concepts were written from. Simply lowering it does not work either. A
    concept describing work that is in the repository scored 0.7402 against
    it, while a concept describing work that plainly is not there scored
    0.7738 against its nearest project -- the absent one scored higher. No
    absolute number in that range separates them.

    What separates them is whether the best match stands clear of the field.
    The genuine one led its runner-up by 0.1186, the absent one by 0.0427. So
    below the strong cut-off exactly one project is offered, and only when it
    clears the floor and leads the next candidate by the configured margin.
    At that margin the rule lifts recall from 72% to 78%, and the rows it adds
    are right about five times in eight; settings.SIMILARITY carries the full
    measurement. It is labelled as possible rather than shown beside the
    confident matches.

    When the leading scores sit in a flat cluster the corpus holds nothing in
    particular and nothing is listed. That is the point of the rule: the
    nearest neighbour of any idea is always some project, and showing it
    regardless of how it compares to the rest is how a check ends up padding
    the screen with unrelated work.

    When neither band has anything, the single closest project is returned
    flagged as below the threshold, so the answer is "nothing related, and
    here is the nearest thing" rather than an empty screen.

    Nothing about the proposal is stored or logged.
    """
    config = _config()
    version = model_version or active_model_version()
    bands = config["CHECK_BANDS_CONCEPT"]

    vector, _text = embed_concept(
        concept=concept, title=title, description=description
    )
    if vector is None:
        return {
            "strong": [], "possible": [], "closest_below_threshold": None,
            "overall_band": None, "overall_band_label": None,
            "threshold_met": False,
        }

    literal = _vector_literal(vector)
    calib = calibration(version)

    def fetch(minimum, limit):
        return _attach_projects(
            _neighbours(
                "%s::vector", [literal],
                exclude_project_id=None, limit=limit,
                min_score=minimum, model_version=version,
            ),
            bands, calib,
        )

    strong = fetch(config["CONCEPT_STRONG_MIN"], config["CONCEPT_STRONG_LIMIT"])

    # The possible band exists only to recover the case where nothing cleared
    # the strong cut-off, and it holds at most one project: the standout test
    # is a statement about the leader against the rest of the field, so it has
    # no meaning applied to a second or third row.
    possible = []
    if not strong:
        leaders = fetch(-1.0, 2)
        if (
            len(leaders) == 2
            and leaders[0]["score"] >= config["CONCEPT_POSSIBLE_MIN"]
            and leaders[0]["score"] - leaders[1]["score"]
            >= config["CONCEPT_POSSIBLE_MARGIN"]
        ):
            possible = [leaders[0]]

    if strong or possible:
        leader = strong[0] if strong else possible[0]
        return {
            "strong": strong,
            "possible": possible,
            "closest_below_threshold": None,
            "overall_band": leader["band"],
            "overall_band_label": leader["band_label"],
            "threshold_met": bool(strong),
        }

    nearest = fetch(-1.0, 1)
    floor = bands[-1]
    return {
        "strong": [],
        "possible": [],
        "closest_below_threshold": nearest[0] if nearest else None,
        "overall_band": floor[1],
        "overall_band_label": floor[2],
        "threshold_met": False,
    }
