"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    logging_utils.py

Description:
    Logging helpers for console and rotating file logging.

Functions:
    configure_logging:
        Build and configure the application logger.

Constants:
    LOGGER_NAME:
        Canonical logger name for the application.

Dependencies:
    logging
    logging.handlers
    pathlib

Example Usage:
    logger = configure_logging('INFO', 'logs/app.log')
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAME = 'polyfi_ranked'


def configure_logging(log_level: str, log_file: str) -> logging.Logger:
    """
    Configure and return the shared application logger.

    Parameters:
        log_level:
            Logging level such as INFO or DEBUG.
        log_file:
            Destination path for the rotating file log.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()

    Path(log_file).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        Path(log_file).expanduser().resolve(),
        maxBytes=1_000_000,
        backupCount=3,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
