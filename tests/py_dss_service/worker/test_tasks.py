"""Tests for py_dss_service.worker.tasks."""

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from py_dss_service.common.errors import JobExecutionError, JobTimeoutError
from py_dss_service.schemas.job_spec import JobSpec
from py_dss_service.schemas.results import JobResult
from py_dss_service.settings import Settings
from py_dss_service.worker.tasks import (
    _handle_failure_abs,
    _move_job_abs,
    _write_result_abs,
    claim_job,
    process_job,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(tmp_path: Path) -> Settings:
    """Create a Settings instance pointing at tmp_path."""
    return Settings(pydss_data_dir=tmp_path / "data")


def _make_job_spec(job_id: str = "test-job-001") -> JobSpec:
    return JobSpec(
        job_id=job_id,
        dss_script="New Circuit.T basekv=12.47\nSolve",
        created_at="2026-01-01T00:00:00+00:00",
    )


def _write_pending_job(settings: Settings, job_spec: JobSpec) -> Path:
    """Write a job spec JSON into pending dir and return the file path."""
    settings.ensure_directories()
    job_file = settings.jobs_pending_dir / f"{job_spec.job_id}.json"
    job_file.write_text(job_spec.model_dump_json(indent=2), encoding="utf-8")
    return job_file


# ---------------------------------------------------------------------------
# claim_job
# ---------------------------------------------------------------------------

class TestClaimJob:
    def test_claims_pending_job(self, tmp_path):
        settings = _make_settings(tmp_path)
        spec = _make_job_spec()
        _write_pending_job(settings, spec)
        logger = logging.getLogger("test")

        result = claim_job(settings, logger)

        assert result is not None
        running_file, claimed_spec = result
        assert claimed_spec.job_id == spec.job_id
        assert running_file.parent == settings.jobs_running_dir
        assert running_file.exists()
        assert not (settings.jobs_pending_dir / f"{spec.job_id}.json").exists()

    def test_returns_none_when_no_pending_jobs(self, tmp_path):
        settings = _make_settings(tmp_path)
        settings.ensure_directories()
        logger = logging.getLogger("test")

        assert claim_job(settings, logger) is None

    def test_claims_oldest_job_first(self, tmp_path):
        """Jobs are sorted; the alphabetically first file is claimed."""
        settings = _make_settings(tmp_path)
        spec_a = _make_job_spec("aaa-job")
        spec_b = _make_job_spec("zzz-job")
        _write_pending_job(settings, spec_a)
        _write_pending_job(settings, spec_b)
        logger = logging.getLogger("test")

        _, claimed_spec = claim_job(settings, logger)
        assert claimed_spec.job_id == "aaa-job"

    def test_skips_already_claimed_file(self, tmp_path):
        """If the pending file disappears before rename, skip to next."""
        settings = _make_settings(tmp_path)
        spec_a = _make_job_spec("first")
        spec_b = _make_job_spec("second")
        _write_pending_job(settings, spec_a)
        _write_pending_job(settings, spec_b)
        logger = logging.getLogger("test")

        # Remove the first file to simulate another worker claiming it
        (settings.jobs_pending_dir / "first.json").unlink()

        _, claimed_spec = claim_job(settings, logger)
        assert claimed_spec.job_id == "second"


# ---------------------------------------------------------------------------
# _write_result_abs / _move_job_abs / _handle_failure_abs
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_write_result_abs(self, tmp_path):
        result = JobResult(
            job_id="j1",
            converged=True,
            completed_at="2026-01-01T00:00:00+00:00",
        )
        _write_result_abs(tmp_path, result)
        written = json.loads((tmp_path / "j1.json").read_text(encoding="utf-8"))
        assert written["job_id"] == "j1"
        assert written["converged"] is True

    def test_move_job_abs(self, tmp_path):
        src_dir = tmp_path / "running"
        dst_dir = tmp_path / "done"
        src_dir.mkdir()
        dst_dir.mkdir()
        job_file = src_dir / "j1.json"
        job_file.write_text("{}", encoding="utf-8")
        logger = logging.getLogger("test")

        _move_job_abs(job_file, dst_dir, logger)

        assert not job_file.exists()
        assert (dst_dir / "j1.json").exists()

    def test_handle_failure_abs_writes_error_result_and_moves(self, tmp_path):
        results_dir = tmp_path / "results"
        failed_dir = tmp_path / "failed"
        running_dir = tmp_path / "running"
        results_dir.mkdir()
        failed_dir.mkdir()
        running_dir.mkdir()

        job_file = running_dir / "j1.json"
        job_file.write_text("{}", encoding="utf-8")
        logger = logging.getLogger("test")

        _handle_failure_abs(results_dir, failed_dir, job_file, "j1", "boom", time.time(), logger)

        result_data = json.loads((results_dir / "j1.json").read_text(encoding="utf-8"))
        assert result_data["converged"] is False
        assert result_data["error"] == "boom"
        assert (failed_dir / "j1.json").exists()
        assert not job_file.exists()


# ---------------------------------------------------------------------------
# process_job (mocked DSSRunner)
# ---------------------------------------------------------------------------

class TestProcessJob:
    @patch("py_dss_service.worker.tasks.DSSRunner")
    def test_success_writes_result_and_moves_to_done(self, MockRunner, tmp_path):
        settings = _make_settings(tmp_path)
        spec = _make_job_spec()
        _write_pending_job(settings, spec)
        logger = logging.getLogger("test")

        # Claim the job first
        running_file, claimed_spec = claim_job(settings, logger)

        mock_result = JobResult(
            job_id=spec.job_id,
            converged=True,
            completed_at="2026-01-01T00:00:00+00:00",
            execution_time_seconds=0.5,
        )
        mock_runner_instance = MockRunner.return_value
        mock_runner_instance.execute.return_value = mock_result
        mock_runner_instance.extract_model_snapshot.return_value = None

        process_job(settings, running_file, claimed_spec, logger)

        # Result written
        result_file = settings.results_dir.resolve() / f"{spec.job_id}.json"
        assert result_file.exists()
        result_data = json.loads(result_file.read_text(encoding="utf-8"))
        assert result_data["converged"] is True

        # Job moved to done
        assert (settings.jobs_done_dir.resolve() / f"{spec.job_id}.json").exists()
        assert not running_file.resolve().exists()

    @patch("py_dss_service.worker.tasks.DSSRunner")
    def test_execution_error_moves_to_failed(self, MockRunner, tmp_path):
        settings = _make_settings(tmp_path)
        spec = _make_job_spec()
        _write_pending_job(settings, spec)
        logger = logging.getLogger("test")

        running_file, claimed_spec = claim_job(settings, logger)

        mock_runner_instance = MockRunner.return_value
        mock_runner_instance.execute.side_effect = JobExecutionError("DSS crashed")

        process_job(settings, running_file, claimed_spec, logger)

        # Error result written
        result_file = settings.results_dir.resolve() / f"{spec.job_id}.json"
        assert result_file.exists()
        result_data = json.loads(result_file.read_text(encoding="utf-8"))
        assert result_data["converged"] is False
        assert "DSS crashed" in result_data["error"]

        # Job moved to failed
        assert (settings.jobs_failed_dir.resolve() / f"{spec.job_id}.json").exists()

    @patch("py_dss_service.worker.tasks.DSSRunner")
    def test_model_snapshot_written_when_available(self, MockRunner, tmp_path):
        settings = _make_settings(tmp_path)
        spec = _make_job_spec()
        _write_pending_job(settings, spec)
        logger = logging.getLogger("test")

        running_file, claimed_spec = claim_job(settings, logger)

        mock_result = JobResult(
            job_id=spec.job_id,
            converged=True,
            completed_at="2026-01-01T00:00:00+00:00",
        )
        model_snapshot = {
            "job_id": spec.job_id,
            "circuit_name": "TestCkt",
            "num_buses": 2,
            "num_lines": 1,
            "num_loads": 1,
        }
        mock_runner_instance = MockRunner.return_value
        mock_runner_instance.execute.return_value = mock_result
        mock_runner_instance.extract_model_snapshot.return_value = model_snapshot

        process_job(settings, running_file, claimed_spec, logger)

        model_file = settings.models_dir.resolve() / f"{spec.job_id}.json"
        assert model_file.exists()
        model_data = json.loads(model_file.read_text(encoding="utf-8"))
        assert model_data["circuit_name"] == "TestCkt"
        assert model_data["num_buses"] == 2
