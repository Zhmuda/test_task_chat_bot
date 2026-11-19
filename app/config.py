from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ACCESS_KEY_PATTERN = r"^[A-Za-z0-9_-]{8,255}$"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    access_key: str = Field(pattern=ACCESS_KEY_PATTERN)

    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_proxy: str | None = None
    gemini_timeout_seconds: float = 60.0

    database_path: Path = Path("data/chat.sqlite3")

    session_cookie_name: str = "chat_session"
    session_ttl_hours: int = 24 * 7
    cookie_secure: bool = False

    context_messages: int = 10

    login_max_attempts: int = 5
    login_window_seconds: int = 60

    @field_validator("gemini_proxy", mode="before")
    @classmethod
    def empty_proxy_is_none(cls, value: str | None) -> str | None:
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
