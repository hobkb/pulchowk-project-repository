#!/usr/bin/env python

"""
Interactive content-level semantic search testing.

Retrieves document chunks from ChromaDB.
"""


import sys
import warnings

warnings.filterwarnings("ignore")


from src.ingestion.vector_store import StatefulVectorPipeline



def classify_distance(distance):

    if distance <= 0.25:
        return "VERY SIMILAR"

    elif distance <= 0.45:
        return "RELATED"

    return "LOW MATCH"



def similarity_score(distance):

    score = max(
        0,
        1-distance
    )

    return round(
        score*100,
        2
    )



def query_content(query):


    store = StatefulVectorPipeline()


    results = store.search(
        query,
        top_k=5
    )


    print("\n==============================")
    print("CONTENT SEARCH RESULTS")
    print("==============================")


    print("\nQuery:")
    print(query)



    for rank in range(
        len(results["documents"][0])
    ):


        metadata = results["metadatas"][0][rank]

        distance = results["distances"][0][rank]



        print("\n------------------------------")

        print(
            "Rank:",
            rank+1
        )


        print(
            "Source:",
            metadata.get(
                "source_file",
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


        print("\nContent preview:")

        print(
            results["documents"][0][rank][:500]
        )



if __name__=="__main__":


    if len(sys.argv)>1:

        query_content(
            " ".join(sys.argv[1:])
        )

    else:

        query=input(
            "Enter content query: "
        )

        if query:

            query_content(query)