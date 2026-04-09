"""
Worker process entry point.

Run with: python -m py_dss_service.worker.main

Stage 1: Polls filesystem queue for pending jobs.
TODO: Stage 2+ - Replace with Redis/Celery worker.
"""

import signal
import time

from py_dss_service.logging import get_logger, setup_logging
from py_dss_service.settings import get_settings
from py_dss_service.worker.tasks import claim_job, process_job

# Global flag for graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    _shutdown_requested = True
    print("\nShutdown requested, finishing current job...")


def main() -> None:
    """
    Main worker loop.

    Polls for pending jobs and processes them sequentially.
    """
    global _shutdown_requested

    settings = get_settings()
    setup_logging(level=settings.log_level)
    logger = get_logger("worker")

    # Ensure directories exist
    settings.ensure_directories()

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print("Starting py-dss-service worker")
    print(f"Data directory: {settings.pydss_data_dir.absolute()}")
    print(f"Poll interval: {settings.worker_poll_interval}s")
    print(f"Job timeout: {settings.worker_job_timeout}s")
    print("Press Ctrl+C to stop...")

    logger.info("Worker started")

    while not _shutdown_requested:
        try:
            # Try to claim a job
            claimed = claim_job(settings, logger)

            if claimed is not None:
                job_file, job_spec = claimed
                logger.info(f"Processing job: {job_spec.job_id}")

                # Process the job
                process_job(settings, job_file, job_spec, logger)

                # Don't sleep after processing - check for more jobs immediately
                continue

            # No jobs available, sleep before next poll
            time.sleep(settings.worker_poll_interval)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(settings.worker_poll_interval)

    logger.info("Worker stopped")
    print("Worker stopped.")


if __name__ == "__main__":
    main()
