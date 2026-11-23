"""Offline evaluation of the search and similarity layers.

Internal developer tooling, not exposed through the API or the interface:

    python manage.py search_eval
    python manage.py search_eval --only ranking --k 10
    python manage.py search_eval --save reports/eval.json

There is no labelled relevance data in this repository and none is invented
here. Every analysis is either an unsupervised diagnostic or a known-item
self-retrieval check:

    coverage     how much of the corpus is embedded and current
    integrity    stored vectors are normalised and self-identical
    neighbours   each project's distance to its nearest other project
    baseline     the same statistic for randomly drawn pairs, and the
                 percentile calibration written from it
    duplicates   pairs above a high cutoff, as duplicate candidates
    proposal     known-item self-retrieval for the Similar Work Check
    thresholds   the concept threshold sweep and the standout-margin sweep
    ranking      P@1, MRR, Recall@k and nDCG@k for the lexical, semantic and
                 fused branches across several weightings
    timing       encode throughput and k-NN query latency

Known-item retrieval measures whether a specific project can be found from a
description of it. It does not measure whether the other results are
relevant, and must not be reported as general precision or recall.

Output is counts, scores, percentiles, identifiers and timings. No title,
abstract, keyword or section text is read into anything printable.
"""

import json
import random
import statistics
import time
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from repository.embedding import active_model_version, audit, get_backend
from repository.models import Project, ProjectEmbedding


def ids_for(version):
    return list(
        ProjectEmbedding.objects.filter(model_version=version)
        .order_by("project_id")
        .values_list("project_id", flat=True)
    )

ALL_ANALYSES = ("coverage", "integrity", "neighbours", "baseline",
                "duplicates", "proposal", "thresholds", "ranking", "timing")

# Above this many possible pairs the random-pair baseline is sampled rather
# than enumerated. Exhaustive enumeration is a single set-returning query and
# stays cheap well into the tens of thousands of pairs; sampling costs one
# query per pair, so it is the slower path until the corpus is large enough
# for the quadratic term to dominate. 50,000 pairs is roughly 320 projects.
EXACT_PAIR_LIMIT = 50_000


def percentiles(values, points=(1, 5, 25, 50, 75, 90, 95, 99)):
    if not values:
        return {}
    ordered = sorted(values)
    out = {}
    for p in points:
        idx = min(len(ordered) - 1, int(len(ordered) * p / 100))
        out["p%d" % p] = round(ordered[idx], 4)
    return out


def describe(values):
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": round(min(values), 4),
        "mean": round(statistics.fmean(values), 4),
        "max": round(max(values), 4),
        **percentiles(values),
    }


class Command(BaseCommand):
    help = "Offline diagnostics for embeddings and semantic retrieval."

    def add_arguments(self, parser):
        parser.add_argument("--only", type=str, default=None,
                            help="Comma-separated subset of: " + ",".join(ALL_ANALYSES))
        parser.add_argument("--save", type=str, default=None,
                            help="Write the aggregate report to this JSON path.")
        parser.add_argument("--duplicate-cutoff", type=float, default=0.95,
                            help="Cosine at or above which a pair is a duplicate candidate.")
        parser.add_argument("--sample-pairs", type=int, default=5000,
                            help="Random pairs drawn for the baseline on large corpora.")
        parser.add_argument("--proposal-sample", type=int, default=0,
                            help="Projects used for the proposal analysis. 0 means all.")
        parser.add_argument("--seed", type=int, default=12345)
        parser.add_argument("--query-set", type=str, default=None,
                            help="JSON file of labelled queries. Without it the "
                                 "ranking analysis uses known-item queries "
                                 "derived from the projects themselves.")
        parser.add_argument("--k", type=int, default=10,
                            help="Cut-off for Recall@k and nDCG@k.")
        parser.add_argument("--ranking-sample", type=int, default=0,
                            help="Queries per strategy. 0 means all projects.")

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        random.seed(options["seed"])
        selected = ALL_ANALYSES
        if options["only"]:
            selected = tuple(s.strip() for s in options["only"].split(",") if s.strip())
            unknown = [s for s in selected if s not in ALL_ANALYSES]
            if unknown:
                self.stderr.write("Unknown analysis: %s" % ", ".join(unknown))
                return

        version = active_model_version()
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "configuration": {
                "model_name": settings.EMBEDDING["MODEL_NAME"],
                "model_version": version,
                "dimension": settings.EMBEDDING["DIMENSION"],
                "max_seq_length": settings.EMBEDDING["MAX_SEQ_LENGTH"],
                "normalised": settings.EMBEDDING["NORMALIZE"],
                "rrf_k": settings.SEARCH["RRF_K"],
                "lexical_pool": settings.SEARCH["LEXICAL_POOL"],
                "semantic_pool": settings.SEARCH["SEMANTIC_POOL"],
            },
            "analyses": {},
        }

        self._banner("Configuration")
        for key, value in report["configuration"].items():
            self.stdout.write("  %-16s : %s" % (key, value))

        ids = list(
            ProjectEmbedding.objects.filter(model_version=version)
            .order_by("project_id")
            .values_list("project_id", flat=True)
        )

        if "coverage" in selected:
            report["analyses"]["coverage"] = self._coverage()
        if "integrity" in selected:
            report["analyses"]["integrity"] = self._integrity(version, ids)
        if "neighbours" in selected:
            report["analyses"]["neighbours"] = self._neighbours(version, ids)
        if "baseline" in selected:
            report["analyses"]["baseline"] = self._baseline(
                version, ids, options["sample_pairs"])
        if "duplicates" in selected:
            report["analyses"]["duplicates"] = self._duplicates(
                version, ids, options["duplicate_cutoff"])
        if "proposal" in selected:
            report["analyses"]["proposal"] = self._proposal(
                version, ids, options["proposal_sample"])
        if "thresholds" in selected:
            report["analyses"]["thresholds"] = self._thresholds(version, options)
        if "ranking" in selected:
            report["analyses"]["ranking"] = self._ranking(version, options)
        if "timing" in selected:
            report["analyses"]["timing"] = self._timing(version, ids)

        if options["save"]:
            path = options["save"]
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2)
            self.stdout.write("")
            self.stdout.write("Report written to %s" % path)

    # ------------------------------------------------------------------
    def _banner(self, title):
        self.stdout.write("")
        self.stdout.write(title)
        self.stdout.write("-" * 60)

    def _show(self, stats, indent="  "):
        if stats.get("n", 0) == 0:
            self.stdout.write(indent + "no values")
            return
        self.stdout.write(
            indent + "n=%d  min=%.4f  mean=%.4f  max=%.4f"
            % (stats["n"], stats["min"], stats["mean"], stats["max"])
        )
        line = "  ".join(
            "%s=%.4f" % (k, v) for k, v in stats.items()
            if k.startswith("p")
        )
        self.stdout.write(indent + line)

    # ------------------------------------------------------------------
    def _coverage(self):
        c = audit()
        self._banner("Coverage")
        for key in ("model_version", "total", "current", "missing", "stale",
                    "no_embeddable_text"):
            self.stdout.write("  %-20s : %s" % (key, c[key]))
        return {k: v for k, v in c.items() if not k.endswith("_ids")}

    def _integrity(self, version, ids):
        """Vectors must be unit length and exactly self-similar. A failure
        here means storage or normalisation is wrong and every downstream
        number is meaningless."""
        self._banner("Vector integrity")
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT MIN(l2), MAX(l2), MIN(selfsim), MAX(selfsim) FROM (
                    SELECT vector_norms.l2, 1 - (e.embedding <=> e.embedding) AS selfsim
                    FROM project_embeddings e
                    JOIN LATERAL (SELECT sqrt(SUM(x*x)) AS l2
                                  FROM unnest(e.embedding::real[]) AS x) vector_norms ON TRUE
                    WHERE e.model_version = %s
                ) t
                """,
                [version],
            )
            row = cur.fetchone()
        result = {
            "vectors": len(ids),
            "l2_norm_min": round(row[0], 6) if row[0] is not None else None,
            "l2_norm_max": round(row[1], 6) if row[1] is not None else None,
            "self_similarity_min": round(row[2], 6) if row[2] is not None else None,
            "self_similarity_max": round(row[3], 6) if row[3] is not None else None,
        }
        for key, value in result.items():
            self.stdout.write("  %-22s : %s" % (key, value))
        ok = (result["l2_norm_min"] is not None
              and abs(result["l2_norm_min"] - 1) < 1e-3
              and abs(result["l2_norm_max"] - 1) < 1e-3)
        self.stdout.write("  normalised as expected : %s" % ok)
        result["normalised_as_expected"] = ok
        return result

    def _neighbours(self, version, ids):
        """Each project's cosine to its nearest other project.

        This is the distribution the Similar Projects threshold has to be
        chosen against: a cutoff below the bulk of it shows everyone
        something, a cutoff above it shows almost nobody anything.
        """
        self._banner("Nearest non-self neighbour")
        scores, pairs = [], []
        with connection.cursor() as cur:
            for pid in ids:
                cur.execute(
                    """
                    SELECT n.project_id, 1 - (n.embedding <=> e.embedding) AS sim
                    FROM project_embeddings n, project_embeddings e
                    WHERE e.project_id = %s AND e.model_version = %s
                      AND n.model_version = %s AND n.project_id <> e.project_id
                    ORDER BY n.embedding <=> e.embedding
                    LIMIT 1
                    """,
                    [pid, version, version],
                )
                row = cur.fetchone()
                if row:
                    scores.append(float(row[1]))
                    pairs.append((pid, row[0], round(float(row[1]), 4)))
        stats = describe(scores)
        self._show(stats)
        top = sorted(pairs, key=lambda p: -p[2])[:10]
        self.stdout.write("  closest pairs (project ids and cosine):")
        for a, b, s in top:
            self.stdout.write("    %-6s <-> %-6s  %.4f" % (a, b, s))
        return {"distribution": stats, "closest_pairs": top}

    def _baseline(self, version, ids, sample_pairs):
        """Cosine between randomly drawn pairs.

        The contrast against the neighbour distribution is what shows whether
        the embedding discriminates at all. If random pairs score as high as
        nearest neighbours, no threshold can work.
        """
        self._banner("Random-pair baseline")
        n = len(ids)
        total_pairs = n * (n - 1) // 2
        exact = total_pairs <= EXACT_PAIR_LIMIT
        self.stdout.write(
            "  corpus=%d  possible pairs=%d  mode=%s"
            % (n, total_pairs, "exhaustive" if exact else "sampled")
        )

        scores = []
        with connection.cursor() as cur:
            if exact:
                cur.execute(
                    """
                    SELECT 1 - (a.embedding <=> b.embedding)
                    FROM project_embeddings a
                    JOIN project_embeddings b
                      ON a.project_id < b.project_id
                     AND b.model_version = %s
                    WHERE a.model_version = %s
                    """,
                    [version, version],
                )
                scores = [float(r[0]) for r in cur.fetchall()]
            else:
                seen = set()
                while len(seen) < min(sample_pairs, total_pairs):
                    a, b = random.sample(ids, 2)
                    seen.add((min(a, b), max(a, b)))
                for a, b in seen:
                    cur.execute(
                        """
                        SELECT 1 - (x.embedding <=> y.embedding)
                        FROM project_embeddings x, project_embeddings y
                        WHERE x.project_id=%s AND y.project_id=%s
                          AND x.model_version=%s AND y.model_version=%s
                        """,
                        [a, b, version, version],
                    )
                    row = cur.fetchone()
                    if row:
                        scores.append(float(row[0]))
        stats = describe(scores)
        self._show(stats)

        # This distribution is the only thing that makes a raw cosine
        # interpretable, so it is persisted rather than merely printed. The
        # application reads it through SimilarityCalibration; recomputing it
        # is a matter of running this command again once the corpus grows.
        stored = self._store_calibration(version, n, scores, exact)
        return {
            "mode": "exhaustive" if exact else "sampled",
            "distribution": stats,
            "calibration": stored,
        }

    def _store_calibration(self, version, corpus_size, scores, exact):
        from repository.models import SimilarityCalibration

        if not scores:
            return None
        points = settings.SIMILARITY["CALIBRATION_PERCENTILES"]
        ordered = sorted(scores)
        breakpoints = []
        for p in points:
            idx = min(len(ordered) - 1, int(len(ordered) * p / 100))
            breakpoints.append([p, round(ordered[idx], 6)])

        obj, created = SimilarityCalibration.objects.update_or_create(
            model_version=version,
            defaults={
                "corpus_size": corpus_size,
                "pair_count": len(scores),
                "sampled": not exact,
                "breakpoints": breakpoints,
            },
        )
        self.stdout.write(
            "  calibration %s for %s: %d pairs over %d projects"
            % ("created" if created else "updated", version, len(scores), corpus_size)
        )
        return {
            "corpus_size": corpus_size,
            "pair_count": len(scores),
            "sampled": not exact,
            "breakpoints": breakpoints,
        }

    def _duplicates(self, version, ids, cutoff):
        """Pairs at or above a high cosine: candidates for genuine duplicates
        in the corpus, or for false positives worth inspecting."""
        self._banner("Near-duplicate candidates (cosine >= %.2f)" % cutoff)
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT a.project_id, b.project_id, 1 - (a.embedding <=> b.embedding) AS sim
                FROM project_embeddings a
                JOIN project_embeddings b
                  ON a.project_id < b.project_id AND b.model_version = %s
                WHERE a.model_version = %s
                  AND 1 - (a.embedding <=> b.embedding) >= %s
                ORDER BY sim DESC
                LIMIT 50
                """,
                [version, version, cutoff],
            )
            rows = [(r[0], r[1], round(float(r[2]), 4)) for r in cur.fetchall()]
        self.stdout.write("  pairs found : %d" % len(rows))
        for a, b, s in rows[:20]:
            self.stdout.write("    %-6s <-> %-6s  %.4f" % (a, b, s))
        return {"cutoff": cutoff, "count": len(rows), "pairs": rows}

    def _proposal(self, version, ids, sample):
        """Known-item self-retrieval for the Similar Work Check.

        Each project is turned into a concept query twice: once from its
        title alone, and once from the opening sentence of its abstract,
        which is the closest available proxy for a student describing an idea
        in a line or two. Both are encoded with the *query* convention, which
        is what the check itself now uses.

        Because the query was derived from the project, the correct answer is
        known without any labelling. The rank of the true project says whether
        an idea can find its own project; the score distribution is what the
        0.78 threshold is judged against, and `cleared_threshold` says how
        many genuine matches that threshold would actually admit.
        """
        self._banner("Concept simulation (known-item self-retrieval)")
        chosen = list(ids)
        if sample and sample < len(chosen):
            chosen = random.sample(chosen, sample)

        projects = {p.pk: p for p in Project.objects.filter(pk__in=chosen)}
        backend = get_backend()
        threshold = settings.SIMILARITY["SIMILAR_PROJECTS_MIN"]
        out = {}

        for mode in ("title_only", "abstract_sentence"):
            texts, order = [], []
            for pid in chosen:
                p = projects.get(pid)
                if p is None:
                    continue
                if mode == "title_only":
                    text = (p.title or "").strip()
                else:
                    first = (p.abstract or "").strip().replace("\n", " ").split(". ")[0]
                    text = first if 40 < len(first) < 400 else ""
                if not text:
                    continue
                texts.append(text)
                order.append(pid)

            vectors = backend.encode_queries(texts)
            self_scores, top_scores, ranks, hits, cleared = [], [], [], 0, 0
            with connection.cursor() as cur:
                for pid, vector in zip(order, vectors):
                    literal = "[" + ",".join("%.7f" % v for v in vector) + "]"
                    cur.execute(
                        """
                        SELECT project_id, 1 - (embedding <=> %s::vector) AS sim
                        FROM project_embeddings
                        WHERE model_version = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT 10
                        """,
                        [literal, version, literal],
                    )
                    rows = cur.fetchall()
                    if not rows:
                        continue
                    top_scores.append(float(rows[0][1]))
                    rank = None
                    for position, row in enumerate(rows, start=1):
                        if row[0] == pid:
                            rank = position
                            score = float(row[1])
                            self_scores.append(score)
                            if score >= threshold:
                                cleared += 1
                            break
                    if rank == 1:
                        hits += 1
                    ranks.append(rank if rank else 0)

            found = [r for r in ranks if r]
            result = {
                "projects_evaluated": len(order),
                "own_project_rank_1": hits,
                "own_project_rank_1_pct": round(100 * hits / len(order), 1) if order else 0,
                "own_project_in_top_10": len(found),
                "threshold": threshold,
                "cleared_threshold": cleared,
                "cleared_threshold_pct": round(100 * cleared / len(order), 1) if order else 0,
                "mean_rank_when_found": round(statistics.fmean(found), 2) if found else None,
                "similarity_to_own_project": describe(self_scores),
                "similarity_to_best_match": describe(top_scores),
            }
            out[mode] = result

            self.stdout.write("")
            self.stdout.write("  mode: %s" % mode)
            self.stdout.write("    evaluated              : %d" % result["projects_evaluated"])
            self.stdout.write("    own project at rank 1  : %d  (%.1f%%)"
                              % (result["own_project_rank_1"], result["own_project_rank_1_pct"]))
            self.stdout.write("    own score >= %.2f       : %d  (%.1f%%)"
                              % (threshold, cleared, result["cleared_threshold_pct"]))
            self.stdout.write("    cosine to own project:")
            self._show(result["similarity_to_own_project"], indent="      ")
        return out

    # ------------------------------------------------------------------
    def _thresholds(self, version, options):
        """The precision/coverage trade-off for concept queries.

        A concept query is short and general, so it scores lower against its
        own project than a full title and abstract does. The threshold that
        was calibrated on project-to-project pairs is therefore the wrong
        instrument here, and this measures what the right one is.

        Known-item again: the query is the opening sentence of a project's own
        abstract, so the one correct answer is known. For each candidate
        threshold it reports

            recall   the share of queries whose own project clears it
            noise    the mean number of OTHER projects that also clear it

        Recall is the useful half; noise is the cost. A threshold is only
        worth lowering while the recall it buys outruns the noise it admits.
        """
        self._banner("Concept threshold trade-off")
        backend = get_backend()
        chosen = list(ids_for(version))
        if options["ranking_sample"]:
            chosen = chosen[: options["ranking_sample"]]

        projects = {p.pk: p for p in Project.objects.filter(pk__in=chosen)}
        texts, order = [], []
        for pid in chosen:
            p = projects.get(pid)
            if p is None:
                continue
            first = (p.abstract or "").strip().replace("\n", " ").split(". ")[0]
            if not (40 < len(first) < 400):
                continue
            texts.append(first)
            order.append(pid)

        vectors = backend.encode_queries(texts)

        # One pass: every score for every query, then swept in Python.
        own_scores, other_scores = [], []
        with connection.cursor() as cur:
            for pid, vector in zip(order, vectors):
                literal = "[" + ",".join("%.7f" % v for v in vector) + "]"
                cur.execute(
                    """
                    SELECT project_id, 1 - (embedding <=> %s::vector)
                    FROM project_embeddings WHERE model_version = %s
                    """,
                    [literal, version],
                )
                mine, others = None, []
                for other_id, score in cur.fetchall():
                    if other_id == pid:
                        mine = float(score)
                    else:
                        others.append(float(score))
                if mine is not None:
                    own_scores.append(mine)
                    other_scores.append(others)

        n = len(own_scores)
        self.stdout.write("  queries: %d   corpus: %d" % (n, len(chosen)))
        self.stdout.write("")
        self.stdout.write("    %-10s %10s %14s %16s" % (
            "threshold", "recall", "noise/query", "queries w/ noise"))

        table = {}
        for t in (0.66, 0.68, 0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82):
            recall = sum(1 for s in own_scores if s >= t) / n if n else 0
            noise = [sum(1 for s in row if s >= t) for row in other_scores]
            mean_noise = statistics.fmean(noise) if noise else 0
            with_noise = sum(1 for c in noise if c) / n if n else 0
            table["%.2f" % t] = {
                "recall": round(recall, 4),
                "mean_other_projects_above": round(mean_noise, 2),
                "share_of_queries_with_any_noise": round(with_noise, 4),
            }
            self.stdout.write("    %-10.2f %9.1f%% %14.2f %15.1f%%" % (
                t, 100 * recall, mean_noise, 100 * with_noise))

        margins = self._standout_margins(own_scores, other_scores)
        return {"queries": n, "table": table, "standout_margins": margins}

    def _standout_margins(self, own_scores, other_scores):
        """The standout rule the concept check actually applies below 0.78.

        A flat threshold cannot separate a concept whose subject is in the
        corpus from one whose subject is absent, because the absent one can
        score higher. What separates them is whether the leading project
        stands clear of the rest of the field, so the rule below the strong
        cut-off takes one project and only when it leads by a margin.

        Both directions are measured. Recall is the share of queries whose own
        project is surfaced. False alarm re-runs each query with its own
        project held out, which makes it a query whose subject is absent, so
        any row returned is unwanted. That overstates the cost -- a held-out
        query can still have genuinely related work in the corpus -- and is
        therefore an upper bound rather than an estimate.
        """
        config = settings.SIMILARITY
        strong = config["CONCEPT_STRONG_MIN"]
        floor = config["CONCEPT_POSSIBLE_MIN"]
        n = len(own_scores)
        if not n:
            return {}

        def top_two(row):
            ranked = sorted(row, reverse=True)
            return ranked[0], (ranked[1] if len(ranked) > 1 else -1.0)

        self.stdout.write("")
        self.stdout.write("  Standout margin below the %.2f cut-off  (floor %.2f)"
                          % (strong, floor))
        self.stdout.write("    %-8s %14s %16s %22s" % (
            "margin", "total recall", "false alarm", "added by the rule"))

        table = {}
        for margin in (None, 0.12, 0.10, 0.08, 0.05, 0.03):
            hit = alarm = extra_hit = extra_alarm = 0
            for own, others in zip(own_scores, other_scores):
                best_other, second_other = top_two(others)

                # Subject present: is the project the concept came from shown?
                if own >= strong or best_other >= strong:
                    hit += 1 if own >= strong else 0
                elif margin is not None and own >= floor and own - best_other >= margin:
                    hit += 1
                    extra_hit += 1

                # Subject held out: anything returned is unwanted.
                if best_other >= strong:
                    alarm += 1
                elif (margin is not None and best_other >= floor
                        and best_other - second_other >= margin):
                    alarm += 1
                    extra_alarm += 1

            key = "off" if margin is None else "%.2f" % margin
            table[key] = {
                "recall": round(hit / n, 4),
                "false_alarm_upper_bound": round(alarm / n, 4),
                "added_true": extra_hit,
                "added_false": extra_alarm,
            }
            added = ("baseline, %.2f only" % strong if margin is None
                     else "+%d true / +%d false" % (extra_hit, extra_alarm))
            self.stdout.write("    %-8s %13.1f%% %15.1f%% %22s" % (
                key, 100 * hit / n, 100 * alarm / n, added))

        self.stdout.write("")
        self.stdout.write("    in use: margin %.2f" % config["CONCEPT_POSSIBLE_MARGIN"])
        return table

    # ------------------------------------------------------------------
    def _ranking(self, version, options):
        """Lexical against semantic against fused, on the same queries.

        Reports Precision@1, Recall@k, MRR and nDCG@k. Where the query set is
        derived from the projects themselves this is known-item retrieval and
        is labelled as such: it measures whether a project can be found from a
        description of it, not whether a result list is relevant in general.
        """
        from repository.evaluation import (
            aggregate,
            build_known_item_queries,
            evaluate_ranking,
            load_query_set,
        )
        from repository.hybrid_search import (
            lexical_ranking,
            reciprocal_rank_fusion,
            semantic_ranking,
        )
        from repository.models import Project

        self._banner("Ranking comparison")
        k = options["k"]
        rrf_k = settings.SEARCH["RRF_K"]
        pool = max(settings.SEARCH["LEXICAL_POOL"], settings.SEARCH["SEMANTIC_POOL"])
        queryset = Project.objects.filter(status="Published")

        if options["query_set"]:
            strategies = {"labelled": load_query_set(options["query_set"])}
            self.stdout.write("  query set  : %s (labelled)" % options["query_set"])
        else:
            limit = options["ranking_sample"] or None
            strategies = {
                name: build_known_item_queries(name, limit=limit, seed=options["seed"])
                for name in ("title", "keywords", "title_subset")
            }
            self.stdout.write(
                "  query set  : known-item, derived from the projects themselves"
            )
        self.stdout.write("  cut-off k  : %d   RRF k: %d   pool: %d"
                          % (k, rrf_k, pool))

        # Candidate weightings. 1:1 is plain RRF; the others let one branch
        # dominate without silencing the other.
        weightings = [
            ("lexical only", None),
            ("semantic only", None),
            ("hybrid 1:1", {"lexical": 1.0, "semantic": 1.0}),
            ("hybrid 2:1 lex", {"lexical": 2.0, "semantic": 1.0}),
            ("hybrid 1:2 sem", {"lexical": 1.0, "semantic": 2.0}),
            ("hybrid 3:1 lex", {"lexical": 3.0, "semantic": 1.0}),
            ("hybrid 1:3 sem", {"lexical": 1.0, "semantic": 3.0}),
        ]

        results = {}
        for strategy, queries in strategies.items():
            if not queries:
                continue
            self.stdout.write("")
            self.stdout.write("  strategy: %s  (%d queries)" % (strategy, len(queries)))
            self.stdout.write("    %-16s %8s %8s %8s %8s"
                              % ("configuration", "P@1", "MRR", "R@%d" % k, "nDCG@%d" % k))

            # Both branches are computed once per query and reused for every
            # weighting, so the sweep costs one pass rather than seven.
            branch_cache = []
            for text, relevant in queries:
                branch_cache.append((
                    lexical_ranking(queryset, text, pool),
                    semantic_ranking(queryset, text, pool, version),
                    relevant,
                ))

            strategy_results = {}
            for label, weights in weightings:
                per_query = []
                for lexical, semantic, relevant in branch_cache:
                    if label == "lexical only":
                        ordered = lexical
                    elif label == "semantic only":
                        ordered = semantic
                    else:
                        ordered, _ = reciprocal_rank_fusion(
                            {"lexical": lexical, "semantic": semantic},
                            k=rrf_k, weights=weights,
                        )
                    per_query.append(evaluate_ranking(ordered, relevant, k=k))
                summary = aggregate(per_query)
                strategy_results[label] = summary
                self.stdout.write(
                    "    %-16s %8.3f %8.3f %8.3f %8.3f"
                    % (label, summary["p_at_1"], summary["reciprocal_rank"],
                       summary["recall_at_k"], summary["ndcg_at_k"])
                )
            results[strategy] = strategy_results
        return results

    def _timing(self, version, ids):
        self._banner("Timing")
        backend = get_backend()
        sample_texts = ["Represent this sentence for searching relevant passages: "
                        "machine learning for medical image analysis"] * 8

        backend.encode_queries(["warm up the model"])

        started = time.perf_counter()
        backend.encode_queries(sample_texts[:1])
        single = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        backend.encode_queries(sample_texts)
        batch8 = (time.perf_counter() - started) * 1000

        vector = backend.encode_queries(["traffic management using reinforcement learning"])[0]
        literal = "[" + ",".join("%.7f" % v for v in vector) + "]"
        latencies = []
        with connection.cursor() as cur:
            for _ in range(20):
                started = time.perf_counter()
                cur.execute(
                    """
                    SELECT project_id FROM project_embeddings
                    WHERE model_version = %s
                    ORDER BY embedding <=> %s::vector LIMIT 10
                    """,
                    [version, literal],
                )
                cur.fetchall()
                latencies.append((time.perf_counter() - started) * 1000)

        result = {
            "corpus_vectors": len(ids),
            "encode_single_ms": round(single, 1),
            "encode_batch_of_8_ms": round(batch8, 1),
            "encode_per_text_in_batch_ms": round(batch8 / 8, 1),
            "knn_top10_ms": describe(latencies),
        }
        self.stdout.write("  corpus vectors           : %d" % result["corpus_vectors"])
        self.stdout.write("  encode 1 query           : %.1f ms" % result["encode_single_ms"])
        self.stdout.write("  encode batch of 8        : %.1f ms (%.1f ms each)"
                          % (result["encode_batch_of_8_ms"], result["encode_per_text_in_batch_ms"]))
        self.stdout.write("  nearest-neighbour top 10 :")
        self._show(result["knn_top10_ms"], indent="    ")
        return result
