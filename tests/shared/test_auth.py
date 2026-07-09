import pytest
from fastapi import HTTPException

from app.shared.auth import verify_api_key
from app.shared.config import settings

VALID_KEY = "dev-local-key"  # matches API_KEY_HASH in .env.example


def test_verify_api_key_rejects_missing_header():
    with pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key=None)
    assert exc.value.status_code == 401


def test_verify_api_key_rejects_wrong_key():
    with pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key="wrong-key")
    assert exc.value.status_code == 401


def test_verify_api_key_accepts_correct_key():
    if settings.api_key_hash != "3700285e3c8496a57e45eb1ccd43f2424852788576961320fbb31f86f17edb61":
        pytest.skip("local .env uses a different key than the fixture assumes")
    verify_api_key(x_api_key=VALID_KEY)
