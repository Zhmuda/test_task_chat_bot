import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import LoginRateLimiter
from app.config import Settings, get_settings
from app.db import Database
from app.llm import GeminiClient, LLMClient
from app.routers import auth, chat

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


_VALIDATION_MESSAGES = {
    "access_key": "Ключ: 8–255 символов, только латиница, цифры, «-» и «_»",
    "text": "Сообщение: от 1 до 500 символов, не только пробелы",
}


def _validation_message(exc: RequestValidationError) -> str:
    for error in exc.errors():
        field = error.get("loc", ())[-1] if error.get("loc") else None
        if field in _VALIDATION_MESSAGES:
            return _VALIDATION_MESSAGES[field]
    return "Некорректный запрос"


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings or get_settings()
        app.state.db = Database(app.state.settings.database_path)
        app.state.llm = llm or GeminiClient(app.state.settings)
        app.state.login_limiter = LoginRateLimiter(
            app.state.settings.login_max_attempts, app.state.settings.login_window_seconds
        )
        yield
        app.state.db.close()
        if isinstance(app.state.llm, GeminiClient):
            app.state.llm.close()

    app = FastAPI(title="Шеф — кулинарный чат", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": _validation_message(exc)})

    app.include_router(auth.router)
    app.include_router(chat.router)
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
