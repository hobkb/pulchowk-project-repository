"""Triggering the search indexing of a project.

Two indexes have to be current before a project is findable: the lexical
`search_vector` and the semantic embedding. The save signal keeps both in step
for ordinary edits, but a workflow that writes a project in many steps -- a
publication, a bundle merge -- would queue one embedding task per step, each
loading the model, all producing the same vector.

`defer_indexing()` suppresses the per-save queueing across such a block, and
`queue_project_indexing()` queues it once at the end. The lexical vector is
unaffected: it is rebuilt inside the transaction on every save, because it
costs one UPDATE and needs no worker.

Both are safe to call more than once. The task compares the digest of the
embedding text against the digest stored with the vector and does nothing when
they match.
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
    """Queue one project's embedding once the transaction has committed.

    Committed first, because a worker must never be told to embed a row the
    database is about to roll back. A broker that is unreachable is not an
    error here: the project stays visible to `backfill_embeddings --report`,
    which is the repair path.
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
