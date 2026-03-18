"""Tests for py_dss_service.sessions.manager."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from py_dss_service.sessions.manager import (
    Session,
    SessionManager,
    get_session_manager,
)


# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------

class TestSession:
    def _make_session(self, **overrides) -> Session:
        defaults = dict(
            session_id="sess-test",
            created_at="2026-01-01T00:00:00+00:00",
            last_activity="2026-01-01T00:00:00+00:00",
            runner=MagicMock(),
        )
        defaults.update(overrides)
        return Session(**defaults)

    def test_status_created_by_default(self):
        s = self._make_session()
        assert s.status == "created"

    def test_status_loaded_when_circuit_loaded(self):
        s = self._make_session(circuit_loaded=True)
        assert s.status == "loaded"

    def test_status_active_when_last_results_set(self):
        s = self._make_session(last_results=MagicMock())
        assert s.status == "active"

    def test_status_active_takes_priority_over_loaded(self):
        s = self._make_session(circuit_loaded=True, last_results=MagicMock())
        assert s.status == "active"

    def test_touch_updates_last_activity(self):
        s = self._make_session()
        old = s.last_activity
        s.touch()
        assert s.last_activity != old


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class TestSessionManager:
    def _make_manager(self, **kwargs) -> SessionManager:
        defaults = dict(timeout_minutes=30, max_sessions=100, cleanup_interval_seconds=60)
        defaults.update(kwargs)
        return SessionManager(**defaults)

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_create_session_returns_session(self, MockRunner):
        mgr = self._make_manager()
        session = mgr.create_session()
        assert session.session_id.startswith("sess-")
        assert session.circuit_loaded is False
        assert session.last_results is None

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_create_session_increments_count(self, MockRunner):
        mgr = self._make_manager()
        assert mgr.session_count == 0
        mgr.create_session()
        assert mgr.session_count == 1
        mgr.create_session()
        assert mgr.session_count == 2

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_get_session_returns_session_by_id(self, MockRunner):
        mgr = self._make_manager()
        session = mgr.create_session()
        found = mgr.get_session(session.session_id)
        assert found is session

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_get_session_returns_none_for_unknown_id(self, MockRunner):
        mgr = self._make_manager()
        assert mgr.get_session("nonexistent") is None

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_list_sessions_returns_all(self, MockRunner):
        mgr = self._make_manager()
        s1 = mgr.create_session()
        s2 = mgr.create_session()
        sessions = mgr.list_sessions()
        ids = {s.session_id for s in sessions}
        assert s1.session_id in ids
        assert s2.session_id in ids
        assert len(sessions) == 2

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_close_session_removes_and_returns_true(self, MockRunner):
        mgr = self._make_manager()
        session = mgr.create_session()
        assert mgr.close_session(session.session_id) is True
        assert mgr.session_count == 0
        assert mgr.get_session(session.session_id) is None

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_close_session_returns_false_for_unknown(self, MockRunner):
        mgr = self._make_manager()
        assert mgr.close_session("nonexistent") is False

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_max_sessions_limit_raises(self, MockRunner):
        mgr = self._make_manager(max_sessions=2)
        mgr.create_session()
        mgr.create_session()
        with pytest.raises(RuntimeError, match="Maximum sessions limit"):
            mgr.create_session()

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_cleanup_expired_removes_stale_sessions(self, MockRunner):
        mgr = self._make_manager(timeout_minutes=5)
        session = mgr.create_session()

        # Set last_activity to 10 minutes ago
        old_time = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=10)
        ).isoformat()
        session.last_activity = old_time

        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr.session_count == 0

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_cleanup_expired_keeps_active_sessions(self, MockRunner):
        mgr = self._make_manager(timeout_minutes=30)
        session = mgr.create_session()
        session.touch()

        removed = mgr.cleanup_expired()
        assert removed == 0
        assert mgr.session_count == 1

    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_cleanup_expired_mixed(self, MockRunner):
        mgr = self._make_manager(timeout_minutes=5)
        stale = mgr.create_session()
        fresh = mgr.create_session()

        old_time = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=10)
        ).isoformat()
        stale.last_activity = old_time
        fresh.touch()

        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr.session_count == 1
        assert mgr.get_session(fresh.session_id) is not None
        assert mgr.get_session(stale.session_id) is None


# ---------------------------------------------------------------------------
# get_session_manager singleton
# ---------------------------------------------------------------------------

class TestGetSessionManager:
    @patch("py_dss_service.sessions.manager._session_manager", None)
    @patch("py_dss_service.settings.get_settings")
    @patch("py_dss_service.sessions.manager.DSSRunner")
    def test_returns_session_manager(self, MockRunner, mock_get_settings):
        mock_settings = MagicMock()
        mock_settings.session_timeout_minutes = 15
        mock_settings.session_max_count = 50
        mock_settings.session_cleanup_interval = 30
        mock_get_settings.return_value = mock_settings

        mgr = get_session_manager()
        assert isinstance(mgr, SessionManager)
        assert mgr._timeout_minutes == 15
        assert mgr._max_sessions == 50
        assert mgr._cleanup_interval == 30


# ---------------------------------------------------------------------------
# __init__.py exports
# ---------------------------------------------------------------------------

class TestPackageExports:
    def test_session_manager_importable(self):
        from py_dss_service.sessions import SessionManager
        assert SessionManager is not None

    def test_get_session_manager_importable(self):
        from py_dss_service.sessions import get_session_manager
        assert callable(get_session_manager)
