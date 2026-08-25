"""Keeping a project in both indexes without anyone remembering to.

Two indexes have to stay current: the lexical `search_vector` and the
semantic embedding. Hooking every write path that can create or change a
project means four call sites today and an unknown number tomorrow, and the
bundle importer has already demonstrated what happens when one of them is
missed. A signal cannot be forgotten by a new code path.

The two are scheduled differently, and the difference matters.

The lexical vector is rebuilt immediately, in the same transaction as the
write that triggered it. It is one UPDATE over text already in memory, and
being in the transaction means a rollback discards the index update along
with the row it described. Deferring it to commit would also make every
project created inside a test invisible to search, because a test's wrapping
transaction never commits.

The embedding is queued on commit instead, because it is handed to another
process: a worker must never be told to embed a row that the database is
about to roll back.

Neither does anything expensive when nothing meaningful changed: the vector
rebuild is a single statement, and the embedding task compares digests
before it encodes.

A write that bypasses the ORM -- `bulk_create`, raw SQL, a data migration --
emits no signal and leaves the project unindexed. `backfill_search_vectors`
and `backfill_embeddings` are the repair for that.
"""

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from repository.models import Project, ProjectKeyword, ProjectPerson


def rebuild_lexical_index(project_id):
    """Recompute the project's search vector, in the current transaction."""
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
        # A broker that is down must not make saving a project fail. The
        # project is simply left stale, which `backfill_embeddings --report`
        # surfaces and repairs.
        pass


def schedule_refresh(project_id):
    rebuild_lexical_index(project_id)

    # The deferral flag is read here, at save time, not inside the callback.
    # The callback runs on commit, by which point a `defer_indexing()` block
    # has long since exited and the flag would read False again -- so a
    # publication would queue one task per intermediate save after all, which
    # is exactly what deferring exists to prevent.
    if getattr(settings, "EMBEDDING_DEFER", False):
        return

    transaction.on_commit(lambda: queue_embedding(project_id))


@receiver(post_save, sender=Project, dispatch_uid="repository.refresh_project_index")
def project_saved(sender, instance, **kwargs):
    schedule_refresh(instance.pk)


@receiver(post_save, sender=ProjectKeyword, dispatch_uid="repository.keyword_added")
@receiver(post_delete, sender=ProjectKeyword, dispatch_uid="repository.keyword_removed")
def keyword_changed(sender, instance, **kwargs):
    # Keywords are part of both the embedding text and weight B of the
    # lexical vector, so a change to them makes both stale.
    schedule_refresh(instance.project_id)


@receiver(post_save, sender=ProjectPerson, dispatch_uid="repository.person_added")
@receiver(post_delete, sender=ProjectPerson, dispatch_uid="repository.person_removed")
def person_changed(sender, instance, **kwargs):
    # People appear in weight D of the lexical vector. They are deliberately
    # not part of the embedding text, so this only refreshes the vector; the
    # embedding task will find its digest unchanged and do nothing.
    schedule_refresh(instance.project_id)
