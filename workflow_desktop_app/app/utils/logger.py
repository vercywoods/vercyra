import logging
from pathlib import Path

from app.config import LOG_PATH


def get_logger(name: str) -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
