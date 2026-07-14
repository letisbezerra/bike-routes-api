import secrets
from datetime import UTC, datetime

import pytest

from app.shared.auth import hash_key
from app.shared.database import SessionLocal
from app.shared.models import ApiKey


@pytest.fixture
def make_api_key():
    """Factory fixture: each call issues a fresh, randomly-keyed ApiKey row
    (never a fixed constant — avoids colliding with a leftover row from an
    interrupted prior run, since key_hash is unique) and returns
    (plaintext, id). All keys created via this fixture are cleaned up
    together at teardown."""
    created_ids = []

    def _make(label="test-suite", revoked=False):
        plaintext = secrets.token_urlsafe(32)
        with SessionLocal() as session:
            api_key = ApiKey(
                key_hash=hash_key(plaintext),
                label=label,
                revoked_at=datetime.now(UTC) if revoked else None,
            )
            session.add(api_key)
            session.commit()
            created_ids.append(api_key.id)
        return plaintext, created_ids[-1]

    yield _make

    with SessionLocal() as session:
        session.query(ApiKey).filter(ApiKey.id.in_(created_ids)).delete(
            synchronize_session=False
        )
        session.commit()


@pytest.fixture
def api_headers(make_api_key):
    plaintext, _ = make_api_key(label="test-suite-router")
    return {"X-API-Key": plaintext}
