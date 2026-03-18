"""
Worker task implementations.

Stage 1: Filesystem-based job processing with py-dss-interface.
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional

from py_dss_service.common.errors import JobExecutionError, JobTimeoutError
from py_dss_service.common.time import utc_now_iso
from py_dss_service.engine.runner import DSSRunner
from py_dss_service.logging import JobLogger
from py_dss_service.schemas.job_spec import JobSpec
from py_dss_service.schemas.model import JobModelSnapshot
from py_dss_service.schemas.results import JobResult
from py_dss_service.settings import Settings


def claim_job(settings: Settings, logger: logging.Logger) -> Optional[tuple[Path, JobSpec]]:
    """
    Atomically claim a pending job by moving it to running/.

    Uses os.rename() for atomic move on the same filesystem.

    Returns:
        Tuple of (running_file_path, job_spec) if a job was claimed, None otherwise.
    """
    pending_dir = settings.jobs_pending_dir
    running_dir = settings.jobs_running_dir

    # List pending jobs (sorted for consistent ordering)
    try:
        pending_files = sorted(pending_dir.glob("*.json"))
    except Exception as e:
        logger.error(f"Error listing pending jobs: {e}")
        return None

    for pending_file in pending_files:
        job_id = pending_file.stem
        running_file = running_dir / pending_file.name

        try:
            # Atomic move (rename) - will fail if another worker claimed it
            os.rename(str(pending_file), str(running_file))
            logger.info(f"Claimed job: {job_id}")

            # Read job spec
            job_spec = JobSpec.model_validate_json(running_file.read_text(encoding="utf-8"))
            return running_file, job_spec

        except FileNotFoundError:
            # Another worker claimed it, try next
            continue
        except Exception as e:
            logger.error(f"Error claiming job {job_id}: {e}")
            continue

    return None


def process_job(
    settings: Settings,
    job_file: Path,
    job_spec: JobSpec,
    parent_logger: logging.Logger,
) -> None:
    """
    Process a claimed job: execute DSS script and store results.

    Args:
        settings: Application settings
        job_file: Path to the job file in running/
        job_spec: The job specification
        parent_logger: Parent logger for status messages
    """
    job_id = job_spec.job_id
    start_time = time.time()

    # IMPORTANT: Resolve ALL paths to absolute BEFORE DSS execution
    # because py-dss-interface/OpenDSS changes the current working directory
    job_file_abs = job_file.resolve()
    results_dir_abs = settings.results_dir.resolve()
    models_dir_abs = settings.models_dir.resolve()
    logs_dir_abs = settings.logs_dir.resolve()
    done_dir_abs = settings.jobs_done_dir.resolve()
    failed_dir_abs = settings.jobs_failed_dir.resolve()

    # Ensure directories exist
    results_dir_abs.mkdir(parents=True, exist_ok=True)
    models_dir_abs.mkdir(parents=True, exist_ok=True)
    logs_dir_abs.mkdir(parents=True, exist_ok=True)
    done_dir_abs.mkdir(parents=True, exist_ok=True)
    failed_dir_abs.mkdir(parents=True, exist_ok=True)

    # Set up per-job logging
    with JobLogger(job_id, logs_dir_abs) as job_logger:
        job_logger.info(f"Starting job: {job_id}")
        job_logger.info(f"Script length: {len(job_spec.dss_script)} characters")

        try:
            # Execute with timeout (best-effort via signal/thread)
            result, model_snapshot = _execute_with_timeout(
                job_id=job_id,
                dss_script=job_spec.dss_script,
                actions=job_spec.actions,
                timeout=settings.worker_job_timeout,
                start_time=start_time,
                logger=job_logger,
            )

            job_logger.info(f"Job completed successfully. Converged: {result.converged}")

            # Write result (using absolute path)
            _write_result_abs(results_dir_abs, result)
            
            # Write model snapshot (using absolute path)
            if model_snapshot:
                _write_model_abs(models_dir_abs, model_snapshot)
                job_logger.info(f"Model snapshot saved for job: {job_id}")

            # Move job to done/
            _move_job_abs(job_file_abs, done_dir_abs, parent_logger)

        except JobTimeoutError as e:
            job_logger.error(f"Job timed out: {e}")
            _handle_failure_abs(results_dir_abs, failed_dir_abs, job_file_abs, job_id, str(e), start_time, parent_logger)

        except JobExecutionError as e:
            job_logger.error(f"Job execution failed: {e}")
            _handle_failure_abs(results_dir_abs, failed_dir_abs, job_file_abs, job_id, str(e), start_time, parent_logger)

        except Exception as e:
            job_logger.error(f"Unexpected error: {e}")
            _handle_failure_abs(results_dir_abs, failed_dir_abs, job_file_abs, job_id, f"Unexpected error: {e}", start_time, parent_logger)


def _execute_with_timeout(
    job_id: str,
    dss_script: str,
    actions: list,
    timeout: int,
    start_time: float,
    logger: logging.Logger,
) -> tuple[JobResult, Optional[dict]]:
    """
    Execute DSS script with a best-effort timeout.

    Note: True timeout enforcement is complex (would need multiprocessing).
    This is a best-effort implementation that checks elapsed time.

    TODO: Stage 2+ - Use proper process isolation with hard timeout.
    
    Returns:
        Tuple of (JobResult, model_snapshot_dict or None)
    """
    import threading

    result_container: dict = {}
    model_container: dict = {}
    error_container: dict = {}

    def run_dss():
        try:
            runner = DSSRunner(logger=logger)

            # Run snapshot simulation (default)
            result_container["result"] = runner.execute(
                job_id, dss_script, start_time, actions=actions
            )
            
            # Extract model snapshot after simulation (circuit is still loaded)
            try:
                model_container["model"] = runner.extract_model_snapshot(job_id)
            except Exception as e:
                logger.warning(f"Error extracting model snapshot: {e}")
                model_container["model"] = None
                
        except Exception as e:
            error_container["error"] = e

    # Run in thread to enable timeout
    thread = threading.Thread(target=run_dss)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        # Thread is still running - timeout exceeded
        # Note: We can't forcefully kill the thread in Python
        # The thread will continue but we'll report timeout
        raise JobTimeoutError(f"Job exceeded timeout of {timeout} seconds")

    if "error" in error_container:
        raise error_container["error"]

    if "result" not in result_container:
        raise JobExecutionError("No result produced")

    return result_container["result"], model_container.get("model")


def _write_result_abs(results_dir: Path, result: JobResult) -> None:
    """Write job result to results directory (using absolute path)."""
    result_file = results_dir / f"{result.job_id}.json"
    result_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _write_model_abs(models_dir: Path, model_snapshot: dict) -> None:
    """Write model snapshot to models directory (using absolute path)."""
    job_id = model_snapshot.get("job_id", "unknown")
    model_file = models_dir / f"{job_id}.json"
    # Validate and serialize using Pydantic model
    model = JobModelSnapshot(**model_snapshot)
    model_file.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _move_job_abs(job_file: Path, target_dir: Path, logger: logging.Logger) -> None:
    """Move job file to target directory (using absolute paths)."""
    target_file = target_dir / job_file.name
    try:
        os.rename(str(job_file), str(target_file))
        logger.info(f"Moved job to {target_dir.name}/")
    except Exception as e:
        logger.error(f"Error moving job file: {e}")


def _handle_failure_abs(
    results_dir: Path,
    failed_dir: Path,
    job_file: Path,
    job_id: str,
    error_message: str,
    start_time: float,
    logger: logging.Logger,
) -> None:
    """Handle job failure: write error result and move to failed/ (using absolute paths)."""
    execution_time = time.time() - start_time

    # Create failure result
    result = JobResult(
        job_id=job_id,
        converged=False,
        circuit_summary=None,
        completed_at=utc_now_iso(),
        execution_time_seconds=round(execution_time, 3),
        error=error_message,
        log_file=f"logs/{job_id}.log",
    )

    _write_result_abs(results_dir, result)
    _move_job_abs(job_file, failed_dir, logger)

