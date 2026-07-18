import psycopg

from src.ingestion import config
from src.ingestion.task_classifier import classify_project_task_full


PROJECT_IDS = [22, 41, 86, 137, 156, 163, 164]


def connect():
    return psycopg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
    )


def main():

    with connect() as conn:
        with conn.cursor() as cur:

            print("=" * 50)
            print("TASK SCORE EVALUATION")
            print("=" * 50)

            for project_id in PROJECT_IDS:

                cur.execute(
                    """
                    SELECT
                        id,
                        embedding_text,
                        task_scores
                    FROM project_profiles
                    WHERE id = %s
                    """,
                    (project_id,)
                )

                row = cur.fetchone()

                if not row:
                    print(
                        f"{project_id}: NOT FOUND"
                    )
                    continue


                pid, embedding_text, existing_scores = row


                if not embedding_text:
                    print(
                        f"{pid}: NO EMBEDDING TEXT"
                    )
                    continue


                primary_task, ranked = classify_project_task_full(
                    embedding_text
                )


                print("-" * 50)
                print(
                    f"ID: {pid}"
                )


                if not ranked:

                    print(
                        "Classifier result: EMPTY"
                    )

                    print(
                        "Existing task_scores:",
                        existing_scores
                    )

                    continue


                print(
                    "Classifier result: OK"
                )

                print(
                    "Primary task:",
                    primary_task
                )

                print(
                    "Number of task scores:",
                    len(ranked)
                )

                print(
                    "Top score:",
                    ranked[0]
                )


            print("=" * 50)
            print("Evaluation complete")
            print("=" * 50)



if __name__ == "__main__":
    main()