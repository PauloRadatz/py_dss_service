"""
Model data schemas for job model snapshots.

These schemas define the structure for circuit model data
that is saved alongside job results.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class JobModelSnapshot(BaseModel):
    """
    Complete model snapshot saved for a job.

    Contains all circuit model data captured after job execution.
    Saved to data/models/{job_id}.json
    """

    job_id: str = Field(..., description="Job ID this model belongs to")
    circuit_name: str = Field(..., description="Name of the circuit")

    # Model counts for quick summary
    num_buses: int = Field(default=0, description="Number of buses")
    num_lines: int = Field(default=0, description="Number of lines")
    num_loads: int = Field(default=0, description="Number of loads")
    num_transformers: int = Field(default=0, description="Number of transformers")

    summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Model summary as key-value pairs (e.g. {'buses': 10, 'line': 5, ...})",
    )
    buses: Optional[dict[str, Any]] = Field(
        default=None,
        description="Bus data keyed by name: {'bus1': {'kv_base': 12.47, ...}, ...}. "
        "Stored on disk as column-oriented records.",
    )
    lines: Optional[dict[str, Any]] = Field(
        default=None,
        description="Line data keyed by name: {'line1': {'bus1': 'a', ...}, ...}. "
        "Stored on disk as column-oriented records.",
    )
    loads: Optional[dict[str, Any]] = Field(
        default=None,
        description="Load data keyed by name: {'load1': {'bus1': 'a', ...}, ...}. "
        "Stored on disk as column-oriented records.",
    )
    segments: Optional[dict[str, Any]] = Field(
        default=None,
        description="Segment data keyed by name: {'seg1': {'bus1': 'a', ...}, ...}. "
        "Stored on disk as column-oriented records.",
    )


class JobModelResponse(BaseModel):
    """Response for GET /jobs/{job_id}/model endpoint."""

    job_id: str
    status: str = Field(default="done", description="Job status")
    model: Optional[JobModelSnapshot] = None
    message: Optional[str] = None


class ModelElementResponse(BaseModel):
    """Response for GET /jobs/{job_id}/model/{element_type} endpoint."""

    job_id: str
    element_type: str
    count: int
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Element data keyed by name: {'elem1': {prop: val, ...}, ...}",
    )
    message: Optional[str] = None
