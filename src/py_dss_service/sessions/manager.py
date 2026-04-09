"""
Session manager.

Handles session lifecycle: create, store, cleanup, and access.
"""

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Optional

from py_dss_service.common.ids import generate_job_id
from py_dss_service.common.time import utc_now_iso
from py_dss_service.engine.runner import DSSRunner
from py_dss_service.schemas.results import JobResult


@dataclass
class Session:
    """Represents an active session with a DSS instance."""

    session_id: str
    created_at: str
    last_activity: str
    runner: DSSRunner
    circuit_loaded: bool = False
    circuit_name: Optional[str] = None
    last_results: Optional[JobResult] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def status(self) -> str:
        """Get session status based on state."""
        if self.last_results is not None:
            return "active"
        elif self.circuit_loaded:
            return "loaded"
        else:
            return "created"

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = utc_now_iso()


class SessionManager:
    """
    Manages session lifecycle and storage.

    Thread-safe session management with automatic cleanup of inactive sessions.
    """

    def __init__(
        self,
        timeout_minutes: int = 30,
        max_sessions: int = 100,
        cleanup_interval_seconds: int = 60,
    ):
        """
        Initialize session manager.

        Args:
            timeout_minutes: Minutes of inactivity before session is cleaned up
            max_sessions: Maximum number of concurrent sessions
            cleanup_interval_seconds: How often to check for expired sessions
        """
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._timeout_minutes = timeout_minutes
        self._max_sessions = max_sessions
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger(__name__)

    def create_session(self) -> Session:
        """
        Create a new session.

        Returns:
            The newly created Session

        Raises:
            RuntimeError: If max sessions limit is reached
        """
        with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise RuntimeError(
                    f"Maximum sessions limit ({self._max_sessions}) reached. "
                    "Please close unused sessions."
                )

            # Generate unique session ID
            session_id = f"sess-{generate_job_id()}"
            now = utc_now_iso()

            # Create DSS runner for this session
            runner = DSSRunner(logger=logging.getLogger(f"session.{session_id}"))

            session = Session(
                session_id=session_id,
                created_at=now,
                last_activity=now,
                runner=runner,
            )

            self._sessions[session_id] = session
            self._logger.info(f"Created session: {session_id}")

            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: The session ID to look up

        Returns:
            The Session if found, None otherwise
        """
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[Session]:
        """
        List all active sessions.

        Returns:
            List of all active sessions
        """
        with self._lock:
            return list(self._sessions.values())

    def close_session(self, session_id: str) -> bool:
        """
        Close and remove a session.

        Args:
            session_id: The session ID to close

        Returns:
            True if session was closed, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._logger.info(f"Closed session: {session_id}")
                return True
            return False

    def cleanup_expired(self) -> int:
        """
        Remove sessions that have been inactive too long.

        Returns:
            Number of sessions cleaned up
        """
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        timeout = datetime.timedelta(minutes=self._timeout_minutes)
        expired = []

        with self._lock:
            for session_id, session in self._sessions.items():
                # Parse last activity timestamp
                try:
                    last_activity = datetime.datetime.fromisoformat(
                        session.last_activity.replace("Z", "+00:00")
                    )
                    if now - last_activity > timeout:
                        expired.append(session_id)
                except Exception:
                    # If we can't parse the timestamp, don't expire
                    pass

            for session_id in expired:
                del self._sessions[session_id]
                self._logger.info(f"Expired session (timeout): {session_id}")

        return len(expired)

    async def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._logger.info("Started session cleanup task")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            self._logger.info("Stopped session cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background loop to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                count = self.cleanup_expired()
                if count > 0:
                    self._logger.info(f"Cleaned up {count} expired sessions")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cleanup loop: {e}")

    @property
    def session_count(self) -> int:
        """Get number of active sessions."""
        with self._lock:
            return len(self._sessions)


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        # Import settings here to avoid circular imports
        from py_dss_service.settings import get_settings

        settings = get_settings()
        _session_manager = SessionManager(
            timeout_minutes=settings.session_timeout_minutes,
            max_sessions=settings.session_max_count,
            cleanup_interval_seconds=settings.session_cleanup_interval,
        )
    return _session_manager
