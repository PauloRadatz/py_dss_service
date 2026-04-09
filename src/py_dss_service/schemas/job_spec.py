"""
Job specification schemas.

Defines the structure of job requests and the internal job spec file format.
"""

from typing import Literal, Union

from pydantic import BaseModel, Field


class DSSCommandAction(BaseModel):
    """Action to execute a raw DSS command."""

    type: Literal["dss_command"] = Field(..., description="Action type")
    command: str = Field(..., description="DSS command to execute", min_length=1)


class AddLineInVsourceAction(BaseModel):
    """
    Action to add a line in series with the Vsource using dss_tools.model.add_line_in_vsource().

    This is useful for adding a meter at the source bus or for creating a reference line
    for monitoring purposes.
    """

    type: Literal["add_line_in_vsource"] = Field(..., description="Action type")
    add_meter: bool = Field(
        default=False,
        description="Whether to add an energy meter at the source",
    )
    add_monitors: bool = Field(
        default=False,
        description="Whether to add monitors to the new line",
    )


# Union type for all actions
# Note: Order matters for Pydantic discriminator matching
Action = Union[
    DSSCommandAction,
    AddLineInVsourceAction,
]


class JobSubmitRequest(BaseModel):
    """Request body for submitting a new job via POST /jobs."""

    dss_script: str = Field(
        ...,
        description="Self-contained OpenDSS commands (no file redirects/compile allowed)",
        min_length=1,
    )

    simulation_type: Literal["snapshot", "qsts"] = Field(
        default="snapshot",
        description="Type of simulation: 'snapshot' for single power flow, 'qsts' for time series",
    )

    actions: list[Action] = Field(
        default_factory=list,
        description="List of actions to apply after dss_script but before solving. "
        "Supported actions: dss_command, add_line_in_vsource. "
        "Actions are processed in order.",
    )


class JobSpec(BaseModel):
    """
    Internal job specification stored as JSON file.

    This is what gets written to jobs/pending/{job_id}.json
    """

    job_id: str = Field(..., description="Unique job identifier")
    dss_script: str = Field(..., description="The OpenDSS script to execute")
    created_at: str = Field(..., description="ISO 8601 timestamp of job creation")

    simulation_type: Literal["snapshot", "qsts"] = Field(
        default="snapshot",
        description="Type of simulation: 'snapshot' for single power flow, 'qsts' for time series",
    )

    actions: list[Action] = Field(
        default_factory=list,
        description="List of actions to apply after dss_script but before solving",
    )

    # TODO: Stage 2+ - additional metadata fields
    # priority: int = 0
    # tags: list[str] = []
    # user_id: Optional[str] = None


class JobSubmitResponse(BaseModel):
    """Response returned after successfully submitting a job."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(default="queued", description="Initial job status")
