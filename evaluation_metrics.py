#!/usr/bin/env python

"""
Evaluation metrics for the Pulchowk Project Repository ingestion pipeline.

Two independent evaluators, because they answer two different questions:

  1. CLASSIFICATION METRICS -- "did we assign the right domain/task?"
     Needs a ground-truth label per project (a human says what the domain
     /task actually is). Compares that against what domain_classifier.py /
     task_classifier.py assigned.

     Reports: accuracy, per-class precision/recall/F1, macro & weighted
     averages, a confusion matrix, top-k accuracy, and MRR -- the last two
     using the full ranked domain_scores/task_scores list (not just the
     single winning label), since a project scoring its true domain 2nd
     instead of 1st is a much smaller failure than not scoring it at all.

  2. RETRIEVAL METRICS -- "when someone searches, do the right projects
     come back, and near the top?"
     Needs a ground-truth relevance judgment per query (a human says which
     projects are actually relevant to a given search query). Runs that
     query through ProjectVectorStore.query_similar_projects and scores
     the returned ranking.

     Reports: precision@k, recall@k, MRR, MAP, nDCG@k.

Neither evaluator can invent ground truth -- you supply it as JSON. See
the `--labels`/`--queries` file formats below and the two worked examples
this script can print with `--show-example-format`.


GROUND TRUTH FORMATS
=====================

Classification labels file (one entry per project you've manually checked):

    {
        "wearable_ppg_monitor.pdf": {
            "domain": "Healthcare & Biomedical AI",
            "task": "Prediction & Forecasting"
        },
        "campus_transit_mapper.pdf": {
            "domain": "Web & Software Engineering",
            "task": "Optimization & Automation"
        }
    }

Retrieval queries file (one entry per query you've manually judged):

    {
        "wearable heart rate monitoring using ppg sensors": [
            "wearable_ppg_monitor.pdf",
            "fitness_band_vitals.pdf"
        ],
        "kathmandu public transit route mapping": [
            "campus_transit_mapper.pdf"
        ]
    }

Filenames in both files must match the `filename` column in `documents`
(i.e. exactly what's stored in the DB, not a local path).


USAGE
=====

    python evaluation_metrics.py classification --labels domain_labels.json --field domain
    python evaluation_metrics.py classification --labels task_labels.json --field task --k 3
    python evaluation_metrics.py retrieval --queries retrieval_queries.json --k 10
    python evaluation_metrics.py --show-example-format
"""

import argparse
import json
import math
import sys

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

from .section_coverage import load_domain_task_info
from .project_vector_store import ProjectVectorStore


# ============================================================
# Ground truth loading
# ============================================================

def load_classification_labels(path):
    """
    Loads {filename: {"domain": ..., "task": ...}} ground truth.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_retrieval_queries(path):
    """
    Loads {query_text: [relevant_filename, ...]} ground truth.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


EXAMPLE_CLASSIFICATION_LABELS = {
    "wearable_ppg_monitor.pdf": {
        "domain": "Healthcare & Biomedical AI",
        "task": "Prediction & Forecasting",
    },
    "campus_transit_mapper.pdf": {
        "domain": "Web & Software Engineering",
        "task": "Optimization & Automation",
    },
}

EXAMPLE_RETRIEVAL_QUERIES = {
    "wearable heart rate monitoring using ppg sensors": [
        "wearable_ppg_monitor.pdf",
        "fitness_band_vitals.pdf",
    ],
    "kathmandu public transit route mapping": [
        "campus_transit_mapper.pdf",
    ],
}


def show_example_format():
    print("Example classification labels file:\n")
    print(json.dumps(EXAMPLE_CLASSIFICATION_LABELS, indent=4))
    print("\nExample retrieval queries file:\n")
    print(json.dumps(EXAMPLE_RETRIEVAL_QUERIES, indent=4))


# ============================================================
# Classification metrics (domain / task)
# ============================================================

def _reciprocal_rank(true_label, ranked_labels):
    """
    ranked_labels is a list of label strings ordered best-first (already
    extracted from domain_scores/task_scores). Returns 1/rank of the true
    label's position (1-indexed), or 0.0 if it isn't present at all.
    """
    for i, label in enumerate(ranked_labels, start=1):
        if label == true_label:
            return 1.0 / i
    return 0.0


def _top_k_hit(true_label, ranked_labels, k):
    return true_label in ranked_labels[:k]


def evaluate_classification(labels_path, field="domain", top_k=3):
    """
    field: "domain" or "task" -- which column to evaluate.
    """
    if field not in ("domain", "task"):
        raise ValueError("field must be 'domain' or 'task'")

    ground_truth = load_classification_labels(labels_path)
    predictions = load_domain_task_info()

    y_true = []
    y_pred = []

    top_k_hits = 0
    reciprocal_ranks = []

    missing_projects = []

    scores_field = "domain_scores" if field == "domain" else "task_scores"
    rank_key = "domain" if field == "domain" else "task"

    for filename, labels in ground_truth.items():

        true_label = labels.get(field)
        if not true_label:
            continue

        prediction = predictions.get(filename)
        if prediction is None:
            missing_projects.append(filename)
            continue

        predicted_label = prediction.get(field)

        y_true.append(true_label)
        y_pred.append(predicted_label)

        ranked_entries = prediction.get(scores_field) or []
        ranked_labels = [
            entry.get(rank_key) for entry in ranked_entries if entry.get(rank_key)
        ]

        if _top_k_hit(true_label, ranked_labels, top_k):
            top_k_hits += 1

        reciprocal_ranks.append(_reciprocal_rank(true_label, ranked_labels))

    if not y_true:
        return {
            "error": (
                "No ground-truth labels could be matched to project_profiles "
                "rows. Check that filenames in the labels file exactly match "
                "documents.filename in the database."
            ),
            "missing_projects": missing_projects,
        }

    labels_sorted = sorted(set(y_true) | set(y_pred))

    accuracy = accuracy_score(y_true, y_pred)

    precision_per_class, recall_per_class, f1_per_class, support_per_class = (
        precision_recall_fscore_support(
            y_true, y_pred, labels=labels_sorted, zero_division=0
        )
    )

    precision_macro, recall_macro, f1_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels_sorted, average="macro", zero_division=0
    )

    precision_weighted, recall_weighted, f1_weighted, _ = (
        precision_recall_fscore_support(
            y_true, y_pred, labels=labels_sorted, average="weighted", zero_division=0
        )
    )

    cm = confusion_matrix(y_true, y_pred, labels=labels_sorted)

    per_class = {
        label: {
            "precision": round(float(precision_per_class[i]), 4),
            "recall": round(float(recall_per_class[i]), 4),
            "f1": round(float(f1_per_class[i]), 4),
            "support": int(support_per_class[i]),
        }
        for i, label in enumerate(labels_sorted)
    }

    return {
        "field": field,
        "n_evaluated": len(y_true),
        "missing_projects": missing_projects,
        "accuracy": round(float(accuracy), 4),
        "precision_macro": round(float(precision_macro), 4),
        "recall_macro": round(float(recall_macro), 4),
        "f1_macro": round(float(f1_macro), 4),
        "precision_weighted": round(float(precision_weighted), 4),
        "recall_weighted": round(float(recall_weighted), 4),
        "f1_weighted": round(float(f1_weighted), 4),
        f"top_{top_k}_accuracy": round(top_k_hits / len(y_true), 4),
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
        "per_class": per_class,
        "confusion_matrix": {
            "labels": labels_sorted,
            "matrix": cm.tolist(),
        },
    }


def print_classification_report(report, top_k):
    if "error" in report:
        print(f"ERROR: {report['error']}")
        if report.get("missing_projects"):
            print(f"Unmatched filenames: {report['missing_projects']}")
        return

    field = report["field"]
    print(f"\n=== Classification metrics: {field} ===")
    print(f"Evaluated on {report['n_evaluated']} labeled project(s)")

    if report["missing_projects"]:
        print(
            f"[warning] {len(report['missing_projects'])} labeled filename(s) "
            f"had no matching project_profiles row (typo, or not yet "
            f"ingested): {report['missing_projects']}"
        )

    print(f"\nAccuracy:            {report['accuracy']}")
    print(f"Precision (macro):   {report['precision_macro']}")
    print(f"Recall (macro):      {report['recall_macro']}")
    print(f"F1 (macro):          {report['f1_macro']}")
    print(f"Precision (weighted):{report['precision_weighted']}")
    print(f"Recall (weighted):   {report['recall_weighted']}")
    print(f"F1 (weighted):       {report['f1_weighted']}")
    print(f"Top-{top_k} accuracy:      {report[f'top_{top_k}_accuracy']}")
    print(
        f"MRR:                 {report['mrr']}  "
        f"(1.0 = true label always ranked #1 in domain_scores/task_scores; "
        f"0.0 = true label never appears in the ranked list at all)"
    )

    print("\nPer-class breakdown:")
    for label, stats in report["per_class"].items():
        print(
            f"  {label:<45} "
            f"P={stats['precision']:<7} R={stats['recall']:<7} "
            f"F1={stats['f1']:<7} support={stats['support']}"
        )

    print("\nConfusion matrix (rows=true, cols=predicted):")
    labels_sorted = report["confusion_matrix"]["labels"]
    matrix = report["confusion_matrix"]["matrix"]
    header = "".join(f"{l[:10]:>12}" for l in labels_sorted)
    print(" " * 25 + header)
    for label, row in zip(labels_sorted, matrix):
        print(f"{label[:23]:<25}" + "".join(f"{v:>12}" for v in row))


# ============================================================
# Retrieval metrics (project-level semantic search)
# ============================================================

def _precision_at_k(ranked_ids, relevant_ids, k):
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(top_k)


def _recall_at_k(ranked_ids, relevant_ids, k):
    if not relevant_ids:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(relevant_ids)


def _average_precision(ranked_ids, relevant_ids):
    if not relevant_ids:
        return 0.0

    hits = 0
    precisions = []
    for i, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            hits += 1
            precisions.append(hits / i)

    if not precisions:
        return 0.0

    return sum(precisions) / len(relevant_ids)


def _reciprocal_rank_retrieval(ranked_ids, relevant_ids):
    for i, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / i
    return 0.0


def _ndcg_at_k(ranked_ids, relevant_ids, k):
    """
    Binary relevance nDCG@k: relevant docs contribute gain 1, others 0.
    """
    top_k = ranked_ids[:k]

    dcg = 0.0
    for i, doc_id in enumerate(top_k, start=1):
        relevance = 1 if doc_id in relevant_ids else 0
        dcg += relevance / math.log2(i + 1)

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, ideal_hits + 1))

    if idcg == 0:
        return 0.0

    return dcg / idcg


def evaluate_retrieval(queries_path, top_k=10):

    ground_truth = load_retrieval_queries(queries_path)

    store = ProjectVectorStore()

    precisions = []
    recalls = []
    reciprocal_ranks = []
    average_precisions = []
    ndcgs = []

    per_query_results = []

    for query_text, relevant_filenames in ground_truth.items():

        relevant_set = set(relevant_filenames)

        results = store.query_similar_projects(query_text, top_k=top_k)

        # query_similar_projects returns metadata without filename directly
        # (it's keyed by project_title in the current schema) -- resolve
        # ranked document_ids back to filenames via get_project_profile's
        # underlying join isn't available here, so we look filenames up
        # from the document_id ordering the query already gives us.
        ranked_filenames = _resolve_filenames_for_results(store, results)

        precision = _precision_at_k(ranked_filenames, relevant_set, top_k)
        recall = _recall_at_k(ranked_filenames, relevant_set, top_k)
        rr = _reciprocal_rank_retrieval(ranked_filenames, relevant_set)
        ap = _average_precision(ranked_filenames, relevant_set)
        ndcg = _ndcg_at_k(ranked_filenames, relevant_set, top_k)

        precisions.append(precision)
        recalls.append(recall)
        reciprocal_ranks.append(rr)
        average_precisions.append(ap)
        ndcgs.append(ndcg)

        per_query_results.append({
            "query": query_text,
            "relevant": sorted(relevant_set),
            "returned": ranked_filenames,
            f"precision@{top_k}": round(precision, 4),
            f"recall@{top_k}": round(recall, 4),
            "reciprocal_rank": round(rr, 4),
            "average_precision": round(ap, 4),
            f"ndcg@{top_k}": round(ndcg, 4),
        })

    n = len(ground_truth)

    return {
        "n_queries": n,
        f"precision@{top_k}": round(sum(precisions) / n, 4) if n else 0.0,
        f"recall@{top_k}": round(sum(recalls) / n, 4) if n else 0.0,
        "mrr": round(sum(reciprocal_ranks) / n, 4) if n else 0.0,
        "map": round(sum(average_precisions) / n, 4) if n else 0.0,
        f"ndcg@{top_k}": round(sum(ndcgs) / n, 4) if n else 0.0,
        "per_query": per_query_results,
    }


def _resolve_filenames_for_results(store, results):
    """
    query_similar_projects() returns document_id + project metadata but not
    filename directly. Resolve document_id -> filename with one small
    lookup query instead of changing query_similar_projects's return
    contract (other callers may depend on its current shape).
    """
    if not results:
        return []

    document_ids = [r["id"] for r in results]

    with store.connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, filename FROM documents WHERE id = ANY(%s)",
            (document_ids,),
        )
        id_to_filename = dict(cursor.fetchall())

    return [
        id_to_filename[r["id"]]
        for r in results
        if r["id"] in id_to_filename
    ]


def print_retrieval_report(report, top_k):
    print(f"\n=== Retrieval metrics (top_k={top_k}) ===")
    print(f"Evaluated on {report['n_queries']} labeled quer(y/ies)")
    print(f"\nPrecision@{top_k}: {report[f'precision@{top_k}']}")
    print(f"Recall@{top_k}:    {report[f'recall@{top_k}']}")
    print(
        f"MRR:              {report['mrr']}  "
        f"(1.0 = first relevant result always ranked #1)"
    )
    print(
        f"MAP:              {report['map']}  "
        f"(mean average precision across all relevant hits, not just the first)"
    )
    print(f"nDCG@{top_k}:      {report[f'ndcg@{top_k}']}")

    print("\nPer-query breakdown:")
    for entry in report["per_query"]:
        print(f"\n  Query: \"{entry['query']}\"")
        print(f"    Relevant (ground truth): {entry['relevant']}")
        print(f"    Returned (ranked):       {entry['returned']}")
        print(
            f"    precision@{top_k}={entry[f'precision@{top_k}']}  "
            f"recall@{top_k}={entry[f'recall@{top_k}']}  "
            f"RR={entry['reciprocal_rank']}  "
            f"AP={entry['average_precision']}  "
            f"nDCG@{top_k}={entry[f'ndcg@{top_k}']}"
        )


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-example-format",
        action="store_true",
        help="Print example ground-truth JSON formats and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    classification_parser = subparsers.add_parser(
        "classification", help="Evaluate domain/task classification quality."
    )
    classification_parser.add_argument(
        "--labels", required=True, help="Path to classification labels JSON."
    )
    classification_parser.add_argument(
        "--field", choices=["domain", "task"], default="domain",
    )
    classification_parser.add_argument(
        "--k", type=int, default=3, help="k for top-k accuracy (default 3)."
    )

    retrieval_parser = subparsers.add_parser(
        "retrieval", help="Evaluate project-level semantic search quality."
    )
    retrieval_parser.add_argument(
        "--queries", required=True, help="Path to retrieval queries JSON."
    )
    retrieval_parser.add_argument(
        "--k", type=int, default=10, help="top_k results to evaluate (default 10)."
    )

    args = parser.parse_args()

    if args.show_example_format:
        show_example_format()
        sys.exit(0)

    if args.command == "classification":
        report = evaluate_classification(args.labels, field=args.field, top_k=args.k)
        print_classification_report(report, top_k=args.k)

    elif args.command == "retrieval":
        report = evaluate_retrieval(args.queries, top_k=args.k)
        print_retrieval_report(report, top_k=args.k)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()