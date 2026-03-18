"""
Unit tests for py_dss_service.schemas.job_spec.
"""

import pytest

from py_dss_service.common.time import utc_now_iso
from py_dss_service.schemas.job_spec import (
    AddLineInVsourceAction,
    DSSCommandAction,
    JobSpec,
    JobSubmitRequest,
    JobSubmitResponse,
)


class TestDSSCommandAction:
    """Tests for DSSCommandAction."""

    def test_create(self):
        action = DSSCommandAction(type="dss_command", command="set loadmult=0.5")
        assert action.type == "dss_command"
        assert action.command == "set loadmult=0.5"

    def test_command_min_length(self):
        with pytest.raises(ValueError):
            DSSCommandAction(type="dss_command", command="")


class TestAddLineInVsourceAction:
    """Tests for AddLineInVsourceAction."""

    def test_create_defaults(self):
        action = AddLineInVsourceAction(type="add_line_in_vsource")
        assert action.type == "add_line_in_vsource"
        assert action.add_meter is False
        assert action.add_monitors is False

    def test_create_with_options(self):
        action = AddLineInVsourceAction(
            type="add_line_in_vsource",
            add_meter=True,
            add_monitors=True,
        )
        assert action.add_meter is True
        assert action.add_monitors is True


class TestActionUnion:
    """Tests for Action union type (parsed via JobSpec which has list[Action])."""

    def test_dss_command_parses_as_action(self):
        data = {
            "job_id": "test",
            "dss_script": "Clear\nnew circuit.c",
            "created_at": "2024-01-15T12:00:00Z",
            "actions": [{"type": "dss_command", "command": "solve"}],
        }
        spec = JobSpec.model_validate(data)
        assert len(spec.actions) == 1
        assert isinstance(spec.actions[0], DSSCommandAction)
        assert spec.actions[0].command == "solve"

    def test_add_line_in_vsource_parses_as_action(self):
        data = {
            "job_id": "test",
            "dss_script": "Clear\nnew circuit.c",
            "created_at": "2024-01-15T12:00:00Z",
            "actions": [{"type": "add_line_in_vsource", "add_meter": True}],
        }
        spec = JobSpec.model_validate(data)
        assert len(spec.actions) == 1
        assert isinstance(spec.actions[0], AddLineInVsourceAction)
        assert spec.actions[0].add_meter is True


class TestJobSubmitRequest:
    """Tests for JobSubmitRequest."""

    def test_minimal(self):
        req = JobSubmitRequest(dss_script="Clear\nnew circuit.c\nSolve")
        assert req.dss_script == "Clear\nnew circuit.c\nSolve"
        assert req.simulation_type == "snapshot"
        assert req.actions == []

    def test_full(self):
        req = JobSubmitRequest(
            dss_script="Clear\nnew circuit.c\nSolve",
            simulation_type="qsts",
            actions=[DSSCommandAction(type="dss_command", command="solve")],
        )
        assert req.simulation_type == "qsts"
        assert len(req.actions) == 1


class TestJobSpec:
    """Tests for JobSpec."""

    def test_round_trip(self):
        spec = JobSpec(
            job_id="test-1",
            dss_script="Clear\nnew circuit.c\nSolve",
            created_at=utc_now_iso(),
        )
        json_str = spec.model_dump_json()
        loaded = JobSpec.model_validate_json(json_str)
        assert loaded.job_id == spec.job_id
        assert loaded.dss_script == spec.dss_script

    def test_with_actions(self):
        spec = JobSpec(
            job_id="test-2",
            dss_script="Clear\nnew circuit.c",
            created_at=utc_now_iso(),
            actions=[AddLineInVsourceAction(type="add_line_in_vsource")],
        )
        assert len(spec.actions) == 1
        assert isinstance(spec.actions[0], AddLineInVsourceAction)


class TestJobSubmitResponse:
    """Tests for JobSubmitResponse."""

    def test_create(self):
        resp = JobSubmitResponse(job_id="abc-123", status="queued")
        assert resp.job_id == "abc-123"
        assert resp.status == "queued"
