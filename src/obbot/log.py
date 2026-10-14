from __future__ import annotations

import sys

from loguru import logger

from obbot import RUNTIME_DIR


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, format="{time:HH:mm:ss} | {level:<7} | {message}")
    logger.add(
        RUNTIME_DIR / "logs" / "obbot_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
    )
