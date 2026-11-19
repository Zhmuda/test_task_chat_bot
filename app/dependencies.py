from typing import TYPE_CHECKING

from fastapi import Request

from app.config import Settings
from app.db import Database
from app.llm import LLMClient

if TYPE_CHECKING:
    from app.auth import LoginRateLimiter


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm


def get_rate_limiter(request: Request) -> "LoginRateLimiter":
    return request.app.state.login_limiter
