"""Background maintenance of the semantic index."""

from celery import shared_task

from repository.embedding import generate_for
from repository.models import Project


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def embed_project(self, project_id):
    """Bring one project's embedding up to date.

    Idempotent by construction: `generate_for` compares the digest of the
    embedding text against the digest stored with the vector and does nothing
    when they match, so a duplicate task, a retry and a redundant signal all
    cost one hash.

    A permanent failure leaves no row behind, which is deliberate: the
    project then reads as `missing` to `backfill_embeddings --report`, and
    the repair path is the same command that did the initial backfill.
    """
    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        return {"skipped": "project no longer exists"}
    stats = generate_for([project])
    return stats.as_dict()


@shared_task
def embed_projects(project_ids):
    """Embed a batch in one task.

    Used after a bundle import, where queueing one task per project would
    mean a hundred model loads for a hundred projects.
    """
    projects = list(Project.objects.filter(pk__in=list(project_ids)))
    if not projects:
        return {"skipped": "no projects"}
    return generate_for(projects).as_dict()
