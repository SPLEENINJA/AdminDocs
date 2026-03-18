"""
utils/logger.py — Logger centralisé avec Rich (console) + fichier
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console

console = Console()


def get_logger(name: str, log_dir: Path) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # déjà configuré

    logger.setLevel(logging.DEBUG)

    # ── Handler console (Rich, coloré) ────────────────────────────────────────
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_path=False,
        markup=True,
    )
    rich_handler.setLevel(logging.INFO)

    # ── Handler fichier ────────────────────────────────────────────────────────
    log_file = log_dir / f"ocr_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    ))

    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)
    return logger
