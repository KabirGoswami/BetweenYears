"""
Application configuration — loads from .env
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Gemini
    gemini_api_key: str

    # Email
    resend_api_key: str
    email_from: str = "noreply@betweenyears.app"
    email_from_name: str = "BetweenYears"

    # App
    secret_key: str
    frontend_url: str = "http://localhost:5500"
    environment: str = "development"
    app_name: str = "BetweenYears"

    # Rate limiting
    rate_limit_general: str = "100/minute"
    rate_limit_ai: str = "10/hour"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
