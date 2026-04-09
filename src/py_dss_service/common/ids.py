"""
ID generation utilities.
"""

import uuid
from datetime import UTC, datetime


def generate_job_id() -> str:
    """
    Generate a unique job ID.

    Format: {timestamp}-{uuid4_short}
    Example: 20240115-143022-a1b2c3d4

    This format ensures:
    - Chronological sorting by default
    - Human-readable timestamps
    - Uniqueness via UUID component
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{timestamp}-{short_uuid}"
