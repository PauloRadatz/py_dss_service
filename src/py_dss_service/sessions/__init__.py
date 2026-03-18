"""
Session management module.

Provides session lifecycle management for interactive OpenDSS operations.
"""

from py_dss_service.sessions.manager import SessionManager, get_session_manager

__all__ = ["SessionManager", "get_session_manager"]

