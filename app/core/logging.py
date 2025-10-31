"""Logging configuration."""
import logging
import sys
from pythonjsonlogger import jsonlogger

from app.core.config import settings


def setup_logging():
    """Configure application logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers
    logger.handlers = []

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Use JSON formatter for production, simple formatter for debug
    if settings.debug:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        formatter = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


# Initialize logger
logger = setup_logging()
