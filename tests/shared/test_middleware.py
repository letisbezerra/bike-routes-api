import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.shared.config import settings
from app.shared.middleware import default_limit, limiter

client = TestClient(app)

VALID_KEY = "dev-local-key"  # matches API_KEY_HASH in .env.example, see tests/shared/test_auth.py
_HEADERS = {"X-API-Key": VALID_KEY}


def _skip_if_key_mismatch():
    if settings.api_key_hash != "3700285e3c8496a57e45eb1ccd43f2424852788576961320fbb31f86f17edb61":
        pytest.skip("local .env uses a different key than the fixture assumes")


def test_limiter_enabled():
    assert limiter.enabled


def test_default_limit_matches_settings_rate():
    assert default_limit == f"{settings.rate_limit_per_minute}/minute"


def test_exceeding_rate_limit_returns_429():
    _skip_if_key_mismatch()
    limiter.reset()
    try:
        for _ in range(settings.rate_limit_per_minute):
            response = client.get("/v1/routes", headers=_HEADERS)
            assert response.status_code == 200

        response = client.get("/v1/routes", headers=_HEADERS)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "rate_limited"
    finally:
        limiter.reset()


def test_health_is_not_rate_limited():
    limiter.reset()
    try:
        for _ in range(settings.rate_limit_per_minute + 1):
            response = client.get("/health")
            assert response.status_code == 200
    finally:
        limiter.reset()
