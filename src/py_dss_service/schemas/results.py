"""
Job result schemas.

Defines the structure of simulation results stored in results/{job_id}.json.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class JobResult(BaseModel):
    """
    Result of a completed DSS simulation job.

    Stored in PYDSS_DATA_DIR/results/{job_id}.json
    """

    job_id: str = Field(..., description="The job ID this result belongs to")
    
    simulation_type: Literal["snapshot", "qsts"] = Field(
        default="snapshot",
        description="Type of simulation that was run",
    )
    
    converged: bool = Field(..., description="Whether the power flow solution converged")
    
    # Circuit summary from py-dss-toolkit (index preserved as keys)
    circuit_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Circuit summary: keys are quantity names, values are column data. "
                    "Example: {'Total Power': {'Results': 100.0}, ...}",
    )

    # Voltage results (line-neutral) - keys are bus names
    voltages_ln: Optional[dict[str, dict[str, Any]]] = Field(
        default=None,
        description="Line-neutral voltages: keys are bus names, values contain magnitude and angle. "
                    "Example: {'sourcebus': {'magnitude': {...}, 'angle': {...}}, ...}",
    )

    # Execution metadata
    completed_at: str = Field(..., description="ISO 8601 timestamp of completion")
    execution_time_seconds: Optional[float] = Field(
        default=None,
        description="Wall-clock time for job execution",
    )

    # Error information (populated if job failed)
    error: Optional[str] = Field(
        default=None,
        description="Error message if job failed",
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Relative path to job log file",
    )


class JobResultResponse(BaseModel):
    """API response wrapper for job results."""

    job_id: str
    status: str
    result: Optional[JobResult] = None
    message: Optional[str] = None

