"""Populate the full-text search vectors.

Needed once after the tsvector column is introduced, and available afterwards
as a repair path. Ordinary operation keeps the vector current through the
save signal, so a second run finds nothing to change.

Output is counts only.
"""

import time

from django.core.management.base import BaseCommand

from repository.models import Project
from repository.search_index import update_search_vector


class Command(BaseCommand):
    help = "Rebuild the lexical search vectors for projects."

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=str, default=None)
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Only projects whose vector has never been built.",
        )

    def handle(self, *args, **options):
        queryset = Project.objects.all().order_by("id")
        if options["project_id"]:
            queryset = queryset.filter(id=options["project_id"])
        if options["missing_only"]:
            queryset = queryset.filter(search_vector__isnull=True)

        projects = queryset.prefetch_related(
            "project_keywords__keyword", "project_people__person"
        ).select_related("department")

        started = time.perf_counter()
        count = 0
        for project in projects:
            update_search_vector(project)
            count += 1
        elapsed = time.perf_counter() - started

        total = Project.objects.count()
        indexed = Project.objects.exclude(search_vector__isnull=True).count()

        self.stdout.write("")
        self.stdout.write("Lexical search index")
        self.stdout.write("-" * 44)
        self.stdout.write("  rebuilt            : %d" % count)
        self.stdout.write("  indexed / total    : %d / %d" % (indexed, total))
        self.stdout.write("  elapsed            : %.1f s" % elapsed)
        self.stdout.write("")
