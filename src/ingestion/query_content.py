"""
Content Semantic Search Tester.

Developer tool for testing CONTENT-LEVEL embeddings only.

Uses:
PostgreSQL + pgvector document_chunks table
"""


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





def query_content(
    query_text,
    top_k=5,
    show_details=False
):


    store = PostgreSQLVectorStore()



    total = store.count()



    results = store.search(

        query_text,

        top_k=top_k

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





    print(
        "\n" + "=" * 70
    )


    print(
        "CONTENT SEARCH RESULTS"
    )


    print(
        "=" * 70
    )


    print(
        f"QUERY: {query_text}"
    )


    print(
        f"CONTENT CHUNKS DATABASE: {total}"
    )





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
            "\n" + "-" * 70
        )


        print(
            f"Rank: {rank}"
        )



        print(
            "File:",
            metadata.get(
                "filename",
                "UNKNOWN"
            )
        )



        print(
            "Project:",
            metadata.get(
                "project_title",
                "UNKNOWN"
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
            f"Distance: {distance:.4f}"
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





        if show_details:


            print(
                "\nContent Preview:"
            )


            print(
                document[:500]
            )



        print(
            "-" * 70
        )







if __name__ == "__main__":


    while True:


        query = input(
            "\nSearch content (type exit): "
        )



        if query.lower() == "exit":

            break



        if query.strip():


            query_content(

                query,

                top_k=5,

                show_details=True

            )