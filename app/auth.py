import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response, status

from app.config import Settings
from app.db import Database, utcnow
from app.dependencies import get_db, get_settings_dep


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_access_key(candidate: str, settings: Settings) -> bool:
    return hmac.compare_digest(candidate.encode(), settings.access_key.encode())


def start_session(response: Response, db: Database, settings: Settings) -> None:
    token = secrets.token_urlsafe(32)
    ttl = timedelta(hours=settings.session_ttl_hours)
    db.delete_expired_sessions()
    db.add_session(_hash_token(token), utcnow() + ttl)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def end_session(request: Request, response: Response, db: Database, settings: Settings) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        db.delete_session(_hash_token(token))
    response.delete_cookie(settings.session_cookie_name, path="/")


def require_session(
    request: Request,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token or not db.session_is_valid(_hash_token(token)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")


class LoginRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_id: str) -> None:
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[client_id]
            while attempts and now - attempts[0] > self._window:
                attempts.popleft()
            if len(attempts) >= self._max:
                retry_after = int(self._window - (now - attempts[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Слишком много попыток входа. Повторите через {retry_after} с",
                    headers={"Retry-After": str(retry_after)},
                )

    def register_failure(self, client_id: str) -> None:
        with self._lock:
            self._attempts[client_id].append(time.monotonic())

    def reset(self, client_id: str) -> None:
        with self._lock:
            self._attempts.pop(client_id, None)
