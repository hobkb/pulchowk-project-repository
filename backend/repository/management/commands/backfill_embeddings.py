"""Generate project embeddings, and repair missing or stale ones.

This is the recovery and maintenance path. Normal operation generates
embeddings automatically when a project is saved; this command exists for the
initial backfill, for projects whose task failed, and for the sweep after a
model version change.

    python manage.py backfill_embeddings --report
    python manage.py backfill_embeddings
    python manage.py backfill_embeddings --missing-only
    python manage.py backfill_embeddings --force

Idempotent. A second run with no intervening change finds nothing to do,
because a project is only re-embedded when the digest of its embedding text
differs from the digest stored alongside its vector.

Output is counts, identifiers and timings. No project text is printed.
"""

import time

from django.core.management.base import BaseCommand

from repository.embedding import GenerationStats, active_model_version, audit, generate_for
from repository.models import Project


class Command(BaseCommand):
    help = "Generate or refresh project-level embeddings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--report",
            action="store_true",
            help="Show coverage and exit without embedding anything.",
        )
        parser.add_argument(
            "--missing-only",
            action="store_true",
            help="Embed only projects with no row for the active model.",
        )
        parser.add_argument(
            "--stale-only",
            action="store_true",
            help="Embed only projects whose stored digest no longer matches.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-embed every project even when its digest still matches.",
        )
        parser.add_argument(
            "--project-id",
            type=str,
            default=None,
            help="Limit the run to one project.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=32,
            help="Projects per encode call. Larger is faster and uses more memory.",
        )
        parser.add_argument(
            "--published-only",
            action="store_true",
            help="Restrict to Published projects, which are the searchable set.",
        )

    def handle(self, *args, **options):
        queryset = Project.objects.all().order_by("id")
        if options["project_id"]:
            queryset = queryset.filter(id=options["project_id"])
        if options["published_only"]:
            queryset = queryset.filter(status="Published")

        coverage = audit(queryset)
        self._report_coverage(coverage)

        if options["report"]:
            return

        targets = self._targets(queryset, coverage, options)
        if not targets:
            self.stdout.write("Nothing to do.")
            return

        self.stdout.write("")
        self.stdout.write("Embedding %d project(s)..." % len(targets))

        stats = GenerationStats()
        started = time.perf_counter()
        size = max(1, options["batch_size"])
        for index in range(0, len(targets), size):
            batch = targets[index : index + size]
            generate_for(batch, force=options["force"], stats=stats)
            self.stdout.write(
                "  %d / %d" % (min(index + size, len(targets)), len(targets))
            )
        elapsed = time.perf_counter() - started

        self._report_run(stats, elapsed)

    # ------------------------------------------------------------------
    def _targets(self, queryset, coverage, options):
        if options["force"]:
            return list(queryset)
        if options["missing_only"]:
            ids = coverage["missing_ids"]
        elif options["stale_only"]:
            ids = coverage["stale_ids"]
        else:
            ids = coverage["missing_ids"] + coverage["stale_ids"]
        return list(queryset.filter(id__in=ids)) if ids else []

    def _report_coverage(self, c):
        self.stdout.write("")
        self.stdout.write("Embedding coverage")
        self.stdout.write("-" * 48)
        self.stdout.write("  active model version : %s" % c["model_version"])
        self.stdout.write("  projects examined    : %d" % c["total"])
        self.stdout.write("  current              : %d" % c["current"])
        self.stdout.write("  missing              : %d" % c["missing"])
        self.stdout.write("  stale                : %d" % c["stale"])
        self.stdout.write("  no embeddable text   : %d" % c["no_embeddable_text"])
        if c["no_text_ids"]:
            self.stdout.write(
                "  project ids with no title or abstract: %s"
                % ", ".join(str(i) for i in c["no_text_ids"][:20])
            )

    def _report_run(self, stats, elapsed):
        d = stats.as_dict()
        done = d["created"] + d["updated"]
        self.stdout.write("")
        self.stdout.write("Generation")
        self.stdout.write("-" * 48)
        self.stdout.write("  created              : %d" % d["created"])
        self.stdout.write("  updated              : %d" % d["updated"])
        self.stdout.write("  unchanged            : %d" % d["unchanged"])
        self.stdout.write("  skipped, no text     : %d" % d["skipped_empty"])
        self.stdout.write("  failed               : %d" % d["failed"])
        for name, count in d["failure_types"].items():
            self.stdout.write("      %s: %d" % (name, count))
        self.stdout.write("  elapsed              : %.1f s" % elapsed)
        if done:
            self.stdout.write("  per project          : %.0f ms" % (elapsed / done * 1000))
            self.stdout.write("  throughput           : %.1f projects/s" % (done / elapsed))
        self.stdout.write("")
