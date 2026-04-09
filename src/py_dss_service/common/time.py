"""
Time utilities for consistent timestamp handling.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Get the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Get the current UTC time as an ISO 8601 string."""
    return utc_now().isoformat()
