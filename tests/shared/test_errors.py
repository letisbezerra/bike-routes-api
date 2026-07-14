from fastapi.testclient import TestClient

from app.main import app
from app.shared.database import get_db

no_raise_client = TestClient(app, raise_server_exceptions=False)


def _broken_db():
    raise RuntimeError("simulated failure — should never reach the client")


def test_unhandled_exception_returns_generic_500(api_headers):
    app.dependency_overrides[get_db] = _broken_db
    try:
        response = no_raise_client.get("/v1/routes", headers=api_headers)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "An unexpected error occurred."}
    }
    assert "RuntimeError" not in response.text
    assert "simulated failure" not in response.text


def test_security_headers_present_on_every_response():
    response = TestClient(app).get("/health")
    assert response.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
