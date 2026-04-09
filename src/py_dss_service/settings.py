"""
Application settings and configuration.

Stage 1: Uses environment variables and filesystem paths.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


def _get_project_root() -> Path:
    """
    Get the project root directory.

    Tries to find the project root by looking for common markers:
    - pyproject.toml
    - .git directory
    - src/py_dss_service directory

    Falls back to current working directory if markers not found.
    """
    # Start from current file location
    current = Path(__file__).resolve().parent

    # Walk up to find project root markers
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
        if (parent / ".git").exists():
            return parent
        if (parent / "src" / "py_dss_service").exists():
            return parent

    # Fallback: use current working directory
    return Path.cwd()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Base data directory for all job-related files
    # Defaults to project root / data, but can be overridden via environment variable
    pydss_data_dir: Path = Path(_get_project_root() / "data")

    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Worker settings
    worker_poll_interval: float = 1.0  # seconds between polling for new jobs
    worker_job_timeout: int = 300  # max seconds per job (5 minutes default)

    # Script validation settings
    max_script_length: int = 200 * 1024  # 200 KB max script size

    # Session settings
    session_timeout_minutes: int = 30  # Close session after N minutes of inactivity
    session_max_count: int = 100  # Maximum concurrent sessions
    session_cleanup_interval: int = 60  # Check for expired sessions every N seconds

    # Logging
    log_level: str = "INFO"

    model_config = {
        "env_prefix": "PYDSS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    def __init__(self, **kwargs):
        """Initialize settings, ensuring data_dir is absolute."""
        super().__init__(**kwargs)
        # Ensure pydss_data_dir is absolute
        if not self.pydss_data_dir.is_absolute():
            # If relative, resolve relative to project root
            self.pydss_data_dir = _get_project_root() / self.pydss_data_dir
        # Convert to absolute path
        self.pydss_data_dir = self.pydss_data_dir.resolve()

    @property
    def jobs_pending_dir(self) -> Path:
        return self.pydss_data_dir / "jobs" / "pending"

    @property
    def jobs_running_dir(self) -> Path:
        return self.pydss_data_dir / "jobs" / "running"

    @property
    def jobs_done_dir(self) -> Path:
        return self.pydss_data_dir / "jobs" / "done"

    @property
    def jobs_failed_dir(self) -> Path:
        return self.pydss_data_dir / "jobs" / "failed"

    @property
    def results_dir(self) -> Path:
        return self.pydss_data_dir / "results"

    @property
    def models_dir(self) -> Path:
        """Directory for saved model snapshots (jobs only)."""
        return self.pydss_data_dir / "models"

    @property
    def logs_dir(self) -> Path:
        return self.pydss_data_dir / "logs"

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        dirs = [
            self.jobs_pending_dir,
            self.jobs_running_dir,
            self.jobs_done_dir,
            self.jobs_failed_dir,
            self.results_dir,
            self.models_dir,
            self.logs_dir,
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance (lazy initialization)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
