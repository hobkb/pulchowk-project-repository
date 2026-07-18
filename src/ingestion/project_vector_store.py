"""
PostgreSQL + pgvector project-level vector storage.

Stores exactly one semantic profile per project.

Table:
project_profiles

Used for:
- similar project recommendation
- project discovery
- project-level semantic retrieval
"""


from sentence_transformers import SentenceTransformer
import psycopg

from psycopg.types.json import Json
from pgvector.psycopg import register_vector

from . import config
from .logger import get_logger


logger = get_logger()



class ProjectVectorStore:


    def __init__(self):

        self.model = SentenceTransformer(
            config.EMBEDDING_MODEL
        )


        self.connection = psycopg.connect(

            host=config.POSTGRES_HOST,

            port=config.POSTGRES_PORT,

            dbname=config.POSTGRES_DB,

            user=config.POSTGRES_USER,

            password=config.POSTGRES_PASSWORD

        )


        register_vector(
            self.connection
        )


        logger.info(
            "Connected to PostgreSQL project vector store"
        )



    # -------------------------------------------------
    # Text cleaning
    # -------------------------------------------------

    def clean_text(
        self,
        text
    ):

        """
        Removes invalid characters before
        PostgreSQL text insertion.

        PostgreSQL text fields cannot contain
        NUL bytes (0x00).
        """

        if not text:

            return ""


        return (

            str(text)

            .replace(
                "\x00",
                ""
            )

            .replace(
                "\u0000",
                ""
            )

        )



    # -------------------------------------------------
    # Insert / Update project profile
    # -------------------------------------------------

    def upsert_project_profile(
        self,
        document_id,
        profile
    ):


        embedding_text = self.clean_text(

            profile.get(
                "embedding_text",
                ""
            )

        )


        embedding = self.model.encode(

            embedding_text,

            normalize_embeddings=True

        )


        try:

            with self.connection.cursor() as cursor:


                cursor.execute(

                    """

                    INSERT INTO project_profiles

                    (

                        document_id,

                        project_title,

                        domain,

                        task,

                        domain_scores,

                        task_scores,

                        keywords,

                        abstract,

                        objectives,

                        methodology,

                        embedding_text,

                        embedding,

                        embedding_model,

                        pipeline_version

                    )


                    VALUES

                    (

                        %s,%s,%s,%s,%s,%s,

                        %s,%s,%s,%s,%s,%s,

                        %s,%s

                    )


                    ON CONFLICT(document_id)

                    DO UPDATE SET


                        project_title = EXCLUDED.project_title,

                        domain = EXCLUDED.domain,

                        task = EXCLUDED.task,

                        domain_scores = EXCLUDED.domain_scores,

                        task_scores = EXCLUDED.task_scores,

                        keywords = EXCLUDED.keywords,

                        abstract = EXCLUDED.abstract,

                        objectives = EXCLUDED.objectives,

                        methodology = EXCLUDED.methodology,

                        embedding_text = EXCLUDED.embedding_text,

                        embedding = EXCLUDED.embedding,

                        embedding_model = EXCLUDED.embedding_model,

                        pipeline_version = EXCLUDED.pipeline_version


                    """,


                    (

                        document_id,


                        self.clean_text(

                            profile.get(
                                "project_title",
                                "UNKNOWN"
                            )

                        ),


                        self.clean_text(

                            profile.get(
                                "domain",
                                "Unknown"
                            )

                        ),


                        self.clean_text(

                            profile.get(
                                "task",
                                "Unknown"
                            )

                        ),


                        Json(
                            profile.get(
                                "domain_scores",
                                []
                            )
                        ),


                        Json(
                            profile.get(
                                "task_scores",
                                []
                            )
                        ),


                        profile.get(
                            "keywords",
                            []
                        ),


                        self.clean_text(

                            profile.get(
                                "abstract",
                                ""
                            )

                        )[:1000],
                                                self.clean_text(

                            profile.get(
                                "objectives",
                                ""
                            )

                        )[:1000],


                        self.clean_text(

                            profile.get(
                                "methodology",
                                ""
                            )

                        )[:1000],


                        embedding_text,


                        embedding.tolist(),


                        config.EMBEDDING_MODEL,


                        config.PIPELINE_VERSION

                    )

                )


                self.connection.commit()


        except Exception:


            self.connection.rollback()


            raise



        logger.info(
            f"Updated project profile for document_id={document_id}"
        )



    # -------------------------------------------------
    # Delete
    # -------------------------------------------------

    def delete_project(
        self,
        document_id
    ):


        with self.connection.cursor() as cursor:


            cursor.execute(

                """

                DELETE FROM project_profiles

                WHERE document_id=%s

                """,

                (
                    document_id,
                )

            )


        self.connection.commit()



    # -------------------------------------------------
    # Query normalization
    # -------------------------------------------------

    @staticmethod
    def normalize_query(
        query
    ):

        return query.strip()



    # -------------------------------------------------
    # Similarity classification
    # -------------------------------------------------

    @staticmethod
    def classify_distance(
        distance
    ):


        if distance <= 0.30:

            return "HIGHLY SIMILAR"


        elif distance <= 0.55:

            return "RELATED"


        else:

            return "LOW SIMILARITY"



    # -------------------------------------------------
    # Similar project search
    # -------------------------------------------------

    def query_similar_projects(
        self,
        query_text,
        top_k=5
    ):


        query = self.normalize_query(
            query_text
        )


        query_embedding = self.model.encode(

            query,

            normalize_embeddings=True

        )



        with self.connection.cursor() as cursor:


            cursor.execute(

                """

                SELECT


                    document_id,

                    project_title,

                    domain,

                    task,

                    domain_scores,

                    task_scores,

                    keywords,

                    abstract,

                    objectives,

                    methodology,


                    embedding <=> %s AS distance



                FROM project_profiles


                ORDER BY embedding <=> %s



                LIMIT %s


                """,

                (

                    query_embedding,


                    query_embedding,

                    top_k

                )

            )


            rows = cursor.fetchall()



        results = []



        for row in rows:


            distance = float(

                row[-1]

            )


            if distance <= 0.55:


                results.append(

                    {


                        "id": row[0],


                        "distance": distance,


                        "similarity":

                            self.classify_distance(

                                distance

                            ),


                        "metadata":


                        {


                            "project_title": row[1],


                            "domain": row[2],


                            "task": row[3],


                            "domain_scores": row[4],


                            "task_scores": row[5],


                            "keywords": row[6],


                            "abstract": row[7],


                            "objectives": row[8],


                            "methodology": row[9]


                        }

                    }

                )



        return results

        # -------------------------------------------------
    # Retrieve project profile
    # -------------------------------------------------

    def get_project_profile(
        self,
        filename
    ):


        with self.connection.cursor() as cursor:


            cursor.execute(

                """

                SELECT


                    d.filename,

                    pp.project_title,

                    pp.domain,

                    pp.task,

                    pp.domain_scores,

                    pp.task_scores,

                    pp.keywords,

                    pp.abstract,

                    pp.objectives,

                    pp.methodology,

                    pp.embedding_text



                FROM project_profiles pp


                JOIN documents d

                ON pp.document_id = d.id



                WHERE d.filename = %s


                """,

                (
                    filename,
                )

            )


            row = cursor.fetchone()



        if not row:

            return None



        return {


            "filename": row[0],


            "project_title": row[1],


            "domain": row[2],


            "task": row[3],


            "domain_scores": row[4],


            "task_scores": row[5],


            "keywords": row[6],


            "abstract": row[7],


            "objectives": row[8],


            "methodology": row[9],


            "embedding_text": row[10]

        }


    # -------------------------------------------------
    # Domain-filtered lookup
    # -------------------------------------------------

    def get_projects_by_domain(
        self,
        domain,
        top_k=20
    ):

        """
        Returns projects where `domain` appears anywhere in their ranked
        domain_scores (primary OR secondary), not just projects whose
        single top-scoring domain happens to match. This is what makes
        multi-domain projects discoverable under each domain they
        genuinely touch, instead of only their single strongest one.
        """

        with self.connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT

                    document_id,
                    project_title,
                    domain,
                    task,
                    domain_scores,
                    task_scores

                FROM project_profiles

                WHERE domain_scores @> %s::jsonb

                OR domain = %s

                LIMIT %s
                """,
                (
                    Json([{"domain": domain}]),
                    domain,
                    top_k
                )
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "project_title": row[1],
                "domain": row[2],
                "task": row[3],
                "domain_scores": row[4],
                "task_scores": row[5],
            }
            for row in rows
        ]



    # -------------------------------------------------
    # Utility
    # -------------------------------------------------

    def count(self):

        with self.connection.cursor() as cursor:


            cursor.execute(

                """

                SELECT COUNT(*)

                FROM project_profiles

                """

            )


            return cursor.fetchone()[0]



    def describe(self):

        return (

            "PostgreSQL + pgvector "

            f"(table=project_profiles, "

            f"embedding={config.EMBEDDING_MODEL}, "

            "metric=cosine)"

        )
