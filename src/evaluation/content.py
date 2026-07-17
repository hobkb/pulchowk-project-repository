import json
import numpy as np

import psycopg

from sentence_transformers import SentenceTransformer

from src.ingestion.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
)



# -------------------------------------------------
# Paths
# -------------------------------------------------

INPUT_FILE = (
    "src/evaluation/content_test_queries.json"
)


OUTPUT_FILE = (
    "src/evaluation/content_test_queries_fixed.json"
)



# -------------------------------------------------
# Load PostgreSQL Metadata
# -------------------------------------------------

connection = psycopg.connect(

    host=POSTGRES_HOST,

    port=POSTGRES_PORT,

    dbname=POSTGRES_DB,

    user=POSTGRES_USER,

    password=POSTGRES_PASSWORD

)



with connection.cursor() as cursor:


    cursor.execute(

        """
        SELECT DISTINCT

            project_title,

            source_file


        FROM document_chunks


        WHERE project_title IS NOT NULL

        AND source_file IS NOT NULL

        """

    )


    rows = cursor.fetchall()



connection.close()



projects = {}



for title, source in rows:


    if title and source:

        projects[title] = source



print(
    "Projects found:",
    len(projects)
)



project_titles = list(
    projects.keys()
)



# -------------------------------------------------
# Load Embedding Model
# -------------------------------------------------

model = SentenceTransformer(

    "sentence-transformers/all-MiniLM-L6-v2"

)



project_embeddings = model.encode(

    project_titles,

    normalize_embeddings=True

)



# -------------------------------------------------
# Load Queries
# -------------------------------------------------

with open(

    INPUT_FILE,

    "r",

    encoding="utf-8"

) as f:


    queries = json.load(f)



# -------------------------------------------------
# Generate Relevant Field
# -------------------------------------------------

for item in queries:


    query = item["query"]


    query_embedding = model.encode(

        query,

        normalize_embeddings=True

    )



    similarities = np.dot(

        project_embeddings,

        query_embedding

    )



    best_index = int(

        np.argmax(similarities)

    )



    best_project = project_titles[

        best_index

    ]


    best_file = projects[

        best_project

    ]



    item["relevant"] = [

        best_file

    ]



    print(

        "\nQuery:",

        query

    )


    print(

        "Matched:",

        best_project

    )


    print(

        "Score:",

        round(

            float(

                similarities[best_index]

            ),

            4

        )

    )



# -------------------------------------------------
# Save
# -------------------------------------------------

with open(

    OUTPUT_FILE,

    "w",

    encoding="utf-8"

) as f:


    json.dump(

        queries,

        f,

        indent=4,

        ensure_ascii=False

    )



print(

    "\nGenerated:",

    OUTPUT_FILE

)