"""
Unit tests for py_dss_service.logging.
"""

import logging

import pytest

from py_dss_service.logging import JobLogger, get_logger, setup_logging


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_sets_level(self):
        setup_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_invalid_level_defaults_to_info(self):
        setup_logging(level="INVALID")
        assert logging.getLogger().level == logging.INFO


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_logger(self):
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test"


class TestJobLogger:
    """Tests for JobLogger context manager."""

    def test_writes_to_file(self, tmp_path):
        job_id = "test-job-123"
        with JobLogger(job_id, tmp_path) as logger:
            logger.info("test message")

        log_file = tmp_path / f"{job_id}.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test message" in content

    def test_returns_logger_in_context(self, tmp_path):
        with JobLogger("job-1", tmp_path) as logger:
            assert isinstance(logger, logging.Logger)
            assert "job-1" in logger.name

    def test_creates_logs_dir_if_missing(self, tmp_path):
        logs_dir = tmp_path / "nested" / "logs"
        with JobLogger("job-2", logs_dir) as logger:
            logger.info("hello")

        assert (logs_dir / "job-2.log").exists()
