"""Shared OpenAPI response examples — FastAPI doesn't auto-document
exception responses, so the error paths every endpoint can hit (auth,
validation, rate limit, not-found) are documented explicitly here instead
of repeating the same dict in every router."""

from app.shared.config import settings
from app.shared.errors import CODE_BY_STATUS

UNAUTHORIZED_RESPONSE = {
    "description": "Missing or invalid API key",
    "content": {
        "application/json": {
            "example": {
                "error": {"code": CODE_BY_STATUS[401], "message": "Invalid or missing API key"}
            }
        }
    },
}

VALIDATION_ERROR_RESPONSE = {
    "description": "Invalid query or path parameters",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": CODE_BY_STATUS[422],
                    "message": "page_size: Input should be less than or equal to 200",
                }
            }
        }
    },
}

RATE_LIMITED_RESPONSE = {
    "description": "Rate limit exceeded",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": CODE_BY_STATUS[429],
                    # Matches slowapi/limits' own message format ("<amount>
                    # per <multiples> <granularity>") for a "<n>/minute"
                    # limit — derived from settings, not a fixed "60", so it
                    # can't drift if RATE_LIMIT_PER_MINUTE is ever changed.
                    "message": f"{settings.rate_limit_per_minute} per 1 minute",
                }
            }
        }
    },
}

LIST_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    422: VALIDATION_ERROR_RESPONSE,
    429: RATE_LIMITED_RESPONSE,
}


def detail_responses(not_found_message: str) -> dict:
    """LIST_RESPONSES plus a 404 — `not_found_message` must match the exact
    `HTTPException(detail=...)` string the calling router raises, so the
    Swagger example never shows a message the API doesn't actually return."""
    return {
        **LIST_RESPONSES,
        404: {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {"code": CODE_BY_STATUS[404], "message": not_found_message}
                    }
                }
            },
        },
    }
