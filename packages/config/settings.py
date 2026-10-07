import json
from typing import List, Literal, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core Application
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    APP_NAME: str = "TechVerse AI Client Acquisition OS"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "techverse_dev_secret_key_ultra_secure_local_development_2026"

    # Server Binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "techverse_os"
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        if isinstance(v, str) and v.strip():
            return v
        data = info.data
        user = data.get("POSTGRES_USER", "postgres")
        password = data.get("POSTGRES_PASSWORD", "postgres")
        server = data.get("POSTGRES_SERVER", "localhost")
        port = data.get("POSTGRES_PORT", 5432)
        db = data.get("POSTGRES_DB", "techverse_os")
        return f"postgresql+asyncpg://{user}:{password}@{server}:{port}/{db}"

    # Redis Cache & Event Bus
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info) -> str:
        if isinstance(v, str) and v.strip():
            return v
        data = info.data
        host = data.get("REDIS_HOST", "localhost")
        port = data.get("REDIS_PORT", 6379)
        db = data.get("REDIS_DB", 0)
        return f"redis://{host}:{port}/{db}"

    # AI Configuration (Local-first & Cloud Fast Inference)
    AI_PROVIDER: Literal["ollama", "groq", "openai", "gemini", "anthropic"] = "ollama"
    AI_FALLBACK_PROVIDER: Optional[str] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: float = 30.0
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Providers
    SEARCH_PROVIDER: str = "local"
    ENRICHMENT_PROVIDER: str = "none"
    HUNTER_API_KEY: Optional[str] = None

    # Outreach
    OUTREACH_PROVIDER: str = "manual"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "outreach@techverse.ai"

    # Security & Networking
    ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    SSRF_PROTECTION_ENABLED: bool = True

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        return v


settings = Settings()
