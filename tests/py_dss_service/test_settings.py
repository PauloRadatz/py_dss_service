"""
Unit tests for py_dss_service.settings.
"""

import pytest

from py_dss_service.settings import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_defaults(self):
        settings = get_settings()
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 8000
        assert settings.worker_poll_interval == 1.0
        assert settings.worker_job_timeout == 300
        assert settings.max_script_length == 200 * 1024
        assert settings.log_level == "INFO"

    def test_data_dir_is_absolute(self):
        settings = get_settings()
        assert settings.pydss_data_dir.is_absolute()

    def test_path_properties(self):
        settings = get_settings()
        base = settings.pydss_data_dir
        assert settings.jobs_pending_dir == base / "jobs" / "pending"
        assert settings.jobs_running_dir == base / "jobs" / "running"
        assert settings.jobs_done_dir == base / "jobs" / "done"
        assert settings.jobs_failed_dir == base / "jobs" / "failed"
        assert settings.results_dir == base / "results"
        assert settings.models_dir == base / "models"
        assert settings.logs_dir == base / "logs"


class TestEnsureDirectories:
    """Tests for ensure_directories()."""

    def test_creates_all_dirs(self, tmp_path):
        settings = Settings(pydss_data_dir=tmp_path)
        settings.ensure_directories()

        assert settings.jobs_pending_dir.exists()
        assert settings.jobs_running_dir.exists()
        assert settings.jobs_done_dir.exists()
        assert settings.jobs_failed_dir.exists()
        assert settings.results_dir.exists()
        assert settings.models_dir.exists()
        assert settings.logs_dir.exists()

    def test_idempotent(self, tmp_path):
        settings = Settings(pydss_data_dir=tmp_path)
        settings.ensure_directories()
        settings.ensure_directories()
        assert settings.jobs_pending_dir.exists()


class TestGetSettings:
    """Tests for get_settings() singleton."""

    def test_returns_same_instance(self):
        a = get_settings()
        b = get_settings()
        assert a is b
