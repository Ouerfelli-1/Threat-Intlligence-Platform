"""
Structured logging utility for TIP modules.
"""
import logging
import sys
from typing import Optional

from tip.core.config import settings


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with consistent formatting.

    Args:
        name: Logger name (usually __name__ of the calling module).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name or "tip")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        logger.propagate = False

    return logger
