"""
Structured logging configuration for the trading bot.
Writes to both console (INFO+) and a rotating log file (DEBUG+).
"""

import logging
import logging.handlers
import os
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "trading_bot.log"

_configured = False


def setup_logging(log_level: str = "DEBUG") -> logging.Logger:
    """
    Configure root logger once. Subsequent calls return the existing logger.

    Args:
        log_level: File log level (default DEBUG). Console always shows INFO+.

    Returns:
        Root logger for the trading_bot package.
    """
    global _configured

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("trading_bot")

    if _configured:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── File handler (rotating, 5 MB × 3 backups) ──────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    # ── Console handler ─────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter(fmt="%(levelname)-8s %(message)s")
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    _configured = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the trading_bot namespace."""
    return logging.getLogger(f"trading_bot.{name}")
