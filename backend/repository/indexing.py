"""Triggering search indexing for a project.

A workflow that writes a project in many steps -- a publication, a bundle
merge -- would otherwise queue one embedding task per save, each loading the
model to produce the same vector. `defer_indexing()` suppresses per-save
queueing across such a block; `queue_project_indexing()` queues once at the
end. Queueing is idempotent: the task compares text digests and skips when
unchanged.

Only the embedding is deferred. The lexical vector is rebuilt in-transaction
on every save, costing one UPDATE and no worker.
"""

from contextlib import contextmanager

from django.db import transaction
from django.test.utils import override_settings


@contextmanager
def defer_indexing():
    """Suppress per-save embedding tasks for the duration of the block."""
    with override_settings(EMBEDDING_DEFER=True):
        yield


def queue_project_indexing(project_id):
    """Queue one project's embedding after commit.

    On commit, because a worker must never be told to embed a row that is
    about to roll back. An unreachable broker is not fatal: the project
    remains visible to `backfill_embeddings --report`.
    """

    def _queue():
        from repository.tasks import embed_project

        try:
            embed_project.delay(project_id)
        except Exception:  # noqa: BLE001
            pass

    transaction.on_commit(_queue)


def queue_projects_indexing(project_ids):
    """Queue a batch, for importers that touched many projects."""
    ids = sorted(set(project_ids))
    if not ids:
        return

    def _queue():
        from repository.tasks import embed_projects

        try:
            embed_projects.delay(ids)
        except Exception:  # noqa: BLE001
            pass

    transaction.on_commit(_queue)
