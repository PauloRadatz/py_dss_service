"""
Logging configuration for py-dss-service.

Stage 1: Simple console and file logging.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to a log file
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class JobLogger:
    """
    Context manager for per-job logging.

    Writes job-specific logs to a dedicated file.
    """

    def __init__(self, job_id: str, logs_dir: Path):
        self.job_id = job_id
        self.log_file = logs_dir / f"{job_id}.log"
        self.logger = logging.getLogger(f"job.{job_id}")
        self.handler: Optional[logging.FileHandler] = None

    def __enter__(self) -> logging.Logger:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.handler = logging.FileHandler(self.log_file, encoding="utf-8")
        self.handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.handler is not None:
            self.handler.close()
            self.logger.removeHandler(self.handler)

