from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth import (
    LoginRateLimiter,
    check_access_key,
    end_session,
    require_session,
    start_session,
)
from app.config import Settings
from app.db import Database
from app.dependencies import get_db, get_rate_limiter, get_settings_dep
from app.schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
    limiter: LoginRateLimiter = Depends(get_rate_limiter),
) -> None:
    client_id = request.client.host if request.client else "unknown"
    limiter.check(client_id)
    if not check_access_key(body.access_key, settings):
        limiter.register_failure(client_id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный ключ доступа")
    limiter.reset(client_id)
    start_session(response, db, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    end_session(request, response, db, settings)


@router.get("/me", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_session)])
def me() -> None:
    pass
