"""
Job status schemas.

Stage 1: Status is derived from which folder the job spec file is in.
TODO: Stage 2+ - Status will be stored in Postgres jobs table.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Possible job states."""

    QUEUED = "queued"  # In jobs/pending/
    RUNNING = "running"  # In jobs/running/
    DONE = "done"  # In jobs/done/
    FAILED = "failed"  # In jobs/failed/
    NOT_FOUND = "not_found"  # Job doesn't exist


class JobStatusResponse(BaseModel):
    """Response for GET /jobs/{job_id} endpoint."""

    job_id: str = Field(..., description="The requested job ID")
    status: JobStatus = Field(..., description="Current job status")

    # Optional additional info
    created_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of job creation",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if status is failed",
    )
