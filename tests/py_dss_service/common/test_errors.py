"""
Unit tests for py_dss_service.common.errors.
"""

import pytest

from py_dss_service.common.errors import (
    JobExecutionError,
    JobNotFoundError,
    JobTimeoutError,
    PyDSSServiceError,
    ScriptValidationError,
)


class TestPyDSSServiceError:
    """Tests for PyDSSServiceError base exception."""

    def test_is_exception_subclass(self):
        assert issubclass(PyDSSServiceError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(PyDSSServiceError) as exc_info:
            raise PyDSSServiceError("test message")
        assert str(exc_info.value) == "test message"


class TestScriptValidationError:
    """Tests for ScriptValidationError."""

    def test_inherits_from_pydss_service_error(self):
        assert issubclass(ScriptValidationError, PyDSSServiceError)

    def test_message_preserved(self):
        with pytest.raises(ScriptValidationError) as exc_info:
            raise ScriptValidationError("Invalid script")
        assert exc_info.value.args[0] == "Invalid script"


class TestJobNotFoundError:
    """Tests for JobNotFoundError."""

    def test_inherits_from_pydss_service_error(self):
        assert issubclass(JobNotFoundError, PyDSSServiceError)


class TestJobExecutionError:
    """Tests for JobExecutionError."""

    def test_inherits_from_pydss_service_error(self):
        assert issubclass(JobExecutionError, PyDSSServiceError)


class TestJobTimeoutError:
    """Tests for JobTimeoutError."""

    def test_inherits_from_pydss_service_error(self):
        assert issubclass(JobTimeoutError, PyDSSServiceError)
