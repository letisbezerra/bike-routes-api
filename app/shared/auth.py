import hashlib
import hmac

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.shared.config import settings

# auto_error=False: a missing header must fail the same way as a wrong one
# (401 via the check below), not FastAPI's own 403 "Not authenticated".
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(x_api_key: str | None = Depends(api_key_header)) -> None:
    """Bootstrap single-key check (Phase 1). Replaced by a DB-backed
    api_keys table with issuance/revocation in Phase 4 — see spec 01."""
    if x_api_key is None or not hmac.compare_digest(_hash(x_api_key), settings.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
