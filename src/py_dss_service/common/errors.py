"""
Custom exceptions for py-dss-service.
"""


class PyDSSServiceError(Exception):
    """Base exception for all py-dss-service errors."""

    pass


class ScriptValidationError(PyDSSServiceError):
    """Raised when a DSS script fails validation (security or size checks)."""

    pass


class JobNotFoundError(PyDSSServiceError):
    """Raised when a requested job does not exist."""

    pass


class JobExecutionError(PyDSSServiceError):
    """Raised when a job fails during execution."""

    pass


class JobTimeoutError(PyDSSServiceError):
    """Raised when a job exceeds its timeout."""

    pass
