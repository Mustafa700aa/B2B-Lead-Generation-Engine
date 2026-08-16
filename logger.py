"""
Centralized logging module for the B2B Lead Generation Engine.
Configures synchronized console and rotating file logging with thread-safe formatting.
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from config import (
    LOG_FILE_PATH,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    LOG_FORMAT,
    LOG_DATE_FORMAT,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class CustomFormatter(logging.Formatter):
    """
    Console log formatter with clean ANSI color highlighting for distinct log levels.
    """
    GREY = "\x1b[38;20m"
    BLUE = "\x1b[34;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: GREY + LOG_FORMAT + RESET,
        logging.INFO: GREEN + LOG_FORMAT + RESET,
        logging.WARNING: YELLOW + LOG_FORMAT + RESET,
        logging.ERROR: RED + LOG_FORMAT + RESET,
        logging.CRITICAL: BOLD_RED + LOG_FORMAT + RESET,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno, LOG_FORMAT)
        formatter = logging.Formatter(log_fmt, datefmt=LOG_DATE_FORMAT)
        return formatter.format(record)


def setup_logger(
    name: str = "LeadEngine",
    level: Optional[str] = None
) -> logging.Logger:
    """
    Initialize and return a named logger configured with both console
    and rotating file handlers. Prevents duplicate handlers.

    :param name: Logger module name
    :param level: Optional log level override (e.g. 'DEBUG', 'INFO')
    :return: Configured logging.Logger instance
    """
    logger = logging.getLogger(name)
    log_level = getattr(logging, (level or LOG_LEVEL).upper(), logging.INFO)
    logger.setLevel(log_level)

    # Avoid attaching multiple handlers if logger is already configured
    if logger.hasHandlers():
        return logger

    # 1. Console Handler with Color Formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(CustomFormatter())
    logger.addHandler(console_handler)

    # 2. Rotating File Handler (Standard clean format, UTF-8)
    try:
        file_handler = RotatingFileHandler(
            filename=str(LOG_FILE_PATH),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize rotating file logger at {LOG_FILE_PATH}: {e}")

    return logger


def get_logger(name: str = "LeadEngine") -> logging.Logger:
    """
    Convenience helper to retrieve configured logger.
    """
    return setup_logger(name)
