"""
Unit tests for py_dss_service.schemas.results.
"""

import pytest

from py_dss_service.common.time import utc_now_iso
from py_dss_service.schemas.results import JobResult, JobResultResponse


class TestJobResult:
    """Tests for JobResult."""

    def test_minimal_success(self):
        result = JobResult(
            job_id="test-1",
            converged=True,
            completed_at=utc_now_iso(),
        )
        assert result.job_id == "test-1"
        assert result.converged is True
        assert result.simulation_type == "snapshot"
        assert result.circuit_summary is None
        assert result.voltages_ln is None
        assert result.error is None

    def test_with_data(self):
        result = JobResult(
            job_id="test-2",
            converged=True,
            completed_at=utc_now_iso(),
            circuit_summary={"Total Power": {"Results": 100.0}},
            voltages_ln={"sourcebus": {"magnitude": {"1": 7200.0}, "angle": {"1": 0.0}}},
            execution_time_seconds=0.5,
        )
        assert result.circuit_summary["Total Power"]["Results"] == 100.0
        assert result.execution_time_seconds == 0.5

    def test_failure(self):
        result = JobResult(
            job_id="test-3",
            converged=False,
            completed_at=utc_now_iso(),
            error="DSS execution failed",
            log_file="logs/test-3.log",
        )
        assert result.error == "DSS execution failed"
        assert result.log_file == "logs/test-3.log"

    def test_round_trip(self):
        result = JobResult(
            job_id="test-4",
            converged=True,
            completed_at=utc_now_iso(),
            circuit_summary={"x": {"y": 1}},
        )
        json_str = result.model_dump_json()
        loaded = JobResult.model_validate_json(json_str)
        assert loaded.job_id == result.job_id
        assert loaded.circuit_summary == result.circuit_summary


class TestJobResultResponse:
    """Tests for JobResultResponse."""

    def test_create(self):
        resp = JobResultResponse(job_id="abc", status="done")
        assert resp.job_id == "abc"
        assert resp.status == "done"
        assert resp.result is None
