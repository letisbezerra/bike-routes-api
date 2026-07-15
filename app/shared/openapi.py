"""Shared OpenAPI response examples — FastAPI doesn't auto-document
exception responses, so the error paths every endpoint can hit (auth,
validation, rate limit, not-found) are documented explicitly here instead
of repeating the same dict in every router."""

UNAUTHORIZED_RESPONSE = {
    "description": "Missing or invalid API key",
    "content": {
        "application/json": {
            "example": {"error": {"code": "unauthorized", "message": "Invalid or missing API key"}}
        }
    },
}

VALIDATION_ERROR_RESPONSE = {
    "description": "Invalid query or path parameters",
    "content": {
        "application/json": {
            "example": {
                "error": {
                    "code": "validation_error",
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
            "example": {"error": {"code": "rate_limited", "message": "60 per 1 minute"}}
        }
    },
}

NOT_FOUND_RESPONSE = {
    "description": "Resource not found",
    "content": {
        "application/json": {
            "example": {"error": {"code": "not_found", "message": "Resource not found"}}
        }
    },
}

LIST_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    422: VALIDATION_ERROR_RESPONSE,
    429: RATE_LIMITED_RESPONSE,
}
DETAIL_RESPONSES = {
    401: UNAUTHORIZED_RESPONSE,
    404: NOT_FOUND_RESPONSE,
    422: VALIDATION_ERROR_RESPONSE,
    429: RATE_LIMITED_RESPONSE,
}
