from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Nonprofit Intake API"
    environment: str = "local"
    debug: bool = False
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",  # client app
        "http://localhost:5174",  # admin app
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()