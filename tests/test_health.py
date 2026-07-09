from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_without_api_key():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_response_has_security_headers():
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert "strict-transport-security" in response.headers
