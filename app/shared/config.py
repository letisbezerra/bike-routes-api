from pydantic_settings import BaseSettings, SettingsConfigDict

# Single source for the app's technical name — matches pyproject.toml's
# `name`. Shared by app/main.py (FastAPI title) and
# app/shared/observability.py (trace SERVICE_NAME) so a rename can't leave
# one of them stale.
APP_NAME = "bike-routes-api"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    rate_limit_per_minute: int = 60
    environment: str = "development"
    enable_observability: bool = False
    sentry_dsn: str | None = None


settings = Settings()
