"""Index maintenance on write.

Hooking every path that creates or changes a project means four call sites
today and an unknown number tomorrow; the bundle importer already
demonstrated what happens when one is missed.

The two indexes are scheduled differently, and the difference matters. The
lexical vector is rebuilt in the same transaction as the write: a rollback
must discard the index update with the row, and deferring to commit would
make every project created inside a test invisible to search, since a test's
wrapping transaction never commits. The embedding is queued on commit
instead, because a worker in another process must never be told to embed a
row that is about to roll back.

Writes that bypass the ORM (`bulk_create`, raw SQL, data migrations) emit no
signal; `backfill_search_vectors` and `backfill_embeddings` repair those.
"""

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from repository.models import Project, ProjectKeyword, ProjectPerson


def rebuild_lexical_index(project_id):
    """Recompute the project's search vector in the current transaction."""
    project = (
        Project.objects.filter(pk=project_id)
        .select_related("department")
        .prefetch_related("project_keywords__keyword", "project_people__person")
        .first()
    )
    if project is None:
        return

    from repository.search_index import update_search_vector

    # `.update()` does not emit post_save, so this cannot recurse.
    update_search_vector(project)


def queue_embedding(project_id):
    from repository.tasks import embed_project

    try:
        embed_project.delay(project_id)
    except Exception:  # noqa: BLE001
        # A down broker must not fail the save; the project is left stale for
        # `backfill_embeddings --report` to repair.
        pass


def schedule_refresh(project_id):
    rebuild_lexical_index(project_id)

    # Read the deferral flag at save time, not inside the callback: the
    # callback runs on commit, by which point a defer_indexing() block has
    # exited and the flag would read False again.
    if getattr(settings, "EMBEDDING_DEFER", False):
        return

    transaction.on_commit(lambda: queue_embedding(project_id))


@receiver(post_save, sender=Project, dispatch_uid="repository.refresh_project_index")
def project_saved(sender, instance, **kwargs):
    schedule_refresh(instance.pk)


@receiver(post_save, sender=ProjectKeyword, dispatch_uid="repository.keyword_added")
@receiver(post_delete, sender=ProjectKeyword, dispatch_uid="repository.keyword_removed")
def keyword_changed(sender, instance, **kwargs):
    # Keywords feed both the embedding text and weight B of the lexical
    # vector, so a change makes both stale.
    schedule_refresh(instance.project_id)


@receiver(post_save, sender=ProjectPerson, dispatch_uid="repository.person_added")
@receiver(post_delete, sender=ProjectPerson, dispatch_uid="repository.person_removed")
def person_changed(sender, instance, **kwargs):
    # People appear in weight D of the lexical vector only, not in the
    # embedding text, so the embedding task will find its digest unchanged.
    schedule_refresh(instance.project_id)
