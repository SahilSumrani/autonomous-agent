import pytest
from packages.config.settings import Settings


def test_settings_default_values():
    settings = Settings()
    assert settings.APP_NAME == "TechVerse AI Client Acquisition OS"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.PORT == 8000
    assert settings.AI_PROVIDER == "ollama"
    assert settings.SSRF_PROTECTION_ENABLED is True


def test_database_url_assembly():
    settings = Settings(
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_SERVER="db.example.com",
        POSTGRES_PORT=5433,
        POSTGRES_DB="test_db",
        DATABASE_URL=None,
    )
    assert settings.DATABASE_URL == "postgresql+asyncpg://test_user:test_password@db.example.com:5433/test_db"


def test_redis_url_assembly():
    settings = Settings(
        REDIS_HOST="cache.example.com",
        REDIS_PORT=6380,
        REDIS_DB=2,
        REDIS_URL=None,
    )
    assert settings.REDIS_URL == "redis://cache.example.com:6380/2"


def test_cors_origins_parsing():
    settings = Settings(ALLOWED_ORIGINS="http://localhost:3000,http://app.example.com")
    assert settings.ALLOWED_ORIGINS == ["http://localhost:3000", "http://app.example.com"]
