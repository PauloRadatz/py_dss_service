"""
Job management endpoints.

Stage 1: Uses filesystem-based job queue.
TODO: Stage 2+ - Replace with Redis queue + Postgres job tracking.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from py_dss_service.common.errors import ScriptValidationError
from py_dss_service.common.ids import generate_job_id
from py_dss_service.common.records import cols_to_named
from py_dss_service.common.time import utc_now_iso
from py_dss_service.engine.validation import validate_dss_script
from py_dss_service.schemas.job_spec import JobSpec, JobSubmitRequest, JobSubmitResponse
from py_dss_service.schemas.model import JobModelResponse, JobModelSnapshot, ModelElementResponse
from py_dss_service.schemas.results import JobResult
from py_dss_service.schemas.status import JobStatus, JobStatusResponse
from py_dss_service.settings import get_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _find_job_file(job_id: str) -> tuple[Optional[Path], JobStatus]:
    """
    Find a job spec file and determine its status based on location.

    Returns:
        Tuple of (file_path, status). file_path is None if not found.
    """
    settings = get_settings()

    # Check each status folder
    status_dirs = [
        (settings.jobs_pending_dir, JobStatus.QUEUED),
        (settings.jobs_running_dir, JobStatus.RUNNING),
        (settings.jobs_done_dir, JobStatus.DONE),
        (settings.jobs_failed_dir, JobStatus.FAILED),
    ]

    for dir_path, job_status in status_dirs:
        file_path = dir_path / f"{job_id}.json"
        if file_path.exists():
            return file_path, job_status

    return None, JobStatus.NOT_FOUND


@router.post("", response_model=JobSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_job(request: JobSubmitRequest) -> JobSubmitResponse:
    """
    Submit a new DSS simulation job.

    The job will be queued for processing by the worker.

    Args:
        request: Job submission request with dss_script

    Returns:
        Job ID and initial status

    Raises:
        HTTPException 400: If script validation fails
    """
    settings = get_settings()

    # Validate the script
    try:
        validate_dss_script(request.dss_script, max_length=settings.max_script_length)
    except ScriptValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Generate job ID and create spec
    job_id = generate_job_id()
    job_spec = JobSpec(
        job_id=job_id,
        dss_script=request.dss_script,
        created_at=utc_now_iso(),
        simulation_type=request.simulation_type,
        actions=request.actions,
    )

    # Write job spec to pending folder
    settings.ensure_directories()
    job_file = settings.jobs_pending_dir / f"{job_id}.json"
    job_file.write_text(job_spec.model_dump_json(indent=2), encoding="utf-8")

    return JobSubmitResponse(job_id=job_id, status="queued")


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Get the status of a job.

    Status is derived from which folder the job spec file is in:
    - jobs/pending/ -> queued
    - jobs/running/ -> running
    - jobs/done/ -> done
    - jobs/failed/ -> failed

    Args:
        job_id: The job ID to look up

    Returns:
        Job status information

    Raises:
        HTTPException 404: If job not found
    """
    file_path, job_status = _find_job_file(job_id)

    if job_status == JobStatus.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    # Read job spec for additional info
    response = JobStatusResponse(job_id=job_id, status=job_status)

    if file_path is not None:
        try:
            job_spec = JobSpec.model_validate_json(file_path.read_text(encoding="utf-8"))
            response.created_at = job_spec.created_at
        except Exception:
            pass  # Best effort

    # If failed, try to get error from result file
    if job_status == JobStatus.FAILED:
        settings = get_settings()
        result_file = settings.results_dir / f"{job_id}.json"
        if result_file.exists():
            try:
                result = JobResult.model_validate_json(result_file.read_text(encoding="utf-8"))
                response.error = result.error
            except Exception:
                pass

    return response


@router.get("/{job_id}/result")
async def get_job_result(
    job_id: str,
    fields: Optional[str] = None,
) -> dict:
    """
    Get the results of a completed job.

    Args:
        job_id: The job ID to look up
        fields: Optional comma-separated list of fields to return.
                If not specified, returns all fields.
                Available fields: circuit_summary, voltages_ln
                Example: ?fields=circuit_summary,voltages_ln

    Returns:
        Job results (filtered by fields if specified)

    Raises:
        HTTPException 404: If job not found or not yet complete
        HTTPException 400: If invalid field names are requested
    """
    settings = get_settings()
    _, job_status = _find_job_file(job_id)

    if job_status == JobStatus.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job_status == JobStatus.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job is still queued: {job_id}. Results not yet available.",
        )

    if job_status == JobStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job is still running: {job_id}. Results not yet available.",
        )

    # Job is done or failed - check for result file
    result_file = settings.results_dir / f"{job_id}.json"

    if not result_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result file not found for job: {job_id}",
        )

    try:
        result = JobResult.model_validate_json(result_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading result file: {e}",
        )

    # Filter results by requested fields
    result_dict = result.model_dump()
    
    if fields:
        # Parse requested fields
        requested_fields = [f.strip() for f in fields.split(",")]
        
        # Valid result fields (excluding metadata fields)
        valid_fields = {
            "circuit_summary",
            "voltages_ln",
        }
        
        # Check for invalid fields
        invalid_fields = [f for f in requested_fields if f not in valid_fields]
        if invalid_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid field(s): {', '.join(invalid_fields)}. "
                       f"Valid fields: {', '.join(sorted(valid_fields))}",
            )
        
        # Filter result_dict to only include requested fields + metadata
        filtered_result = {
            "job_id": result_dict["job_id"],
            "simulation_type": result_dict.get("simulation_type", "snapshot"),
            "converged": result_dict["converged"],
            "completed_at": result_dict["completed_at"],
            "execution_time_seconds": result_dict.get("execution_time_seconds"),
        }
        
        # Add requested fields
        for field in requested_fields:
            if field in result_dict:
                filtered_result[field] = result_dict[field]
        
        result_dict = filtered_result

    # For failed jobs, include a helpful message
    if job_status == JobStatus.FAILED:
        return {
            "job_id": job_id,
            "status": "failed",
            "error": result.error,
            "message": f"Job failed. See log file: {result.log_file}",
            "result": result_dict,
        }

    return {
        "job_id": job_id,
        "status": "done",
        "result": result_dict,
    }


# =============================================================================
# Result sub-endpoints - retrieve specific result fields
# =============================================================================

# Valid result field names for sub-endpoints
VALID_RESULT_FIELDS = {
    "circuit_summary",
    "voltages_ln",
}


def _get_result_file(job_id: str) -> Optional[Path]:
    """Get the result file for a job if it exists."""
    settings = get_settings()
    result_file = settings.results_dir / f"{job_id}.json"
    return result_file if result_file.exists() else None


def _load_job_result(job_id: str) -> JobResult:
    """Load and return job result, raising appropriate HTTP errors."""
    _require_job_complete(job_id)
    
    result_file = _get_result_file(job_id)
    if result_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Result file not found for job: {job_id}",
        )
    
    try:
        return JobResult.model_validate_json(result_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading result file: {e}",
        )


@router.get("/{job_id}/result/circuit_summary")
async def get_job_result_circuit_summary(job_id: str) -> dict:
    """
    Get circuit summary from job results.
    
    Returns the circuit summary containing power flow summary data.
    """
    result = _load_job_result(job_id)
    return {
        "job_id": job_id,
        "field": "circuit_summary",
        "data": result.circuit_summary,
    }


@router.get("/{job_id}/result/voltages_ln")
async def get_job_result_voltages_ln(job_id: str) -> dict:
    """
    Get line-neutral voltages from job results.
    
    Returns voltage magnitudes and angles for each bus (line-to-neutral).
    """
    result = _load_job_result(job_id)
    return {
        "job_id": job_id,
        "field": "voltages_ln",
        "data": result.voltages_ln,
    }

# =============================================================================
# Model endpoints - retrieve saved model data for completed jobs
# =============================================================================


def _get_model_file(job_id: str) -> Optional[Path]:
    """Get the model file for a job if it exists."""
    settings = get_settings()
    model_file = settings.models_dir / f"{job_id}.json"
    return model_file if model_file.exists() else None


def _require_job_complete(job_id: str) -> None:
    """Check that job is complete, raise 404 otherwise."""
    _, job_status = _find_job_file(job_id)
    
    if job_status == JobStatus.NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    
    if job_status == JobStatus.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job is still queued: {job_id}. Model not yet available.",
        )
    
    if job_status == JobStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job is still running: {job_id}. Model not yet available.",
        )


@router.get("/{job_id}/model", response_model=JobModelResponse)
async def get_job_model(job_id: str) -> JobModelResponse:
    """
    Get the complete model snapshot for a completed job.
    
    The model snapshot contains all circuit data captured after job execution:
    buses, lines, loads, transformers, capacitors, generators, PV systems, storage.
    
    Args:
        job_id: The job ID to look up
        
    Returns:
        Complete model snapshot
        
    Raises:
        HTTPException 404: If job not found, not complete, or no model data
    """
    _require_job_complete(job_id)
    
    model_file = _get_model_file(job_id)
    if model_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model data not found for job: {job_id}",
        )
    
    try:
        model = JobModelSnapshot.model_validate_json(model_file.read_text(encoding="utf-8"))
        model.buses = cols_to_named(model.buses)
        model.lines = cols_to_named(model.lines)
        model.loads = cols_to_named(model.loads)
        model.segments = cols_to_named(model.segments)
        return JobModelResponse(job_id=job_id, status="done", model=model)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading model file: {e}",
        )


@router.get("/{job_id}/model/summary")
async def get_job_model_summary(job_id: str) -> dict:
    """
    Get circuit summary from the job's model snapshot.
    
    Args:
        job_id: The job ID
        
    Returns:
        Circuit summary data
    """
    _require_job_complete(job_id)
    
    model_file = _get_model_file(job_id)
    if model_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model data not found for job: {job_id}",
        )
    
    try:
        model = JobModelSnapshot.model_validate_json(model_file.read_text(encoding="utf-8"))
        return {
            "job_id": job_id,
            "circuit_name": model.circuit_name,
            "num_buses": model.num_buses,
            "num_lines": model.num_lines,
            "num_loads": model.num_loads,
            "num_transformers": model.num_transformers,
            "summary": model.summary,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading model file: {e}",
        )


@router.get("/{job_id}/model/{element_type}", response_model=ModelElementResponse)
async def get_job_model_element(job_id: str, element_type: str) -> ModelElementResponse:
    """
    Get specific element data from the job's model snapshot.
    
    Args:
        job_id: The job ID
        element_type: Type of element: buses, lines, loads, transformers,
                      capacitors, generators, pvsystems, storage, segments
        
    Returns:
        Element data for the specified type
        
    Raises:
        HTTPException 400: If invalid element type
        HTTPException 404: If job/model not found
    """
    valid_types = {
        "buses", "lines", "loads", "segments"
    }
    
    if element_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid element type: {element_type}. Valid types: {', '.join(sorted(valid_types))}",
        )
    
    _require_job_complete(job_id)
    
    model_file = _get_model_file(job_id)
    if model_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model data not found for job: {job_id}",
        )
    
    try:
        model = JobModelSnapshot.model_validate_json(model_file.read_text(encoding="utf-8"))
        
        raw_data = getattr(model, element_type, None)
        named_data = cols_to_named(raw_data)
        count = len(named_data) if named_data else 0
        
        return ModelElementResponse(
            job_id=job_id,
            element_type=element_type,
            count=count,
            data=named_data,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading model file: {e}",
        )

