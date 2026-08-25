"""Generating, refreshing and auditing project embeddings.

The freshness rule is one line: an embedding is current when a row exists for
the active model version whose `source_hash` equals the digest of the text the
current representation produces. Everything else follows from it.

    missing   no row for the active model version
    stale     a row exists but the digest no longer matches
    current   digest matches

Because the digest covers the built text, this responds to a title edit, an
abstract correction, a keyword being added or removed, and to a change in the
representation itself, without anyone maintaining a list of watched fields.

Nothing in this module returns or logs project text. Callers receive vectors,
counts and identifiers.
"""

from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction

from repository.models import Project, ProjectEmbedding

from .backends import get_backend
from .text import build_concept_text, build_text, fingerprint


def active_model_version():
    return settings.EMBEDDING["MODEL_VERSION"]


@dataclass
class GenerationStats:
    """Aggregate outcome of a generation run. Counts only, by design."""

    examined: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_empty: int = 0
    failed: int = 0
    failure_types: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "examined": self.examined,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped_empty": self.skipped_empty,
            "failed": self.failed,
            "failure_types": dict(self.failure_types),
        }


def _keyword_map(projects):
    """Keywords for many projects in one query, to keep batch generation from
    issuing a query per project."""
    from repository.models import ProjectKeyword

    mapping = {p.pk: [] for p in projects}
    rows = ProjectKeyword.objects.filter(project__in=projects).select_related("keyword")
    for row in rows:
        mapping.setdefault(row.project_id, []).append(row.keyword.name)
    return mapping


def plan_for(projects, *, force=False):
    """Work out what each project needs without embedding anything.

    Returns (to_embed, unchanged_ids, empty_ids) where `to_embed` is a list of
    (project, text, digest) triples.
    """
    version = active_model_version()
    projects = list(projects)
    keywords = _keyword_map(projects)

    existing = {
        e.project_id: e
        for e in ProjectEmbedding.objects.filter(
            project__in=projects, model_version=version
        )
    }

    to_embed, unchanged, empty = [], [], []
    for project in projects:
        text = build_text(project, keywords.get(project.pk, []))
        if not text.strip():
            empty.append(project.pk)
            continue
        digest = fingerprint(text)
        current = existing.get(project.pk)
        if current is not None and current.source_hash == digest and not force:
            unchanged.append(project.pk)
            continue
        to_embed.append((project, text, digest))
    return to_embed, unchanged, empty


def generate_for(projects, *, force=False, stats=None):
    """Embed the projects that need it and write the rows.

    Idempotent: running it twice in a row leaves the second run with nothing
    to do. A failure to encode one batch is recorded and does not abort the
    others, so a partial run still makes progress and the remainder stays
    visible to `audit()`.
    """
    stats = stats or GenerationStats()
    projects = list(projects)
    stats.examined += len(projects)

    to_embed, unchanged, empty = plan_for(projects, force=force)
    stats.unchanged += len(unchanged)
    stats.skipped_empty += len(empty)
    if not to_embed:
        return stats

    backend = get_backend()
    version = backend.model_version

    try:
        vectors = backend.encode_documents([t for _, t, _ in to_embed])
    except Exception as exc:  # noqa: BLE001
        # Only the exception class is recorded: a model or file error can
        # embed a path, and a tokenizer error can embed the text itself.
        stats.failed += len(to_embed)
        name = type(exc).__name__
        stats.failure_types[name] = stats.failure_types.get(name, 0) + 1
        return stats

    with transaction.atomic():
        for (project, _text, digest), vector in zip(to_embed, vectors):
            _, created = ProjectEmbedding.objects.update_or_create(
                project=project,
                model_version=version,
                defaults={"source_hash": digest, "embedding": vector},
            )
            if created:
                stats.created += 1
            else:
                stats.updated += 1
    return stats


def embed_query(text):
    """Vector for a search query, using the model's query convention."""
    vectors = get_backend().encode_queries([text])
    return vectors[0] if vectors else None


def embed_concept(*, concept, title="", description=""):
    """Vector for a proposed idea in the Similar Work Check.

    Encoded with the model's *query* convention, not the document one. bge is
    trained asymmetrically, and a one-line idea is a query against a corpus of
    documents, not a document being compared to documents. Measured over this
    corpus the two conventions land in almost the same place (own-project
    median 0.830 against 0.845), so the calibrated bands still apply, but the
    query form is the correct one for this direction.

    Nothing is persisted.
    """
    text = build_concept_text(concept=concept, title=title, description=description)
    if not text.strip():
        return None, text
    vectors = get_backend().encode_queries([text])
    return (vectors[0] if vectors else None), text


def audit(queryset=None):
    """Coverage of the corpus under the active model version.

    Returns counts and id lists only; used by the backfill command and by the
    evaluation harness.
    """
    version = active_model_version()
    projects = list(queryset if queryset is not None else Project.objects.all())
    to_embed, unchanged, empty = plan_for(projects, force=False)

    have_row = set(
        ProjectEmbedding.objects.filter(
            project__in=projects, model_version=version
        ).values_list("project_id", flat=True)
    )
    to_embed_ids = [p.pk for p, _, _ in to_embed]
    missing = [pk for pk in to_embed_ids if pk not in have_row]
    stale = [pk for pk in to_embed_ids if pk in have_row]

    return {
        "model_version": version,
        "total": len(projects),
        "current": len(unchanged),
        "missing": len(missing),
        "stale": len(stale),
        "no_embeddable_text": len(empty),
        "missing_ids": missing,
        "stale_ids": stale,
        "no_text_ids": empty,
    }
