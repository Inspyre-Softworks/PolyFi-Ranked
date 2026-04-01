"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    logging_utils.py

Description:
    Logging helpers backed by inspy-logger.

Functions:
    configure_logging:
        Build and configure the application logger.

Constants:
    LOGGER_NAME:
        Canonical logger name for the application.

Dependencies:
    logging
    pathlib
    inspy_logger

Example Usage:
    logger = configure_logging('INFO', 'logs/app.log')
"""

from __future__ import annotations

import logging
from pathlib import Path

from inspy_logger import InspyLogger


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
    logger.handlers.clear()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False

    log_path = Path(log_file).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    inspy_logger = InspyLogger(
        LOGGER_NAME,
        console_level=log_level.upper(),
        file_level=log_level.upper(),
        file_name=log_path.name,
        file_path=log_path.parent,
        announce_on_init=False,
    )
    return inspy_logger.logger
