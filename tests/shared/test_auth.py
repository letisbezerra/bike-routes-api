from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.shared.auth import hash_key, verify_api_key
from app.shared.database import SessionLocal
from app.shared.models import ApiKey

PLAINTEXT_KEY = "test-key-for-auth-suite"
REVOKED_PLAINTEXT_KEY = "revoked-key-for-auth-suite"


@pytest.fixture
def active_key():
    with SessionLocal() as session:
        api_key = ApiKey(key_hash=hash_key(PLAINTEXT_KEY), label="test-suite-active")
        session.add(api_key)
        session.commit()
        key_id = api_key.id
    yield key_id
    with SessionLocal() as session:
        session.query(ApiKey).filter(ApiKey.id == key_id).delete()
        session.commit()


@pytest.fixture
def revoked_key():
    with SessionLocal() as session:
        api_key = ApiKey(
            key_hash=hash_key(REVOKED_PLAINTEXT_KEY),
            label="test-suite-revoked",
            revoked_at=datetime.now(UTC),
        )
        session.add(api_key)
        session.commit()
        key_id = api_key.id
    yield key_id
    with SessionLocal() as session:
        session.query(ApiKey).filter(ApiKey.id == key_id).delete()
        session.commit()


def test_verify_api_key_rejects_missing_header():
    with SessionLocal() as session, pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key=None, db=session)
    assert exc.value.status_code == 401


def test_verify_api_key_rejects_unknown_key():
    with SessionLocal() as session, pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key="not-a-real-key", db=session)
    assert exc.value.status_code == 401


def test_verify_api_key_rejects_revoked_key(revoked_key):
    with SessionLocal() as session, pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key=REVOKED_PLAINTEXT_KEY, db=session)
    assert exc.value.status_code == 401


def test_verify_api_key_accepts_active_key(active_key):
    with SessionLocal() as session:
        verify_api_key(x_api_key=PLAINTEXT_KEY, db=session)


def test_verify_api_key_updates_last_used_at(active_key):
    with SessionLocal() as session:
        verify_api_key(x_api_key=PLAINTEXT_KEY, db=session)
    with SessionLocal() as session:
        api_key = session.get(ApiKey, active_key)
        assert api_key.last_used_at is not None
