from app.shared.config import Settings


def test_settings_load_from_env():
    settings = Settings()

    assert settings.database_url
    assert settings.api_key_hash
    assert settings.rate_limit_per_minute == 60
