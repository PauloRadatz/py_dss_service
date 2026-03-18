"""Tests for /sessions API endpoints."""

import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from py_dss_service.api.main import create_app
from py_dss_service.common.time import utc_now_iso
from py_dss_service.schemas.results import JobResult
from py_dss_service.sessions.manager import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    session_id: str = "sess-abc123",
    circuit_loaded: bool = False,
    circuit_name: str | None = None,
    last_results: JobResult | None = None,
) -> Session:
    """Build a minimal Session dataclass for testing (no real DSS runner)."""
    now = utc_now_iso()
    runner = MagicMock()
    return Session(
        session_id=session_id,
        created_at=now,
        last_activity=now,
        runner=runner,
        circuit_loaded=circuit_loaded,
        circuit_name=circuit_name,
        last_results=last_results,
        lock=threading.Lock(),
    )


def _make_manager(sessions: list[Session] | None = None) -> MagicMock:
    """Build a mock SessionManager populated with the given sessions."""
    sessions = sessions or []
    by_id = {s.session_id: s for s in sessions}

    manager = MagicMock()
    manager.create_session.return_value = sessions[0] if sessions else _make_session()
    manager.get_session.side_effect = lambda sid: by_id.get(sid)
    manager.list_sessions.return_value = list(sessions)
    manager.close_session.side_effect = lambda sid: sid in by_id
    return manager


def _mock_lifespan_manager() -> MagicMock:
    """Session manager mock with async lifecycle methods for the app lifespan."""
    manager = MagicMock()
    manager.start_cleanup_task = AsyncMock()
    manager.stop_cleanup_task = AsyncMock()
    return manager


@pytest.fixture()
def client():
    """TestClient with a mocked lifespan session manager."""
    lifespan_manager = _mock_lifespan_manager()
    with patch("py_dss_service.api.main.get_session_manager", return_value=lifespan_manager):
        app = create_app()
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_returns_201(self, client):
        session = _make_session()
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.post("/sessions")
        assert response.status_code == 201

    def test_returns_session_id_and_created_status(self, client):
        session = _make_session("sess-xyz")
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.post("/sessions")
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "created"

    def test_max_sessions_reached_returns_503(self, client):
        manager = MagicMock()
        manager.create_session.side_effect = RuntimeError("Maximum sessions limit reached")
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=manager):
            response = client.post("/sessions")
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# GET /sessions
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_empty_list_returns_count_zero(self, client):
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager()):
            response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["sessions"] == []

    def test_with_sessions_returns_correct_count(self, client):
        sessions = [_make_session("sess-1"), _make_session("sess-2")]
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager(sessions)):
            response = client.get("/sessions")
        data = response.json()
        assert data["count"] == 2
        assert len(data["sessions"]) == 2


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}
# ---------------------------------------------------------------------------

class TestGetSession:
    def test_unknown_session_returns_404(self, client):
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager()):
            response = client.get("/sessions/nonexistent")
        assert response.status_code == 404

    def test_known_session_returns_200_with_id(self, client):
        session = _make_session("sess-known")
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-known")
        assert response.status_code == 200
        assert response.json()["session_id"] == "sess-known"

    def test_session_without_circuit_has_created_status(self, client):
        session = _make_session("sess-s1", circuit_loaded=False)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-s1")
        assert response.json()["status"] == "created"

    def test_session_with_circuit_has_loaded_status(self, client):
        session = _make_session("sess-s2", circuit_loaded=True)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-s2")
        assert response.json()["status"] == "loaded"


# ---------------------------------------------------------------------------
# DELETE /sessions/{session_id}
# ---------------------------------------------------------------------------

class TestCloseSession:
    def test_unknown_session_returns_404(self, client):
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager()):
            response = client.delete("/sessions/nonexistent")
        assert response.status_code == 404

    def test_known_session_returns_200_and_closed_status(self, client):
        session = _make_session("sess-del")
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.delete("/sessions/sess-del")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess-del"
        assert data["status"] == "closed"


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/results
# ---------------------------------------------------------------------------

class TestGetResults:
    def test_no_results_returns_404(self, client):
        session = _make_session("sess-r", circuit_loaded=True)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-r/results")
        assert response.status_code == 404

    def test_with_results_returns_200_and_data(self, client):
        result = JobResult(
            job_id="session-sess-r2",
            converged=True,
            completed_at=utc_now_iso(),
            circuit_summary={"P feeder (kW)": [100.0]},
        )
        session = _make_session("sess-r2", circuit_loaded=True, last_results=result)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-r2/results")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess-r2"
        assert data["result"]["converged"] is True


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/results/circuit_summary
# ---------------------------------------------------------------------------

class TestGetResultsCircuitSummary:
    def test_no_results_returns_404(self, client):
        session = _make_session("sess-cs", circuit_loaded=True)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-cs/results/circuit_summary")
        assert response.status_code == 404

    def test_returns_circuit_summary_data(self, client):
        result = JobResult(
            job_id="session-sess-cs2",
            converged=True,
            completed_at=utc_now_iso(),
            circuit_summary={"P feeder (kW)": [42.0]},
        )
        session = _make_session("sess-cs2", circuit_loaded=True, last_results=result)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-cs2/results/circuit_summary")
        assert response.status_code == 200
        data = response.json()
        assert data["field"] == "circuit_summary"
        assert data["data"] == {"P feeder (kW)": [42.0]}


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/results/voltages_ln
# ---------------------------------------------------------------------------

class TestGetResultsVoltagesLn:
    def test_no_results_returns_404(self, client):
        session = _make_session("sess-vln-empty", circuit_loaded=True)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-vln-empty/results/voltages_ln")
        assert response.status_code == 404

    def test_returns_voltages_ln_data(self, client):
        voltages = {"magnitude": {"bus1": {"1": 1.0}}}
        result = JobResult(
            job_id="session-sess-vln",
            converged=True,
            completed_at=utc_now_iso(),
            voltages_ln=voltages,
        )
        session = _make_session("sess-vln", circuit_loaded=True, last_results=result)
        with patch("py_dss_service.api.routers.sessions.get_session_manager", return_value=_make_manager([session])):
            response = client.get("/sessions/sess-vln/results/voltages_ln")
        assert response.status_code == 200
        data = response.json()
        assert data["field"] == "voltages_ln"
        assert data["data"] == voltages
