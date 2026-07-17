import json


from src.ingestion.vector_store import StatefulVectorPipeline
from src.ingestion.project_vector_store import ProjectVectorStore

from src.evaluation.retrieval_metrics import RetrievalEvaluator



def run(
    store,
    file,
    mode
):


    with open(
        file,
        encoding="utf-8"
    ) as f:

        queries = json.load(f)



    evaluator = RetrievalEvaluator(
        store,
        mode
    )


    results = []


    for q in queries:


        result = evaluator.evaluate(

            q["query"],

            q["relevant"],

            k=3

        )


        results.append(result)



    print("\n======================")
    print(mode.upper(), "RETRIEVAL")
    print("======================")


    for metric in [

        "precision",
        "recall",
        "mrr",
        "map",
        "distance"

    ]:


        values = [

            r[metric]

            for r in results

            if r[metric] == r[metric]

        ]


        if values:

            avg = sum(values) / len(values)

        else:

            avg = 0



        print(

            metric.upper(),

            ":",

            round(avg, 4)

        )





# CONTENT LEVEL

content_store = StatefulVectorPipeline()


run(

    content_store,

    "src/evaluation/content_test_queries.json",

    "content"

)



# PROJECT LEVEL

project_store = ProjectVectorStore()


run(

    project_store,

    "src/evaluation/project_test_queries.json",

    "project"

)