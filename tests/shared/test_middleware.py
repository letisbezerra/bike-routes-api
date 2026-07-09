from app.shared.config import settings
from app.shared.middleware import limiter


def test_limiter_configured_with_settings_rate():
    assert limiter.enabled
    assert len(limiter._default_limits) == 1

    parsed_limit = next(iter(limiter._default_limits[0])).limit
    assert parsed_limit.amount == settings.rate_limit_per_minute
