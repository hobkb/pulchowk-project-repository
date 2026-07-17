#!/usr/bin/env python

"""
Interactive project-level semantic search testing.

Tests:
- Project similarity retrieval
- Ranking quality
- Chroma distance
- Metadata correctness

Usage:

python query_similar_projects.py "deep learning autonomous driving"

or

python query_similar_projects.py
"""


import sys
import warnings

warnings.filterwarnings("ignore")


from src.ingestion.project_vector_store import ProjectVectorStore



def query_projects(query):


    store = ProjectVectorStore()


    results = store.query_similar_projects(

        query_text=query,

        top_k=10

    )


    print("\n==============================")
    print("PROJECT SEARCH RESULTS")
    print("==============================")

    print("\nQuery:")
    print(query)


    for rank,item in enumerate(results,1):


        metadata = item["metadata"]


        print("\n------------------------------")

        print(
            f"Rank {rank}"
        )


        print(
            "Project:",
            metadata.get(
                "project_title",
                "UNKNOWN"
            )
        )


        print(
            "Domain:",
            metadata.get(
                "domain",
                ""
            )
        )


        print(
            "Task:",
            metadata.get(
                "task",
                ""
            )
        )


        print(
            "Distance:",
            round(
                item["distance"],
                4
            )
        )


        print(
            "Similarity:",
            item["similarity"]
        )




if __name__=="__main__":


    if len(sys.argv)>1:


        query_projects(
            " ".join(sys.argv[1:])
        )


    else:


        query=input(
            "Enter project similarity query: "
        ).strip()


        if query:

            query_projects(query)

        else:

            print(
                "No query entered."
            )