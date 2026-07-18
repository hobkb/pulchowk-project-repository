# src/ingestion/task_classifier.py

from .logger import get_logger
from .ontology_scoring import classify, classify_with_scores

logger = get_logger()

# Task ontology -- what KIND of AI/CS task a project performs, independent
# of which domain it's in (e.g. "Prediction" applies whether you're
# predicting heart rate or stock prices).
TASK_ONTOLOGY = {

    "Object Detection": {
        "positive": {
            "yolo": 5, "bounding box": 5, "detection": 3, "localization": 4,
            "faster rcnn": 5, "ssd": 4, "anchor box": 4, "object detection": 6,
        },
        "negative": {
            "classification": 2,
        }
    },

    "Recognition": {
        "positive": {
            "recognition": 5, "face recognition": 6, "identity": 4,
            "face embedding": 5, "facenet": 5, "identification": 4,
        },
        "negative": {}
    },

    "Segmentation": {
        "positive": {
            "segmentation": 6, "mask": 4, "pixel-wise": 4, "unet": 5,
            "semantic segmentation": 6, "instance segmentation": 6,
        },
        "negative": {}
    },

    "Prediction & Forecasting": {
        "positive": {
            "prediction": 5, "forecast": 5, "forecasting": 5, "regression": 4,
            "time series": 5, "estimate": 3, "estimation": 3,
        },
        "negative": {
            "classification": 2,
        }
    },

    "Classification": {
        "positive": {
            "classification": 5, "categorization": 4, "classifier": 4,
            "multiclass": 3, "binary classification": 5,
        },
        "negative": {}
    },

    "Semantic Similarity & Matching": {
        "positive": {
            "similarity": 6, "semantic matching": 6, "sbert": 5,
            "cosine similarity": 5, "matching": 3, "duplicate detection": 5,
        },
        "negative": {}
    },

    "Content Generation": {
        "positive": {
            "generation": 5, "generative": 5, "synthesis": 5,
            "music generation": 6, "text generation": 6, "image generation": 6,
            "gan": 4, "vae": 4, "diffusion model": 5,
        },
        "negative": {}
    },

    "Anomaly Detection": {
        "positive": {
            "anomaly": 6, "outlier": 5, "novelty detection": 5,
            "fraud detection": 5, "intrusion detection": 5, "abnormal": 4,
        },
        "negative": {}
    },

    "Recommendation": {
        "positive": {
            "recommendation": 6, "recommender": 6, "collaborative filtering": 5,
            "personalized": 4, "content-based filtering": 5, "matchmaking": 4,
        },
        "negative": {}
    },

    "Sentiment Analysis": {
        "positive": {
            "sentiment": 6, "opinion mining": 5, "polarity": 4,
            "emotion detection": 4, "sentiment analysis": 7,
        },
        "negative": {}
    },

    "Topic Modeling & Text Mining": {
        "positive": {
            "topic modeling": 6, "topic model": 6, "lda": 5, "text mining": 5,
            "clustering": 3, "keyphrase": 4,
        },
        "negative": {}
    },

    "Question Answering & Generation": {
        "positive": {
            "question answering": 6, "question generation": 6, "qa system": 5,
            "chatbot": 4,
        },
        "negative": {}
    },

    "Summarization": {
        "positive": {
            "summarization": 6, "summary": 4, "abstractive": 4, "extractive": 4,
        },
        "negative": {}
    },

    "Optimization & Automation": {
        "positive": {
            "optimization": 5, "automation": 5, "automated": 4, "scheduling": 4,
            "resource allocation": 4,
        },
        "negative": {}
    },

}

DEFAULT_TASK = "General Analysis"


def classify_project_task(text: str) -> str:
    """
    Identifies the primary AI/CS task a project performs (detection,
    prediction, generation, etc.), independent of its domain.
    """
    return classify(text, TASK_ONTOLOGY, DEFAULT_TASK, logger=logger, label="Task")


def classify_project_task_full(text: str, top_k: int = 5):
    """
    Same decision as classify_project_task(), but also returns every task
    that scored above zero, ranked descending.

    Returns:
        (primary_task, ranked) where ranked is [(task, score), ...].
    """
    return classify_with_scores(
        text, TASK_ONTOLOGY, DEFAULT_TASK, logger=logger, label="Task", top_k=top_k
    )
