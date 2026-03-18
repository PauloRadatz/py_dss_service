"""Tests for py_dss_service.worker.main."""

import signal
from unittest.mock import MagicMock, patch

import pytest

from py_dss_service.worker import main as worker_main


class TestWorkerMain:
    @patch("py_dss_service.worker.main.process_job")
    @patch("py_dss_service.worker.main.claim_job")
    @patch("py_dss_service.worker.main.get_settings")
    @patch("py_dss_service.worker.main.setup_logging")
    @patch("py_dss_service.worker.main.get_logger")
    def test_loop_exits_when_no_jobs_and_shutdown_requested(
        self, mock_get_logger, mock_setup_logging, mock_get_settings,
        mock_claim_job, mock_process_job,
    ):
        """Worker loop exits when _shutdown_requested is set."""
        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.worker_poll_interval = 0.01
        mock_settings.worker_job_timeout = 10
        mock_settings.pydss_data_dir = MagicMock()
        mock_settings.pydss_data_dir.absolute.return_value = "/tmp/data"
        mock_get_settings.return_value = mock_settings
        mock_get_logger.return_value = MagicMock()
        mock_claim_job.return_value = None

        # Set shutdown flag after first poll
        call_count = 0
        original_claim = mock_claim_job.side_effect

        def claim_then_shutdown(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                worker_main._shutdown_requested = True
            return None

        mock_claim_job.side_effect = claim_then_shutdown

        try:
            worker_main.main()
        finally:
            worker_main._shutdown_requested = False

        mock_settings.ensure_directories.assert_called_once()
        mock_claim_job.assert_called()
        mock_process_job.assert_not_called()

    @patch("py_dss_service.worker.main.process_job")
    @patch("py_dss_service.worker.main.claim_job")
    @patch("py_dss_service.worker.main.get_settings")
    @patch("py_dss_service.worker.main.setup_logging")
    @patch("py_dss_service.worker.main.get_logger")
    def test_processes_claimed_job(
        self, mock_get_logger, mock_setup_logging, mock_get_settings,
        mock_claim_job, mock_process_job,
    ):
        """Worker calls process_job when a job is claimed."""
        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.worker_poll_interval = 0.01
        mock_settings.worker_job_timeout = 10
        mock_settings.pydss_data_dir = MagicMock()
        mock_settings.pydss_data_dir.absolute.return_value = "/tmp/data"
        mock_get_settings.return_value = mock_settings
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_job_file = MagicMock()
        mock_job_spec = MagicMock()
        mock_job_spec.job_id = "test-123"

        call_count = 0

        def claim_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (mock_job_file, mock_job_spec)
            worker_main._shutdown_requested = True
            return None

        mock_claim_job.side_effect = claim_once

        try:
            worker_main.main()
        finally:
            worker_main._shutdown_requested = False

        mock_process_job.assert_called_once_with(
            mock_settings, mock_job_file, mock_job_spec, mock_logger
        )

    def test_signal_handler_sets_shutdown_flag(self):
        """_signal_handler sets the global _shutdown_requested flag."""
        worker_main._shutdown_requested = False
        try:
            worker_main._signal_handler(signal.SIGINT, None)
            assert worker_main._shutdown_requested is True
        finally:
            worker_main._shutdown_requested = False
