import pytest

from app.shared.auth import hash_key
from app.shared.database import SessionLocal
from app.shared.models import ApiKey

PLAINTEXT_KEY = "test-key-for-router-suite"


@pytest.fixture
def api_headers():
    with SessionLocal() as session:
        api_key = ApiKey(key_hash=hash_key(PLAINTEXT_KEY), label="test-suite-router")
        session.add(api_key)
        session.commit()
        key_id = api_key.id
    yield {"X-API-Key": PLAINTEXT_KEY}
    with SessionLocal() as session:
        session.query(ApiKey).filter(ApiKey.id == key_id).delete()
        session.commit()
