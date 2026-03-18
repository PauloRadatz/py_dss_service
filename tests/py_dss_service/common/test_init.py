"""
Unit tests for py_dss_service.common package exports.
"""

import pytest


class TestCommonInit:
    """Tests for py_dss_service.common package __init__ exports."""

    def test_import_from_common(self):
        """Verify __all__ exports are importable from common."""
        from py_dss_service.common import (
            JobNotFoundError,
            PyDSSServiceError,
            ScriptValidationError,
            generate_job_id,
            utc_now,
            utc_now_iso,
        )

        assert generate_job_id() is not None
        assert utc_now() is not None
        assert utc_now_iso() != ""
