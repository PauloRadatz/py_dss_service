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
    
    # Detailed model data
    summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Circuit summary from dss_tools.model.summary_df",
    )
    buses: Optional[dict[str, Any]] = Field(
        default=None,
        description="Bus data - keys are bus names",
    )
    lines: Optional[dict[str, Any]] = Field(
        default=None,
        description="Line data - keys are line names",
    )
    loads: Optional[dict[str, Any]] = Field(
        default=None,
        description="Load data - keys are load names",
    )
    segments: Optional[dict[str, Any]] = Field(
        default=None,
        description="Segment data - keys are segment identifiers",
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
    data: Optional[dict[str, Any]] = None
    message: Optional[str] = None

