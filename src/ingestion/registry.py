"""
Ingestion Registry Manager.

Tracks indexed PDF documents using SHA-256 hashes.

Used by PostgreSQL + pgvector ingestion pipeline for:

- duplicate detection
- modified document detection
- incremental re-indexing
- ingestion history tracking

The registry is independent from vector storage.

Vector data is stored in:

- document_chunks      -> content-level embeddings
- project_profiles     -> project-level embeddings
"""


import json


from .logger import get_logger


logger = get_logger()





class IngestionRegistry:
    """
    Manages document ingestion state.

    Registry format:

    {
        "documents": {

            "<sha256>": {

                "sha256": "...",

                "filename": "...",

                "document_id": 12,

                "chunk_count": 123,

                "timestamp": "..."

            }

        }
    }
    """



    def __init__(
        self,
        registry_path
    ):

        self.registry_path = registry_path

        self.registry = self.load()





    # -------------------------------------------------
    # Create empty registry
    # -------------------------------------------------

    def create_empty_registry(self):

        return {

            "documents": {}

        }





    # -------------------------------------------------
    # Load registry
    # -------------------------------------------------

    def load(self):


        if not self.registry_path.exists():


            registry = self.create_empty_registry()



            self.registry_path.parent.mkdir(

                parents=True,

                exist_ok=True

            )



            with open(

                self.registry_path,

                "w",

                encoding="utf-8"

            ) as file:


                json.dump(

                    registry,

                    file,

                    indent=4

                )



            return registry





        try:


            with open(

                self.registry_path,

                "r",

                encoding="utf-8"

            ) as file:


                registry = json.load(file)



            if "documents" not in registry:


                registry["documents"] = {}



            return registry



        except Exception as error:


            logger.warning(

                f"Registry load failed: {error}. Creating new registry."

            )


            return self.create_empty_registry()





    # -------------------------------------------------
    # Save registry
    # -------------------------------------------------

    def save(self):


        self.registry_path.parent.mkdir(

            parents=True,

            exist_ok=True

        )



        with open(

            self.registry_path,

            "w",

            encoding="utf-8"

        ) as file:


            json.dump(

                self.registry,

                file,

                indent=4

            )





    # -------------------------------------------------
    # Lookup operations
    # -------------------------------------------------

    def document_exists(
        self,
        sha256
    ):

        return (

            sha256

            in self.registry["documents"]

        )





    def get_document(
        self,
        sha256
    ):


        return self.registry["documents"].get(

            sha256

        )





    def find_by_filename(
        self,
        filename
    ):

        """
        Finds previously indexed document.

        Returns:

        NEW:
            (None, None)

        DUPLICATE:
            (old_sha256, record)

        MODIFIED:
            (old_sha256, old_record)

        """


        for sha256, record in self.registry["documents"].items():


            if record.get(

                "filename"

            ) == filename:


                return sha256, record





        return None, None





    # -------------------------------------------------
    # Insert document
    # -------------------------------------------------

    def add_document(
        self,
        document_data
    ):


        sha256 = document_data["sha256"]



        self.registry["documents"][sha256] = document_data



        self.save()



        logger.info(

            f"Registered document: {sha256}"

        )





    # -------------------------------------------------
    # Replace modified document
    # -------------------------------------------------

    def replace_document(
        self,
        old_sha256,
        document_data
    ):


        if (

            old_sha256

            and

            old_sha256 in self.registry["documents"]

        ):


            del self.registry["documents"][old_sha256]



        self.add_document(

            document_data

        )





    # -------------------------------------------------
    # Update metadata
    # -------------------------------------------------

    def update_document(
        self,
        sha256,
        updates
    ):


        if sha256 in self.registry["documents"]:


            self.registry["documents"][sha256].update(

                updates

            )


            self.save()



            logger.info(

                f"Updated registry: {sha256}"

            )





    # -------------------------------------------------
    # Remove document
    # -------------------------------------------------

    def remove_document(
        self,
        sha256
    ):


        if sha256 in self.registry["documents"]:


            del self.registry["documents"][sha256]



            self.save()



            logger.info(

                f"Removed registry entry: {sha256}"

            )





    # -------------------------------------------------
    # List documents
    # -------------------------------------------------

    def list_documents(
        self
    ):


        return list(

            self.registry["documents"].values()

        )





    # -------------------------------------------------
    # Clear registry
    # -------------------------------------------------

    def clear(
        self
    ):


        self.registry = self.create_empty_registry()



        self.save()



        logger.info(

            "Registry cleared"

        )





    # -------------------------------------------------
    # Statistics
    # -------------------------------------------------

    def total_documents(
        self
    ):


        return len(

            self.registry["documents"]

        )