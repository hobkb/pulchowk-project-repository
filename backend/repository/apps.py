from django.apps import AppConfig


class RepositoryConfig(AppConfig):
    name = "repository"

    def ready(self):
        # Index maintenance signals. Imported here rather than at module
        # level so the handlers are registered exactly once, after the app
        # registry is populated.
        from repository import signals  # noqa: F401

        self._prewarm_embedding_model()

    @staticmethod
    def _prewarm_embedding_model():
        """Load the embedding model at startup rather than on first use.

        In a daemon thread, so a slow or failing model load delays neither
        startup nor the first request. A failure here is not fatal: the model
        simply loads lazily on the first query, which is the behaviour this
        avoids rather than depends on.
        """
        from django.conf import settings

        if not settings.EMBEDDING.get("PREWARM"):
            return

        import threading

        def _load():
            try:
                from repository.embedding import get_backend

                get_backend().encode_queries(["warm up"])
            except Exception:  # noqa: BLE001
                # Deliberately silent. The next real query will retry the
                # load and surface any genuine problem there.
                pass

        threading.Thread(target=_load, name="embedding-prewarm", daemon=True).start()
