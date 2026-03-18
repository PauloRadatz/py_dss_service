"""
Unit tests for py_dss_service.schemas.model.
"""

import pytest

from py_dss_service.schemas.model import (
    JobModelResponse,
    JobModelSnapshot,
    ModelElementResponse,
)


class TestJobModelSnapshot:
    """Tests for JobModelSnapshot."""

    def test_minimal(self):
        snapshot = JobModelSnapshot(
            job_id="test-1",
            circuit_name="TestCkt",
        )
        assert snapshot.job_id == "test-1"
        assert snapshot.circuit_name == "TestCkt"
        assert snapshot.num_buses == 0
        assert snapshot.num_lines == 0
        assert snapshot.summary is None
        assert snapshot.buses is None

    def test_with_data(self):
        snapshot = JobModelSnapshot(
            job_id="test-2",
            circuit_name="MyCircuit",
            num_buses=5,
            num_lines=4,
            num_loads=3,
            summary={"key": {"value": 1}},
            buses={"bus1": {"x": 1.0}},
        )
        assert snapshot.num_buses == 5
        assert snapshot.buses["bus1"]["x"] == 1.0

    def test_round_trip(self):
        snapshot = JobModelSnapshot(
            job_id="test-3",
            circuit_name="Ckt",
            lines={"l1": {"length": 1.0}},
        )
        json_str = snapshot.model_dump_json()
        loaded = JobModelSnapshot.model_validate_json(json_str)
        assert loaded.lines == snapshot.lines


class TestJobModelResponse:
    """Tests for JobModelResponse."""

    def test_create(self):
        resp = JobModelResponse(job_id="abc", status="done")
        assert resp.job_id == "abc"
        assert resp.status == "done"
        assert resp.model is None


class TestModelElementResponse:
    """Tests for ModelElementResponse."""

    def test_create(self):
        resp = ModelElementResponse(
            job_id="abc",
            element_type="lines",
            count=2,
            data={"l1": {"length": 1.0}},
        )
        assert resp.job_id == "abc"
        assert resp.element_type == "lines"
        assert resp.count == 2
        assert resp.data["l1"]["length"] == 1.0
