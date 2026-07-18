"""
PostgreSQL + pgvector content-level vector storage.

Stores semantic document chunks in PostgreSQL using pgvector embeddings.

One PDF produces many records in document_chunks table.

Used for:
- semantic retrieval
- RAG context retrieval
- detailed document question answering
"""


from sentence_transformers import SentenceTransformer
import psycopg
from psycopg.types.json import Json
from pgvector.psycopg import register_vector

from . import config
from .logger import get_logger


logger = get_logger()



class PostgreSQLVectorStore:


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
            "Connected to PostgreSQL pgvector content store"
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

            text

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
    # Delete existing chunks of a document
    # -------------------------------------------------

    def delete_by_document_id(
        self,
        document_id
    ):


        with self.connection.cursor() as cursor:


            cursor.execute(

                """
                DELETE FROM document_chunks
                WHERE document_id = %s
                """,

                (
                    document_id,
                )

            )


        self.connection.commit()



    # -------------------------------------------------
    # Insert document chunks
    # -------------------------------------------------

    def index_chunks(
        self,
        document_id,
        payloads
    ):


        if not payloads:

            return



        self.delete_by_document_id(
            document_id
        )



        texts = [

            self.clean_text(
                record.get(
                    "content",
                    ""
                )
            )

            for record in payloads

        ]



        embeddings = self.model.encode(

            texts,

            normalize_embeddings=True

        )



        with self.connection.cursor() as cursor:



            for record, embedding in zip(

                payloads,

                embeddings

            ):


                metadata = record.get(

                    "metadata",

                    {}

                )



                try:

                    cursor.execute(

                        """

                        INSERT INTO document_chunks

                        (

                            document_id,

                            chunk_index,

                            page_number,

                            page_type,

                            chapter,

                            chapter_title,

                            section_number,

                            section_title,

                            content,

                            estimated_tokens,

                            character_count,

                            embedding_model,

                            pipeline_version,

                            metadata,

                            embedding

                        )


                        VALUES

                        (

                            %s,%s,%s,%s,%s,

                            %s,%s,%s,%s,%s,

                            %s,%s,%s,%s,%s

                        )


                        ON CONFLICT

                        (

                            document_id,

                            chunk_index

                        )


                        DO UPDATE SET


                            page_number = EXCLUDED.page_number,

                            page_type = EXCLUDED.page_type,

                            chapter = EXCLUDED.chapter,

                            chapter_title = EXCLUDED.chapter_title,

                            section_number = EXCLUDED.section_number,

                            section_title = EXCLUDED.section_title,

                            content = EXCLUDED.content,

                            estimated_tokens = EXCLUDED.estimated_tokens,

                            character_count = EXCLUDED.character_count,

                            embedding_model = EXCLUDED.embedding_model,

                            pipeline_version = EXCLUDED.pipeline_version,

                            metadata = EXCLUDED.metadata,

                            embedding = EXCLUDED.embedding


                        """,
                                                (

                            document_id,


                            record.get(
                                "chunk_index",
                                0
                            ),


                            record.get(
                                "page_number",
                                0
                            ),


                            record.get(
                                "page_type",
                                "content"
                            ),


                            record.get(
                                "hierarchy",
                                {}
                            ).get(
                                "chapter",
                                ""
                            ),


                            record.get(
                                "hierarchy",
                                {}
                            ).get(
                                "chapter_title",
                                ""
                            ),


                            record.get(
                                "hierarchy",
                                {}
                            ).get(
                                "section_number",
                                ""
                            ),


                            record.get(
                                "hierarchy",
                                {}
                            ).get(
                                "section_title",
                                ""
                            ),


                            self.clean_text(
                                record.get(
                                    "content",
                                    ""
                                )
                            ),


                            record.get(
                                "estimated_tokens",
                                0
                            ),


                            len(
                                self.clean_text(
                                    record.get(
                                        "content",
                                        ""
                                    )
                                )
                            ),


                            config.EMBEDDING_MODEL,


                            config.PIPELINE_VERSION,


                            Json(
                                metadata
                            ),


                            embedding.tolist()

                        )

                    )


                except Exception as e:


                    print(
                        "\n========== CHUNK INSERT FAILED =========="
                    )


                    print(
                        "Document ID:",
                        document_id
                    )


                    print(
                        "Chunk:",
                        record.get(
                            "chunk_index"
                        )
                    )


                    print(
                        "Page:",
                        record.get(
                            "page_number"
                        )
                    )


                    print(
                        "Content preview:"
                    )


                    print(
                        self.clean_text(
                            record.get(
                                "content",
                                ""
                            )
                        )[:300]
                    )


                    print(
                        "\nMetadata:"
                    )


                    print(
                        metadata
                    )


                    print(
                        "\nERROR:"
                    )


                    print(
                        e
                    )


                    self.connection.rollback()


                    raise




        try:

            self.connection.commit()


        except Exception:

            self.connection.rollback()

            raise




        logger.info(

            f"Indexed {len(payloads)} chunks "
            f"for document_id={document_id}"

        )



    # -------------------------------------------------
    # Compatibility wrapper
    # -------------------------------------------------

    def index_document(

        self,

        document_id,

        payloads

    ):


        self.index_chunks(

            document_id,

            payloads

        )



    # -------------------------------------------------
    # Semantic Search
    # -------------------------------------------------

    def search(

        self,

        query,

        top_k=5,

        distance_threshold=0.60

    ):


        query_embedding = self.model.encode(

            query,

            normalize_embeddings=True

        )



        with self.connection.cursor() as cursor:


            cursor.execute(

                """

                SELECT


                    dc.content,


                    d.filename,


                    d.project_title,


                    dc.page_number,


                    dc.page_type,


                    dc.chapter,


                    dc.chapter_title,


                    dc.section_number,


                    dc.section_title,


                    dc.embedding <=> %s AS distance



                FROM document_chunks dc


                JOIN documents d

                ON dc.document_id = d.id



                ORDER BY dc.embedding <=> %s



                LIMIT %s


                """,


                (

                    query_embedding,


                    query_embedding,


                    top_k

                )

            )



            rows = cursor.fetchall()



        documents = []

        metadatas = []

        distances = []



        for row in rows:


            distance = float(

                row[-1]

            )


            if distance <= distance_threshold:



                documents.append(

                    row[0]

                )


                metadatas.append(

                    {


                        "filename": row[1],


                        "project_title": row[2],


                        "page_number": row[3],


                        "page_type": row[4],


                        "chapter": row[5],


                        "chapter_title": row[6],


                        "section_number": row[7],


                        "section_title": row[8]

                    }

                )


                distances.append(

                    distance

                )



        return {


            "documents": [

                documents

            ],


            "metadatas": [

                metadatas

            ],


            "distances": [

                distances

            ]

        }



    # -------------------------------------------------
    # Distance interpretation
    # -------------------------------------------------

    @staticmethod
    def classify_distance(

        distance

    ):


        if distance <= 0.25:

            return "VERY SIMILAR"


        elif distance <= 0.45:

            return "RELATED"


        else:

            return "WEAK"



    # -------------------------------------------------
    # Utilities
    # -------------------------------------------------

    def count(

        self

    ):


        with self.connection.cursor() as cursor:


            cursor.execute(

                """

                SELECT COUNT(*)

                FROM document_chunks

                """

            )


            return cursor.fetchone()[0]



    def describe(

        self

    ):


        return (

            "PostgreSQL + pgvector "

            f"(table=document_chunks, "

            f"embedding={config.EMBEDDING_MODEL}, "

            "metric=cosine)"

        )