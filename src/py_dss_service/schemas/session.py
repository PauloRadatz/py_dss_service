"""
Session schemas.

Defines the structure of session requests and responses.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from py_dss_service.schemas.job_spec import Action


class SessionCreateResponse(BaseModel):
    """Response when creating a new session."""

    session_id: str = Field(..., description="Unique session identifier")
    status: Literal["created"] = Field(default="created", description="Session status")
    message: str = Field(default="Session created successfully")


class SessionInfo(BaseModel):
    """Information about a session."""

    session_id: str = Field(..., description="Unique session identifier")
    status: Literal["created", "loaded", "active", "closed"] = Field(
        ..., description="Current session status"
    )
    created_at: str = Field(..., description="ISO 8601 timestamp of creation")
    last_activity: str = Field(..., description="ISO 8601 timestamp of last activity")
    circuit_loaded: bool = Field(default=False, description="Whether a circuit is loaded")
    circuit_name: Optional[str] = Field(default=None, description="Name of loaded circuit")


class SessionListResponse(BaseModel):
    """Response listing all active sessions."""

    count: int = Field(..., description="Number of active sessions")
    sessions: list[SessionInfo] = Field(..., description="List of session info")


class LoadCircuitRequest(BaseModel):
    """Request to load a circuit into a session."""

    dss_script: str = Field(
        ...,
        description="DSS script to load (self-contained, no compile/redirect)",
        min_length=1,
    )


class LoadCircuitResponse(BaseModel):
    """Response after loading a circuit."""

    status: Literal["loaded"] = Field(default="loaded")
    circuit_name: str = Field(..., description="Name of the loaded circuit")
    message: str = Field(default="Circuit loaded successfully")


class SolveRequest(BaseModel):
    """Request to run a simulation on the loaded circuit."""

    simulation_type: Literal["snapshot", "qsts"] = Field(
        default="snapshot",
        description="Type of simulation to run",
    )


class SolveResponse(BaseModel):
    """Response after running a simulation."""

    status: Literal["solved"] = Field(default="solved")
    converged: bool = Field(..., description="Whether the simulation converged")
    simulation_type: str = Field(..., description="Type of simulation that was run")
    message: str = Field(default="Simulation completed")


class ApplyActionsRequest(BaseModel):
    """Request to apply actions to the circuit."""

    actions: list[Action] = Field(
        ...,
        description="List of actions to apply to the circuit",
        min_length=1,
    )


class ApplyActionsResponse(BaseModel):
    """Response after applying actions."""

    status: Literal["applied"] = Field(default="applied")
    actions_count: int = Field(..., description="Number of actions applied")
    message: str = Field(default="Actions applied successfully")


class SessionDeleteResponse(BaseModel):
    """Response when deleting a session."""

    session_id: str = Field(..., description="Session ID that was deleted")
    status: Literal["closed"] = Field(default="closed")
    message: str = Field(default="Session closed successfully")
