# src/ingestion/domain_classifier.py

import re
from collections import defaultdict
from .logger import get_logger

logger = get_logger()

# Configured domain ontology with weighted signals
DOMAIN_ONTOLOGY = {
    "Computer Vision & Image Processing": {
        "positive": {
            "yolo": 5, "opencv": 5, "image": 3, "video": 3, "cnn": 2, 
            "segmentation": 4, "ocr": 4, "object detection": 5, "resnet": 3,
            "face recognition": 5, "gan": 1  # GAN gets minor weight here due to image synthesis
        },
        "negative": {
            "audio": 5, "music": 5, "speech": 5, "waveform": 5, "mel": 4,
            "nlp": 3, "text translation": 4, "natural language": 4
        }
    },
    "Audio & Speech Processing": {
        "positive": {
            "audio": 5, "music": 5, "speech": 5, "mel": 5, "spectrogram": 5,
            "waveform": 5, "midi": 4, "synthesizer": 4, "voice": 3,
            "sound": 3, "gan": 2  # Deep learning music synthesis heavily leverages GANs
        },
        "negative": {
            "image classification": 5, "object detection": 5, "yolo": 5,
            "camera": 3, "video stream": 3, "pixel": 4
        }
    },
    "Natural Language Processing": {
        "positive": {
            "bert": 5, "transformer": 5, "text": 4, "sentence": 4, 
            "language": 4, "nlp": 5, "llm": 5, "sentiment": 3, 
            "tokenization": 4, "ner": 5, "translation": 4, "corpus": 4
        },
        "negative": {
            "pixel": 4, "image": 3, "spectrogram": 5, "audio": 3, "waveform": 4
        }
    }
}

DEFAULT_DOMAIN = "General Computer Science & Engineering"

def classify_project_domain(text: str) -> str:
    """
    Analyzes project context to map it to a specific academic domain.
    Utilizes positive keyword frequencies against strict negative constraints.
    """
    text_lower = text.lower()
    scores = defaultdict(float)

    for domain, rules in DOMAIN_ONTOLOGY.items():
        # 1. Accumulate Positive Weights
        pos_score = 0.0
        for term, weight in rules["positive"].items():
            # Use raw count but apply logarithmic scaling to prevent a single repetitive word from blowing up the score
            occurrences = text_lower.count(term)
            if occurrences > 0:
                pos_score += weight * (1 + (occurrences - 1) * 0.2)
        
        # 2. Subtract Negative Weights (Negative Suppression)
        neg_score = 0.0
        for term, weight in rules["negative"].items():
            occurrences = text_lower.count(term)
            if occurrences > 0:
                # Negative weights are multiplied aggressively to force suppression
                neg_score += weight * 3.0

        final_score = pos_score - neg_score
        if final_score > 0:
            scores[domain] = final_score

    if not scores:
        return DEFAULT_DOMAIN

    # Pick the domain that maintains the strongest positive signal
    assigned_domain = max(scores, key=scores.get)
    logger.info(f"Domain Scores: {dict(scores)} -> Assigned: '{assigned_domain}'")
    return assigned_domain