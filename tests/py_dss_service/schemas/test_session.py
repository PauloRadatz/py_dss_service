"""
Unit tests for py_dss_service.schemas.session.
"""

import pytest

from py_dss_service.schemas.job_spec import AddLineInVsourceAction, DSSCommandAction
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


class TestSessionCreateResponse:
    """Tests for SessionCreateResponse."""

    def test_create(self):
        resp = SessionCreateResponse(session_id="sess-123")
        assert resp.session_id == "sess-123"
        assert resp.status == "created"


class TestSessionInfo:
    """Tests for SessionInfo."""

    def test_create(self):
        info = SessionInfo(
            session_id="sess-1",
            status="loaded",
            created_at="2024-01-15T12:00:00Z",
            last_activity="2024-01-15T12:05:00Z",
            circuit_loaded=True,
            circuit_name="TestCkt",
        )
        assert info.session_id == "sess-1"
        assert info.status == "loaded"
        assert info.circuit_name == "TestCkt"


class TestSessionListResponse:
    """Tests for SessionListResponse."""

    def test_create(self):
        resp = SessionListResponse(count=0, sessions=[])
        assert resp.count == 0
        assert resp.sessions == []


class TestLoadCircuitRequest:
    """Tests for LoadCircuitRequest."""

    def test_create(self):
        req = LoadCircuitRequest(dss_script="Clear\nnew circuit.c\nSolve")
        assert req.dss_script == "Clear\nnew circuit.c\nSolve"


class TestLoadCircuitResponse:
    """Tests for LoadCircuitResponse."""

    def test_create(self):
        resp = LoadCircuitResponse(circuit_name="MyCkt")
        assert resp.circuit_name == "MyCkt"
        assert resp.status == "loaded"


class TestSolveRequest:
    """Tests for SolveRequest."""

    def test_default_snapshot(self):
        req = SolveRequest()
        assert req.simulation_type == "snapshot"

    def test_qsts(self):
        req = SolveRequest(simulation_type="qsts")
        assert req.simulation_type == "qsts"


class TestSolveResponse:
    """Tests for SolveResponse."""

    def test_create(self):
        resp = SolveResponse(converged=True, simulation_type="snapshot")
        assert resp.converged is True
        assert resp.simulation_type == "snapshot"


class TestApplyActionsRequest:
    """Tests for ApplyActionsRequest."""

    def test_with_dss_command(self):
        req = ApplyActionsRequest(
            actions=[DSSCommandAction(type="dss_command", command="set loadmult=0.5")]
        )
        assert len(req.actions) == 1
        assert req.actions[0].command == "set loadmult=0.5"

    def test_with_add_line_in_vsource(self):
        req = ApplyActionsRequest(
            actions=[AddLineInVsourceAction(type="add_line_in_vsource", add_meter=True)]
        )
        assert len(req.actions) == 1
        assert req.actions[0].add_meter is True

    def test_min_length(self):
        with pytest.raises(ValueError):
            ApplyActionsRequest(actions=[])


class TestApplyActionsResponse:
    """Tests for ApplyActionsResponse."""

    def test_create(self):
        resp = ApplyActionsResponse(actions_count=2)
        assert resp.actions_count == 2
        assert resp.status == "applied"


class TestSessionDeleteResponse:
    """Tests for SessionDeleteResponse."""

    def test_create(self):
        resp = SessionDeleteResponse(session_id="sess-1")
        assert resp.session_id == "sess-1"
        assert resp.status == "closed"
