"""Tests for /jobs API endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from py_dss_service.api.main import create_app
from py_dss_service.common.time import utc_now_iso
from py_dss_service.schemas.job_spec import JobSpec
from py_dss_service.schemas.results import JobResult
from py_dss_service.settings import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_settings(tmp_path) -> Settings:
    """Isolated Settings instance pointing at tmp_path."""
    s = Settings(pydss_data_dir=tmp_path / "data")
    s.ensure_directories()
    return s


def _mock_lifespan_manager() -> MagicMock:
    """Session manager mock with async lifecycle methods for the lifespan."""
    manager = MagicMock()
    manager.start_cleanup_task = AsyncMock()
    manager.stop_cleanup_task = AsyncMock()
    return manager


@pytest.fixture()
def client(fake_settings):
    """TestClient with isolated data directory and no real DSS."""
    manager = _mock_lifespan_manager()
    with patch("py_dss_service.settings._settings", fake_settings), \
         patch("py_dss_service.api.main.get_session_manager", return_value=manager):
        app = create_app()
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# POST /jobs
# ---------------------------------------------------------------------------

class TestSubmitJob:
    def test_valid_script_returns_201(self, client):
        response = client.post("/jobs", json={"dss_script": "New Circuit.T basekv=12.47\nSolve"})
        assert response.status_code == 201

    def test_valid_script_returns_job_id_and_queued_status(self, client):
        response = client.post("/jobs", json={"dss_script": "New Circuit.T basekv=12.47\nSolve"})
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_forbidden_command_returns_400(self, client):
        response = client.post("/jobs", json={"dss_script": "compile myfile.dss"})
        assert response.status_code == 400
        assert "forbidden" in response.json()["detail"].lower()

    def test_missing_script_returns_422(self, client):
        response = client.post("/jobs", json={})
        assert response.status_code == 422

    def test_job_file_written_to_pending(self, client, fake_settings):
        response = client.post("/jobs", json={"dss_script": "New Circuit.T\nSolve"})
        job_id = response.json()["job_id"]
        pending_file = fake_settings.jobs_pending_dir / f"{job_id}.json"
        assert pending_file.exists()

    def test_job_file_contains_valid_spec(self, client, fake_settings):
        response = client.post("/jobs", json={"dss_script": "New Circuit.T\nSolve"})
        job_id = response.json()["job_id"]
        pending_file = fake_settings.jobs_pending_dir / f"{job_id}.json"
        spec = JobSpec.model_validate_json(pending_file.read_text(encoding="utf-8"))
        assert spec.job_id == job_id
        assert spec.dss_script == "New Circuit.T\nSolve"


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------

class TestGetJobStatus:
    def test_unknown_job_returns_404(self, client):
        response = client.get("/jobs/nonexistent-job-id")
        assert response.status_code == 404

    def test_queued_job_returns_queued_status(self, client):
        submit = client.post("/jobs", json={"dss_script": "New Circuit.T\nSolve"})
        job_id = submit.json()["job_id"]

        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_done_job_returns_done_status(self, client, fake_settings):
        job_id = "test-done-job"
        spec = JobSpec(job_id=job_id, dss_script="Solve", created_at=utc_now_iso())
        (fake_settings.jobs_done_dir / f"{job_id}.json").write_text(
            spec.model_dump_json(), encoding="utf-8"
        )
        result = JobResult(job_id=job_id, converged=True, completed_at=utc_now_iso())
        (fake_settings.results_dir / f"{job_id}.json").write_text(
            result.model_dump_json(), encoding="utf-8"
        )

        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "done"

    def test_failed_job_includes_error(self, client, fake_settings):
        job_id = "test-failed-job"
        spec = JobSpec(job_id=job_id, dss_script="Solve", created_at=utc_now_iso())
        (fake_settings.jobs_failed_dir / f"{job_id}.json").write_text(
            spec.model_dump_json(), encoding="utf-8"
        )
        result = JobResult(
            job_id=job_id, converged=False, completed_at=utc_now_iso(), error="DSS error"
        )
        (fake_settings.results_dir / f"{job_id}.json").write_text(
            result.model_dump_json(), encoding="utf-8"
        )

        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "DSS error"


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/result
# ---------------------------------------------------------------------------

class TestGetJobResult:
    def test_unknown_job_returns_404(self, client):
        response = client.get("/jobs/nonexistent/result")
        assert response.status_code == 404

    def test_queued_job_result_returns_404(self, client):
        submit = client.post("/jobs", json={"dss_script": "New Circuit.T\nSolve"})
        job_id = submit.json()["job_id"]
        response = client.get(f"/jobs/{job_id}/result")
        assert response.status_code == 404

    def test_done_job_result_returns_data(self, client, fake_settings):
        job_id = "test-result-job"
        spec = JobSpec(job_id=job_id, dss_script="Solve", created_at=utc_now_iso())
        (fake_settings.jobs_done_dir / f"{job_id}.json").write_text(
            spec.model_dump_json(), encoding="utf-8"
        )
        result = JobResult(
            job_id=job_id,
            converged=True,
            completed_at=utc_now_iso(),
            circuit_summary={"P feeder (kW)": [100.0]},
        )
        (fake_settings.results_dir / f"{job_id}.json").write_text(
            result.model_dump_json(), encoding="utf-8"
        )

        response = client.get(f"/jobs/{job_id}/result")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"
        assert data["result"]["converged"] is True

    def test_fields_filter_returns_only_requested(self, client, fake_settings):
        job_id = "test-fields-job"
        spec = JobSpec(job_id=job_id, dss_script="Solve", created_at=utc_now_iso())
        (fake_settings.jobs_done_dir / f"{job_id}.json").write_text(
            spec.model_dump_json(), encoding="utf-8"
        )
        result = JobResult(
            job_id=job_id,
            converged=True,
            completed_at=utc_now_iso(),
            circuit_summary={"P feeder (kW)": [100.0]},
            voltages_ln={"magnitude": {}},
        )
        (fake_settings.results_dir / f"{job_id}.json").write_text(
            result.model_dump_json(), encoding="utf-8"
        )

        response = client.get(f"/jobs/{job_id}/result?fields=circuit_summary")
        assert response.status_code == 200
        result_data = response.json()["result"]
        assert "circuit_summary" in result_data
        assert "voltages_ln" not in result_data

    def test_invalid_fields_param_returns_400(self, client, fake_settings):
        job_id = "test-badfield-job"
        spec = JobSpec(job_id=job_id, dss_script="Solve", created_at=utc_now_iso())
        (fake_settings.jobs_done_dir / f"{job_id}.json").write_text(
            spec.model_dump_json(), encoding="utf-8"
        )
        result = JobResult(job_id=job_id, converged=True, completed_at=utc_now_iso())
        (fake_settings.results_dir / f"{job_id}.json").write_text(
            result.model_dump_json(), encoding="utf-8"
        )

        response = client.get(f"/jobs/{job_id}/result?fields=nonexistent_field")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/model
# ---------------------------------------------------------------------------

class TestGetJobModel:
    def test_queued_job_model_returns_404(self, client):
        submit = client.post("/jobs", json={"dss_script": "New Circuit.T\nSolve"})
        job_id = submit.json()["job_id"]
        response = client.get(f"/jobs/{job_id}/model")
        assert response.status_code == 404

    def test_done_job_no_model_file_returns_404(self, client, fake_settings):
        job_id = "test-model-missing"
        spec = JobSpec(job_id=job_id, dss_script="Solve", created_at=utc_now_iso())
        (fake_settings.jobs_done_dir / f"{job_id}.json").write_text(
            spec.model_dump_json(), encoding="utf-8"
        )

        response = client.get(f"/jobs/{job_id}/model")
        assert response.status_code == 404

    def test_invalid_element_type_returns_400(self, client, fake_settings):
        job_id = "test-elem-type"
        spec = JobSpec(job_id=job_id, dss_script="Solve", created_at=utc_now_iso())
        (fake_settings.jobs_done_dir / f"{job_id}.json").write_text(
            spec.model_dump_json(), encoding="utf-8"
        )

        response = client.get(f"/jobs/{job_id}/model/generators")
        assert response.status_code == 400
