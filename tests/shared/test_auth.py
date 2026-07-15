import pytest
from fastapi import HTTPException

from app.shared.auth import verify_api_key
from app.shared.database import SessionLocal
from app.shared.models import ApiKey


def test_verify_api_key_rejects_missing_header():
    with SessionLocal() as session, pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key=None, db=session)
    assert exc.value.status_code == 401


def test_verify_api_key_rejects_unknown_key():
    with SessionLocal() as session, pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key="not-a-real-key", db=session)
    assert exc.value.status_code == 401


def test_verify_api_key_rejects_revoked_key(make_api_key):
    plaintext, _ = make_api_key(label="test-suite-revoked", revoked=True)
    with SessionLocal() as session, pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key=plaintext, db=session)
    assert exc.value.status_code == 401


def test_verify_api_key_accepts_active_key(make_api_key):
    plaintext, _ = make_api_key(label="test-suite-active")
    with SessionLocal() as session:
        verify_api_key(x_api_key=plaintext, db=session)


def test_verify_api_key_updates_last_used_at(make_api_key):
    plaintext, key_id = make_api_key(label="test-suite-active")
    with SessionLocal() as session:
        verify_api_key(x_api_key=plaintext, db=session)
    with SessionLocal() as session:
        api_key = session.get(ApiKey, key_id)
        assert api_key.last_used_at is not None
