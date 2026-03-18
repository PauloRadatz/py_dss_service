"""
Unit tests for py_dss_service.common.ids.
"""

import re

import pytest

from py_dss_service.common.ids import generate_job_id


class TestGenerateJobId:
    """Tests for generate_job_id()."""

    def test_returns_string(self):
        result = generate_job_id()
        assert isinstance(result, str)

    def test_format_timestamp_uuid(self):
        """Format should be YYYYMMDD-HHMMSS-xxxxxxxx (8 hex chars)."""
        result = generate_job_id()
        assert re.match(r"^\d{8}-\d{6}-[a-f0-9]{8}$", result), result

    def test_unique_ids(self):
        """Multiple calls should produce different IDs."""
        ids = [generate_job_id() for _ in range(10)]
        assert len(ids) == len(set(ids))

    def test_length(self):
        """Expected length: 8+1+6+1+8 = 24 chars."""
        result = generate_job_id()
        assert len(result) == 24
