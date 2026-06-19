from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, resolved relative to this file so it loads from any cwd.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Postgres (direct connection for Alembic + SQLAlchemy)
    database_url: PostgresDsn

    # Google Gemini
    gemini_api_key: str
    gemini_chat_model: str = "gemini-2.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimensions: int = 768

    # Server — JSON-encoded list in env: '["https://app.example.com","http://localhost:5173"]'
    allowed_origins: list[str] = ["http://localhost:5173"]

    # Logging
    log_level: str = "INFO"
    log_json: bool = False  # set True in prod for machine-parseable logs


settings = Settings()
