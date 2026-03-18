"""Tests for GET /health endpoint."""

from fastapi.testclient import TestClient

from py_dss_service.api.main import create_app


class TestHealth:
    def test_health_returns_200(self):
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self):
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.json() == {"status": "ok"}
