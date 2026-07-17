"""
Retrieval Evaluation Metrics

Supports:

1. Content-level chunk retrieval evaluation
   PostgreSQL + pgvector document_chunks

2. Project-level similarity evaluation
   PostgreSQL + pgvector project_profiles


Metrics:

- Precision@K
- Recall@K
- MRR
- MAP
- Average Retrieval Distance
"""


import numpy as np



class RetrievalEvaluator:


    def __init__(
        self,
        vector_store,
        mode="content"
    ):

        self.vector_store = vector_store
        self.mode = mode



    # ------------------------------------------------
    # Normalize names
    # ------------------------------------------------

    @staticmethod
    def normalize(
        text
    ):

        return (
            str(text)
            .lower()
            .replace(".pdf", "")
            .replace("_", " ")
            .strip()
        )



    # ------------------------------------------------
    # Remove duplicates
    # ------------------------------------------------

    @staticmethod
    def unique(
        items
    ):

        output = []
        seen = set()


        for item in items:

            if item not in seen:

                output.append(item)
                seen.add(item)


        return output



    # ------------------------------------------------
    # Precision@K
    # ------------------------------------------------

    @staticmethod
    def precision_at_k(
        retrieved,
        relevant,
        k
    ):

        retrieved = retrieved[:k]


        if not retrieved:
            return 0


        hits = sum(
            1
            for item in retrieved
            if item in relevant
        )


        return hits / k



    # ------------------------------------------------
    # Recall@K
    # ------------------------------------------------

    @staticmethod
    def recall_at_k(
        retrieved,
        relevant,
        k
    ):


        if not relevant:
            return 0


        retrieved = retrieved[:k]


        hits = sum(
            1
            for item in retrieved
            if item in relevant
        )


        return hits / len(relevant)



    # ------------------------------------------------
    # MRR
    # ------------------------------------------------

    @staticmethod
    def reciprocal_rank(
        retrieved,
        relevant
    ):


        for index, item in enumerate(retrieved):

            if item in relevant:

                return 1 / (index + 1)


        return 0



    # ------------------------------------------------
    # MAP
    # ------------------------------------------------

    @staticmethod
    def average_precision(
        retrieved,
        relevant
    ):


        score = 0
        hits = 0


        for index,item in enumerate(retrieved):


            if item in relevant:

                hits += 1

                score += hits / (index + 1)



        if hits == 0:

            return 0



        return score / len(relevant)



    # ------------------------------------------------
    # Extract content IDs
    # ------------------------------------------------

    def extract_content_ids(
        self,
        results
    ):


        ids = []


        metadata_groups = results.get(
            "metadatas",
            [[]]
        )


        if not metadata_groups:

            return ids



        for metadata in metadata_groups[0]:


            filename = metadata.get(
                "source_file",
                ""
            )


            ids.append(
                self.normalize(filename)
            )


        return self.unique(ids)



    # ------------------------------------------------
    # Extract project IDs
    # ------------------------------------------------

    def extract_project_ids(
        self,
        results
    ):


        ids = []

        distances = []


        for item in results:


            metadata = item.get(
                "metadata",
                {}
            )


            title = metadata.get(
                "project_title",
                ""
            )


            ids.append(
                self.normalize(title)
            )


            distances.append(
                item.get(
                    "distance",
                    1.0
                )
            )


        return (
            self.unique(ids),
            distances
        )



    # ------------------------------------------------
    # Evaluate query
    # ------------------------------------------------

    def evaluate(
        self,
        query,
        relevant,
        k=5
    ):


        relevant = [

            self.normalize(item)

            for item in relevant

        ]


        distances = []



        # ==================================================
        # PROJECT LEVEL
        # ==================================================

        if self.mode == "project":


            results = self.vector_store.query_similar_projects(

                query_text=query,

                top_k=k

            )


            retrieved, distances = (

                self.extract_project_ids(
                    results
                )

            )



        # ==================================================
        # CONTENT LEVEL
        # ==================================================

        else:


            results = self.vector_store.search(

                query,

                top_k=k

            )


            retrieved = self.extract_content_ids(
                results
            )


            distances = results.get(
                "distances",
                [[]]
            )[0]



        avg_distance = (

            float(np.mean(distances))

            if distances

            else 0

        )



        return {


            "precision":

                self.precision_at_k(

                    retrieved,

                    relevant,

                    k

                ),



            "recall":

                self.recall_at_k(

                    retrieved,

                    relevant,

                    k

                ),



            "mrr":

                self.reciprocal_rank(

                    retrieved,

                    relevant

                ),



            "map":

                self.average_precision(

                    retrieved,

                    relevant

                ),



            "distance":

                avg_distance,



            "retrieved":

                retrieved

        }