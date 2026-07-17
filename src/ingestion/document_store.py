"""
PostgreSQL document metadata storage.

Handles:
- documents table insertion
- retrieving document primary key
- duplicate file tracking
"""


import psycopg


from . import config
from .logger import get_logger


logger = get_logger()



class DocumentStore:


    def __init__(self):

        self.connection = psycopg.connect(

            host=config.POSTGRES_HOST,

            port=config.POSTGRES_PORT,

            dbname=config.POSTGRES_DB,

            user=config.POSTGRES_USER,

            password=config.POSTGRES_PASSWORD

        )



        logger.info(
            "Connected to PostgreSQL document store"
        )



    # -------------------------------------------------
    # Insert / update document metadata
    # -------------------------------------------------

    def upsert_document(
        self,
        filename,
        project_title,
        file_hash,
        page_count=None
    ):


        try:

            with self.connection.cursor() as cursor:


                cursor.execute(

                    """

                    INSERT INTO documents

                    (
                        filename,
                        project_title,
                        file_hash,
                        page_count
                    )


                    VALUES

                    (%s,%s,%s,%s)


                    ON CONFLICT(file_hash)

                    DO UPDATE SET


                       filename =
                        EXCLUDED.filename,


                        
                        project_title =
                        EXCLUDED.project_title,


                        page_count =
                        EXCLUDED.page_count


                    RETURNING id

                    """,

                    (

                        filename,

                        project_title,

                        file_hash,

                        page_count

                    )

                )


                document_id = cursor.fetchone()[0]



            self.connection.commit()



            logger.info(

                f"Document stored: {filename} "
                f"(id={document_id})"

            )


            return document_id



        except Exception:


            self.connection.rollback()


            logger.exception(

                f"Failed storing document: {filename}"

            )


            raise





    # -------------------------------------------------
    # Count documents
    # -------------------------------------------------

    def count(self):


        try:

            with self.connection.cursor() as cursor:


                cursor.execute(

                    """

                    SELECT COUNT(*)

                    FROM documents

                    """

                )


                return cursor.fetchone()[0]



        except Exception:


            self.connection.rollback()


            raise





    # -------------------------------------------------
    # Close connection
    # -------------------------------------------------

    def close(self):


        if self.connection:


            self.connection.close()