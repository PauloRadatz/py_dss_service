"""
Unit tests for py_dss_service.common.time.
"""

from datetime import datetime

import pytest

from py_dss_service.common.time import utc_now, utc_now_iso


class TestUtcNow:
    """Tests for utc_now()."""

    def test_returns_datetime(self):
        result = utc_now()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self):
        result = utc_now()
        assert result.tzinfo is not None


class TestUtcNowIso:
    """Tests for utc_now_iso()."""

    def test_returns_string(self):
        result = utc_now_iso()
        assert isinstance(result, str)

    def test_iso_format(self):
        """Should contain ISO 8601 format (T separator, timezone)."""
        result = utc_now_iso()
        assert "T" in result
        assert "+" in result or result.endswith("Z")

    def test_parseable_as_datetime(self):
        result = utc_now_iso()
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None
