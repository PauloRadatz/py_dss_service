"""
Sessions API endpoints.

Provides stateful session management for interactive OpenDSS operations.
Each session maintains a DSS instance in memory, allowing users to:
- Load a circuit once
- Run multiple simulations
- Modify the circuit and re-solve
- Query model information
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from py_dss_service.common.errors import JobExecutionError, ScriptValidationError
from py_dss_service.common.records import cols_to_named
from py_dss_service.engine.validation import get_script_lines, validate_dss_script
from py_dss_service.schemas.session import (
    ApplyActionsRequest,
    ApplyActionsResponse,
    LoadCircuitRequest,
    LoadCircuitResponse,
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionInfo,
    SessionListResponse,
    SolveRequest,
    SolveResponse,
)
from py_dss_service.sessions.manager import Session, get_session_manager
from py_dss_service.settings import get_settings

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


def _get_session_or_404(session_id: str) -> Session:
    """Get session by ID or raise 404."""
    manager = get_session_manager()
    session = manager.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return session


def _require_circuit_loaded(session: Session) -> None:
    """Raise 400 if no circuit is loaded in the session."""
    if not session.circuit_loaded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No circuit loaded. Use POST /sessions/{id}/load first.",
        )


def _session_to_info(session: Session) -> SessionInfo:
    """Convert Session to SessionInfo response."""
    return SessionInfo(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
        last_activity=session.last_activity,
        circuit_loaded=session.circuit_loaded,
        circuit_name=session.circuit_name,
    )


# =============================================================================
# Session Management Endpoints
# =============================================================================


@router.post("", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_session() -> SessionCreateResponse:
    """
    Create a new session.

    Creates a new session with its own DSS instance. The session remains active
    until explicitly closed or it times out after inactivity.

    Returns:
        Session ID and status
    """
    manager = get_session_manager()

    try:
        session = manager.create_session()
        logger.info(f"Created session: {session.session_id}")

        return SessionCreateResponse(
            session_id=session.session_id,
            status="created",
            message="Session created successfully",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.get("", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """
    List all active sessions.

    Returns:
        List of all active sessions with their status
    """
    manager = get_session_manager()
    sessions = manager.list_sessions()

    return SessionListResponse(
        count=len(sessions),
        sessions=[_session_to_info(s) for s in sessions],
    )


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str) -> SessionInfo:
    """
    Get information about a specific session.

    Args:
        session_id: The session ID

    Returns:
        Session information
    """
    session = _get_session_or_404(session_id)
    session.touch()  # Update last activity
    return _session_to_info(session)


@router.delete("/{session_id}", response_model=SessionDeleteResponse)
async def close_session(session_id: str) -> SessionDeleteResponse:
    """
    Close a session and release its resources.

    Args:
        session_id: The session ID to close

    Returns:
        Confirmation of session closure
    """
    manager = get_session_manager()

    if not manager.close_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    logger.info(f"Closed session: {session_id}")

    return SessionDeleteResponse(
        session_id=session_id,
        status="closed",
        message="Session closed successfully",
    )


# =============================================================================
# Circuit Operations
# =============================================================================


@router.post("/{session_id}/load", response_model=LoadCircuitResponse)
async def load_circuit(session_id: str, request: LoadCircuitRequest) -> LoadCircuitResponse:
    """
    Load a DSS circuit into the session.

    The circuit will remain in memory for subsequent operations.
    Loading a new circuit replaces any previously loaded circuit.

    Args:
        session_id: The session ID
        request: The DSS script to load

    Returns:
        Confirmation with circuit name
    """
    session = _get_session_or_404(session_id)
    settings = get_settings()

    # Validate script
    try:
        validate_dss_script(request.dss_script, max_length=settings.max_script_length)
    except ScriptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Load circuit with lock to ensure thread safety
    with session.lock:
        try:
            runner = session.runner
            dss = runner._get_dss()
            runner._connect_dss_tools(dss)

            # Clear any previous circuit
            dss.text("clear")

            # Execute script lines
            lines = get_script_lines(request.dss_script)
            for line in lines:
                dss.text(line)

            # Solve to initialize
            dss.text("solve")

            # Update session state
            circuit_name = dss.circuit.name or "unknown"
            session.circuit_loaded = True
            session.circuit_name = circuit_name
            session.last_results = None
            session.touch()

            logger.info(f"Session {session_id}: Loaded circuit '{circuit_name}'")

            return LoadCircuitResponse(
                status="loaded",
                circuit_name=circuit_name,
                message=f"Circuit '{circuit_name}' loaded successfully",
            )

        except Exception as e:
            logger.error(f"Session {session_id}: Failed to load circuit: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load circuit: {e}",
            )


@router.post("/{session_id}/solve", response_model=SolveResponse)
async def solve(session_id: str, request: SolveRequest = None) -> SolveResponse:
    """
    Run a simulation on the loaded circuit.

    Supports both snapshot (power flow) and QSTS (time series) simulations.
    Results are cached in the session and can be retrieved via GET /sessions/{id}/results.

    Args:
        session_id: The session ID
        request: Simulation options (defaults to snapshot)

    Returns:
        Simulation status and convergence
    """
    session = _get_session_or_404(session_id)
    _require_circuit_loaded(session)

    if request is None:
        request = SolveRequest()

    with session.lock:
        try:
            runner = session.runner

            result = runner.solve_snapshot(
                job_id=f"session-{session_id}",
            )

            # Cache results
            session.last_results = result
            session.touch()

            logger.info(
                f"Session {session_id}: Solved ({request.simulation_type}), "
                f"converged={result.converged}"
            )

            return SolveResponse(
                status="solved",
                converged=result.converged,
                simulation_type=request.simulation_type,
                message=f"Simulation completed. Converged: {result.converged}",
            )

        except JobExecutionError as e:
            logger.error(f"Session {session_id}: Solve failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )


@router.post("/{session_id}/actions", response_model=ApplyActionsResponse)
async def apply_actions(session_id: str, request: ApplyActionsRequest) -> ApplyActionsResponse:
    """
    Apply actions to modify the circuit.

    Actions are applied in order. After applying actions, you typically want
    to call POST /sessions/{id}/solve to see the effects.

    Args:
        session_id: The session ID
        request: Actions to apply

    Returns:
        Confirmation with action count
    """
    session = _get_session_or_404(session_id)
    _require_circuit_loaded(session)

    with session.lock:
        try:
            runner = session.runner
            dss = runner._get_dss()

            # Apply each action
            for i, action in enumerate(request.actions):
                runner._apply_action(dss, action, f"session-{session_id}", i + 1)

            session.touch()

            logger.info(f"Session {session_id}: Applied {len(request.actions)} actions")

            return ApplyActionsResponse(
                status="applied",
                actions_count=len(request.actions),
                message=f"Applied {len(request.actions)} actions successfully",
            )

        except JobExecutionError as e:
            logger.error(f"Session {session_id}: Actions failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )


@router.get("/{session_id}/results")
async def get_results(session_id: str) -> dict[str, Any]:
    """
    Get the latest simulation results.

    Returns the results from the most recent solve operation.

    Args:
        session_id: The session ID

    Returns:
        Simulation results
    """
    session = _get_session_or_404(session_id)
    session.touch()

    if session.last_results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No results available. Run POST /sessions/{id}/solve first.",
        )

    return {
        "session_id": session_id,
        "status": "success",
        "result": session.last_results.model_dump(),
    }


# =============================================================================
# Result Sub-Endpoints - retrieve specific result fields
# =============================================================================


def _require_results(session: "Session") -> None:
    """Check that results exist, raise 404 otherwise."""
    if session.last_results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No results available. Run POST /sessions/{id}/solve first.",
        )


@router.get("/{session_id}/results/circuit_summary")
async def get_results_circuit_summary(session_id: str) -> dict[str, Any]:
    """Get circuit summary from session results."""
    session = _get_session_or_404(session_id)
    _require_results(session)
    session.touch()

    return {
        "session_id": session_id,
        "field": "circuit_summary",
        "data": session.last_results.circuit_summary,
    }


@router.get("/{session_id}/results/voltages_ln")
async def get_results_voltages_ln(session_id: str) -> dict[str, Any]:
    """Get line-neutral voltages from session results."""
    session = _get_session_or_404(session_id)
    _require_results(session)
    session.touch()

    return {
        "session_id": session_id,
        "field": "voltages_ln",
        "data": session.last_results.voltages_ln,
    }


# =============================================================================
# Model Query Endpoints
# =============================================================================


@router.get("/{session_id}/model/summary")
async def get_model_summary(session_id: str) -> dict[str, Any]:
    """Get circuit model summary."""
    session = _get_session_or_404(session_id)
    _require_circuit_loaded(session)
    session.touch()

    with session.lock:
        runner = session.runner
        dss = runner._get_dss()

        summary_data = runner.get_model_summary()

        return {
            "name": dss.circuit.name,
            "num_buses": dss.circuit.num_buses,
            "num_lines": len(dss.lines.names) if dss.lines.names != [""] else 0,
            "num_loads": len(dss.loads.names) if dss.loads.names != [""] else 0,
            "num_transformers": len(dss.transformers.names)
            if dss.transformers.names != [""]
            else 0,
            "data": summary_data,
        }


@router.get("/{session_id}/model/buses")
async def get_model_buses(session_id: str) -> dict[str, Any]:
    """Get all bus data."""
    session = _get_session_or_404(session_id)
    _require_circuit_loaded(session)
    session.touch()

    with session.lock:
        buses = cols_to_named(session.runner.get_buses())
        return {"count": len(buses) if buses else 0, "buses": buses or {}}


@router.get("/{session_id}/model/lines")
async def get_model_lines(session_id: str) -> dict[str, Any]:
    """Get all line data."""
    session = _get_session_or_404(session_id)
    _require_circuit_loaded(session)
    session.touch()

    with session.lock:
        lines = cols_to_named(session.runner.get_lines())
        return {"count": len(lines) if lines else 0, "lines": lines or {}}


@router.get("/{session_id}/model/loads")
async def get_model_loads(session_id: str) -> dict[str, Any]:
    """Get all load data."""
    session = _get_session_or_404(session_id)
    _require_circuit_loaded(session)
    session.touch()

    with session.lock:
        loads = cols_to_named(session.runner.get_loads())
        return {"count": len(loads) if loads else 0, "loads": loads or {}}
