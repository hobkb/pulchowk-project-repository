"""
Project Similarity Search Tester.

Developer tool for testing PROJECT-LEVEL embeddings only.

Uses:
PostgreSQL + pgvector project_profiles table.

Used for:
- similar project recommendation
- project discovery
- project-level semantic retrieval
"""


from .project_vector_store import ProjectVectorStore





def classify_distance(distance):


    if distance <= 0.30:

        return "HIGHLY SIMILAR"


    elif distance <= 0.55:

        return "RELATED"


    return "LOW MATCH"





def similarity_score(distance):

    """
    Convert cosine distance into intuitive score.

    pgvector cosine distance:
    0 = identical
    1 = completely different
    """


    score = max(
        0,
        1 - distance
    )


    return round(
        score * 100,
        2
    )





def query_projects(
    query_text,
    top_k=10,
    show_details=False
):


    store = ProjectVectorStore()


    total = store.count()



    results = store.query_similar_projects(

        query_text,

        top_k=top_k

    )



    if not results:

        print(
            "\nNo projects indexed."
        )

        return





    print(
        "\n" + "="*70
    )


    print(
        f"QUERY: {query_text}"
    )


    print(
        f"PROJECT DATABASE: {total}"
    )


    print(
        "="*70
    )





    for rank, item in enumerate(
        results,
        1
    ):



        distance = item["distance"]


        metadata = item.get(
            "metadata",
            {}
        )



        title = metadata.get(
            "project_title",
            "UNKNOWN"
        )



        domain = metadata.get(
            "domain",
            "Unknown"
        )



        task = metadata.get(
            "task",
            "Unknown"
        )



        print(
            f"\n{rank}. {title}"
        )


        print(
            f"   Domain   : {domain}"
        )


        print(
            f"   Task     : {task}"
        )


        print(
            f"   Distance : {distance:.4f}"
        )


        print(
            f"   Match    : {classify_distance(distance)}"
        )


        print(
            f"   Score    : {similarity_score(distance)}%"
        )





        if show_details:


            keywords = metadata.get(
                "keywords",
                []
            )


            if isinstance(
                keywords,
                list
            ):

                keywords = ", ".join(
                    keywords
                )



            print(
                f"   Keywords : {keywords}"
            )



            print(
                f"   Abstract : "
                f"{metadata.get('abstract','')[:250]}"
            )


            print(
                f"   Methodology : "
                f"{metadata.get('methodology','')[:250]}"
            )





    print(
        "\n" + "="*70
    )









def interactive_test():


    print(
        "\nPROJECT SIMILARITY TESTER"
    )


    print(
        "Type 'exit' to stop\n"
    )



    while True:


        query = input(
            "Search project: "
        ).strip()



        if query.lower() == "exit":

            break



        query_projects(

            query,

            top_k=10,

            show_details=True

        )







if __name__ == "__main__":


    interactive_test()