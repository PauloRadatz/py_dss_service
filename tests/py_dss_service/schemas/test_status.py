"""
Unit tests for py_dss_service.schemas.status.
"""

import pytest

from py_dss_service.schemas.status import JobStatus, JobStatusResponse


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_values(self):
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.DONE.value == "done"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.NOT_FOUND.value == "not_found"

    def test_is_str_enum(self):
        assert isinstance(JobStatus.DONE, str)


class TestJobStatusResponse:
    """Tests for JobStatusResponse."""

    def test_minimal(self):
        resp = JobStatusResponse(job_id="abc", status=JobStatus.QUEUED)
        assert resp.job_id == "abc"
        assert resp.status == JobStatus.QUEUED
        assert resp.created_at is None
        assert resp.error is None

    def test_with_optional_fields(self):
        resp = JobStatusResponse(
            job_id="xyz",
            status=JobStatus.FAILED,
            created_at="2024-01-15T12:00:00Z",
            error="Execution failed",
        )
        assert resp.created_at == "2024-01-15T12:00:00Z"
        assert resp.error == "Execution failed"
