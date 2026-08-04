from fastapi.testclient import TestClient

from app.main import app
from app.shared.config import settings
from app.shared.database import get_db
from app.shared.errors import build_error_content
from app.shared.middleware import limiter

no_raise_client = TestClient(app, raise_server_exceptions=False)
client = TestClient(app)


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


def test_cors_header_present_on_unhandled_exception(api_headers):
    # A handler registered for the bare Exception class runs outside
    # CORSMiddleware too (same quirk as security headers, above) — without
    # this, a real server error looks like an opaque CORS failure to a
    # browser caller instead of the intended JSON error body.
    app.dependency_overrides[get_db] = _broken_db
    try:
        response = no_raise_client.get(
            "/v1/routes", headers={**api_headers, "Origin": "https://example.com"}
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_build_error_content_omits_hint_when_none():
    assert build_error_content("not_found", "Bike route not found") == {
        "error": {"code": "not_found", "message": "Bike route not found"}
    }


def test_build_error_content_includes_hint_when_given():
    assert build_error_content("rate_limited", "Slow down.", hint="Wait a moment.") == {
        "error": {"code": "rate_limited", "message": "Slow down.", "hint": "Wait a moment."}
    }


def test_page_size_over_cap_returns_friendly_message(api_headers):
    response = client.get("/v1/routes", headers=api_headers, params={"page_size": 500})
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "query.page_size: must be 200 or less"}
    }


def test_page_below_minimum_returns_friendly_message(api_headers):
    response = client.get("/v1/routes", headers=api_headers, params={"page": 0})
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "query.page: must be 1 or greater"}
    }


def test_page_size_non_integer_returns_friendly_message(api_headers):
    response = client.get("/v1/routes", headers=api_headers, params={"page_size": "abc"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "query.page_size: must be a whole number",
        }
    }


def test_invalid_enum_filter_returns_friendly_message(api_headers):
    response = client.get("/v1/parking", headers=api_headers, params={"type": "invalid"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "query.type: must be one of: 'paraciclo' or 'bicicletario'",
        }
    }


def test_unknown_query_param_returns_friendly_message_with_docs_hint(api_headers):
    response = client.get("/v1/routes", headers=api_headers, params={"foo": "bar"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "query.foo: this parameter isn't recognized",
            "hint": "See the parameter list at /docs for this endpoint.",
        }
    }


def test_bbox_validation_error_strips_value_error_prefix_and_adds_hint(api_headers):
    response = client.get("/v1/routes", headers=api_headers, params={"bbox": "not,a,valid,bbox"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "query.bbox: bbox values must be numeric",
            "hint": "Example: bbox=-38.63,-3.87,-38.42,-3.69",
        }
    }


def test_rate_limit_exceeded_returns_friendly_message_and_hint(api_headers):
    limiter.reset()
    try:
        for _ in range(settings.rate_limit_per_minute):
            response = client.get("/v1/routes", headers=api_headers, params={"page_size": 1})
            assert response.status_code == 200

        response = client.get("/v1/routes", headers=api_headers, params={"page_size": 1})
        assert response.status_code == 429
        assert response.json() == {
            "error": {
                "code": "rate_limited",
                "message": f"Rate limit exceeded ({settings.rate_limit_per_minute} "
                "requests per minute).",
                "hint": "Wait a moment before retrying.",
            }
        }
    finally:
        limiter.reset()


def test_401_error_includes_api_key_header_hint():
    response = client.get("/v1/routes")
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Invalid or missing API key",
            "hint": "Include an X-API-Key header with a valid key.",
        }
    }


def test_404_error_includes_check_id_hint(api_headers):
    response = client.get("/v1/parking/999999999", headers=api_headers)
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Bike parking not found",
            "hint": "Check that the id is correct.",
        }
    }
