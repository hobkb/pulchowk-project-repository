"""
Shared logging configuration.

Every module imports `get_logger()` instead of calling `logging.basicConfig`
itself, so log setup happens exactly once no matter how many modules
import it or in what order.
"""

import logging

from .config import LOG_FILE, ensure_directories


def get_logger(name: str = "IngestionPipeline") -> logging.Logger:
    ensure_directories()
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
