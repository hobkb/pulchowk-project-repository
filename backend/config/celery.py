import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# Load the embedding model when the worker comes up, so the first ingestion
# task after a restart does not pay for it. Guarded by the same setting as the
# web process; see EMBEDDING["PREWARM"].
from celery.signals import worker_ready  # noqa: E402


@worker_ready.connect
def _prewarm_embedding_model(**_kwargs):
    from django.conf import settings

    if not settings.EMBEDDING.get("PREWARM"):
        return
    try:
        from repository.embedding import get_backend

        get_backend().encode_documents(["warm up"])
    except Exception:  # noqa: BLE001
        pass
