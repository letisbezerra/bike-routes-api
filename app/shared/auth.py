import hashlib
import logging
from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.shared.models import ApiKey

logger = logging.getLogger(__name__)

# auto_error=False: a missing header must fail the same way as a wrong one
# (401 via the check below), not FastAPI's own 403 "Not authenticated".
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(
    x_api_key: str | None = Depends(api_key_header), db: Session = Depends(get_db)
) -> None:
    """Issued/revoked via scripts/manage_keys.py — no self-service endpoint
    (docs/CONTEXT.md §1). A revoked key must return the same 401 as an
    unknown one, so the response never discloses which case applied."""
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == hash_key(x_api_key), ApiKey.revoked_at.is_(None))
        .first()
    )
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Best-effort: a failed traceability write must never fail the request
    # it's tracking.
    try:
        api_key.last_used_at = datetime.now(UTC)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to update last_used_at for api_key id=%s", api_key.id)
