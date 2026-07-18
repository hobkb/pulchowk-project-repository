# src/ingestion/domain_classifier.py

from .logger import get_logger
from .ontology_scoring import classify, classify_with_scores

logger = get_logger()

# Configured domain ontology with weighted signals.
DOMAIN_ONTOLOGY = {

    "Computer Vision & Image Processing": {
        "positive": {
            "yolo": 5, "opencv": 5, "image": 3, "images": 3, "video": 3,
            "camera": 4, "cnn": 2, "segmentation": 4, "ocr": 4,
            "object detection": 5, "face recognition": 5, "image classification": 5,
            "resnet": 3, "mobilenet": 3, "efficientnet": 3, "mask rcnn": 5,
            "unet": 4, "deeplab": 4, "pixel": 3, "gan": 1,
            "helmet": 4, "ppe detection": 5, "surveillance": 4, "cctv": 4,
            "anomaly detection": 3, "number plate": 5, "license plate": 5,
            "haar cascade": 3, "yolov5": 5, "yolov8": 5, "bounding box": 4,
            "video frame": 3, "video surveillance": 5,
        },
        "negative": {
            "audio": 5, "music": 5, "speech": 5, "waveform": 5, "mel": 4,
            "nlp": 3, "text translation": 4, "natural language": 4,
        }
    },

    "Audio & Speech Processing": {
        "positive": {
            "audio": 5, "music": 5, "speech": 5, "voice": 4, "speaker": 4,
            "speech recognition": 5, "speech synthesis": 5, "spectrogram": 5,
            "waveform": 5, "mel": 5, "mfcc": 5, "midi": 4, "sound": 3,
            "noise reduction": 4, "voice activity detection": 5, "gan": 2,
            "music generation": 6, "melody": 4, "audio synthesis": 5,
        },
        "negative": {
            "image classification": 5, "object detection": 5, "yolo": 5,
            "camera": 3, "video stream": 3, "pixel": 4,
        }
    },

    "Natural Language Processing": {
        "positive": {
            "bert": 5, "transformer": 5, "text": 4, "sentence": 4,
            "language": 4, "nlp": 5, "llm": 5, "gpt": 5, "tokenization": 4,
            "tokenizer": 4, "embedding": 5, "sentence transformer": 5,
            "semantic": 4, "retrieval": 4, "rag": 5, "question answering": 5,
            "chatbot": 4, "translation": 4, "summarization": 4,
            "named entity recognition": 5, "ner": 5, "corpus": 4, "sentiment": 4,
            "sentiment analysis": 6, "topic modeling": 6, "topic model": 6,
            "keyphrase": 5, "keyword extraction": 4, "lda": 4, "word2vec": 4,
            "glove": 3, "pos tagging": 3, "text classification": 4,
            "text summarization": 4, "opinion mining": 4, "question generation": 5,
        },
        "negative": {
            "pixel": 4, "image": 3, "spectrogram": 5, "audio": 3, "waveform": 4,
        }
    },

    "Cybersecurity": {
        "positive": {
            "cybersecurity": 5, "security": 4, "malware": 5, "phishing": 5,
            "intrusion": 5, "ids": 5, "ips": 5, "firewall": 5, "attack": 4,
            "threat": 4, "vulnerability": 5, "encryption": 4, "cryptography": 5,
            "authentication": 4, "authorization": 4, "digital forensics": 5,
        },
        "negative": {
            "image segmentation": 4, "speech synthesis": 4,
        }
    },

    "Healthcare & Biomedical AI": {
        "positive": {
            "medical": 5, "healthcare": 5, "patient": 4, "doctor": 3,
            "disease": 4, "diagnosis": 5, "clinical": 4, "ecg": 5, "eeg": 5,
            "ppg": 5, "mri": 5, "ct scan": 5, "tumor": 5, "blood": 3,
            "heart": 4, "heart rate": 6, "vital sign": 5, "pulse rate": 5,
            "wearable": 3, "biomedical signal": 5, "physiological": 4,
        },
        "negative": {
            "router": 4, "switch": 4,
        }
    },

    "Networking & SDN": {
        "positive": {
            "network": 4, "networking": 4, "sdn": 5,
            "software defined network": 5, "controller": 4, "routing": 4,
            "router": 4, "switch": 4, "qos": 5, "packet": 4, "latency": 4,
            "throughput": 4, "bandwidth": 4, "tcp": 3, "udp": 3,
        },
        "negative": {
            "image": 3, "speech": 3,
        }
    },

    "Internet of Things & Embedded Systems": {
        "positive": {
            "iot": 5, "internet of things": 5, "arduino": 5, "esp32": 5,
            "esp8266": 5, "raspberry pi": 5, "microcontroller": 5,
            "sensor": 4, "embedded": 4, "firmware": 4, "actuator": 4,
        },
        "negative": {
            "bert": 4, "sentence": 4,
        }
    },

    "Web & Software Engineering": {
        "positive": {
            "django": 5, "react": 5, "angular": 4, "vue": 4, "flutter": 5,
            "backend": 4, "frontend": 4, "rest api": 5, "api": 3,
            "database": 4, "postgresql": 5, "mysql": 4, "mongodb": 4,
            "software engineering": 5, "web application": 5,
        },
        "negative": {
            "segmentation": 4, "speech recognition": 4,
            # A project can mention its tech stack in passing without being
            # ABOUT web engineering -- if it's strongly about a specific AI
            # task, don't let "database" or "api" steal the domain from it.
            "face recognition": 3, "object detection": 3, "sentiment analysis": 3,
            "heart rate": 3, "topic modeling": 3,
        }
    },

    "Data Science & Analytics": {
        "positive": {
            "analytics": 5, "analysis": 3, "dashboard": 4, "visualization": 4,
            "prediction": 4, "forecasting": 5, "regression": 4, "clustering": 4,
            "time series": 5, "statistics": 4, "business intelligence": 5,
        },
        "negative": {
            "object detection": 4, "speech synthesis": 4,
        }
    },

    "Robotics & Automation": {
        "positive": {
            "robot": 5, "robotics": 5, "autonomous": 5, "navigation": 4,
            "path planning": 5, "slam": 5, "localization": 4,
            "manipulator": 4, "arm": 3, "automation": 4,
        },
        "negative": {
            "bert": 4, "translation": 4,
        }
    },

    "Recommendation & Expert Systems": {
        "positive": {
            "recommendation": 5, "recommender": 5, "collaborative filtering": 5,
            "content-based filtering": 5, "personalized": 4, "personalization": 4,
            "e-commerce": 5, "ecommerce": 5, "expert system": 5,
            "inference engine": 4, "rule-based": 3, "knowledge base": 4,
            "product recommendation": 5, "user preference": 3,
            "job matching": 5, "resume": 4, "recruitment": 4, "candidate": 3,
            "cv screening": 4, "matchmaking": 4,
        },
        "negative": {
            "image classification": 3, "speech recognition": 3,
        }
    },

}

DEFAULT_DOMAIN = "General Computer Science & Engineering"


def classify_project_domain(text: str) -> str:
    """
    Analyzes project context to map it to a specific academic domain.
    Utilizes positive keyword frequencies against strict negative constraints.
    """
    return classify(text, DOMAIN_ONTOLOGY, DEFAULT_DOMAIN, logger=logger, label="Domain")


def classify_project_domain_full(text: str, top_k: int = 5):
    """
    Same decision as classify_project_domain(), but also returns every
    domain that scored above zero, ranked descending.

    Returns:
        (primary_domain, ranked) where ranked is [(domain, score), ...].
        Lets callers persist secondary/related domains (e.g. a project that
        is both "Healthcare & Biomedical AI" and "Internet of Things &
        Embedded Systems") instead of being forced into a single bucket.
    """
    return classify_with_scores(
        text, DOMAIN_ONTOLOGY, DEFAULT_DOMAIN, logger=logger, label="Domain", top_k=top_k
    )
