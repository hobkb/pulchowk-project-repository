#!/usr/bin/env python

"""
Interactive content-level semantic search testing.

Retrieves document chunks from PostgreSQL + pgvector.
"""


import sys
import warnings

warnings.filterwarnings("ignore")


from src.ingestion.postgres_vector_store import PostgreSQLVectorStore





def classify_distance(distance):


    if distance <= 0.30:

        return "VERY SIMILAR"


    elif distance <= 0.55:

        return "RELATED"


    return "LOW MATCH"





def similarity_score(distance):


    score = max(
        0,
        1 - distance
    )


    return round(
        score * 100,
        2
    )





def query_content(query):


    store = PostgreSQLVectorStore()



    results = store.search(

        query,

        top_k=5

    )



    documents = results.get(
        "documents",
        [[]]
    )[0]


    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]


    distances = results.get(
        "distances",
        [[]]
    )[0]





    print("\n==============================")
    print("CONTENT SEARCH RESULTS")
    print("==============================")


    print("\nQuery:")
    print(query)



    if not documents:


        print(
            "\nNo matching chunks found."
        )

        return





    for rank, document in enumerate(

        documents,

        1

    ):


        metadata = metadatas[rank - 1]

        distance = distances[rank - 1]



        print(
            "\n------------------------------"
        )


        print(
            "Rank:",
            rank
        )



        print(
            "File:",
            metadata.get(
                "filename",
                ""
            )
        )



        print(
            "Project:",
            metadata.get(
                "project_title",
                ""
            )
        )



        print(
            "Page Type:",
            metadata.get(
                "page_type",
                ""
            )
        )



        print(
            "Chapter:",
            metadata.get(
                "chapter_title",
                ""
            )
        )



        print(
            "Section:",
            metadata.get(
                "section_title",
                ""
            )
        )



        print(
            "Page:",
            metadata.get(
                "page_number",
                ""
            )
        )



        print(
            "Distance:",
            round(
                distance,
                4
            )
        )



        print(
            "Similarity:",
            classify_distance(distance)
        )



        print(
            "Score:",
            similarity_score(distance),
            "%"
        )



        print(
            "\nContent preview:"
        )


        print(
            document[:500]
        )





if __name__ == "__main__":



    if len(sys.argv) > 1:


        query_content(

            " ".join(sys.argv[1:])

        )


    else:


        query = input(
            "Enter content query: "
        )


        if query:


            query_content(
                query
            )