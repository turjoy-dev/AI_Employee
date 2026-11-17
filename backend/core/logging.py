"""Structured and secure application logging configuration."""

import logging
import sys
from typing import Optional


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_level: Optional[str] = "INFO") -> None:
    """Configure the root application logger with a structured format and secure handlers."""
    level = getattr(logging, (log_level or "INFO").upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    else:
        for handler in root_logger.handlers:
            handler.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance configured for the application."""
    return logging.getLogger(name)
