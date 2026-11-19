from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import LLMError
from app.main import create_app
from app.schemas import Message

ACCESS_KEY = "test-key_123"


class FakeLLM:
    def __init__(self) -> None:
        self.fail_with: str | None = None
        self.calls: list[tuple[list[Message], str]] = []

    def generate(self, history: list[Message], text: str) -> str:
        self.calls.append((history, text))
        if self.fail_with:
            raise LLMError(self.fail_with)
        return f"Ответ на: {text}"


def make_settings(db_path: Path) -> Settings:
    return Settings(access_key=ACCESS_KEY, database_path=db_path, login_max_attempts=3)


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "chat.sqlite3"


@pytest.fixture
def client(db_path: Path, llm: FakeLLM):
    with TestClient(create_app(make_settings(db_path), llm)) as c:
        yield c


@pytest.fixture
def authed(client: TestClient) -> TestClient:
    assert client.post("/api/auth/login", json={"access_key": ACCESS_KEY}).status_code == 204
    return client




def test_chat_requires_session(client: TestClient) -> None:
    assert client.get("/api/chat/messages").status_code == 401
    assert client.post("/api/chat/messages", json={"text": "hi"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("key", ["short", "a" * 256, "bad key with spaces", "ключ-на-русском"])
def test_login_rejects_malformed_key(client: TestClient, key: str) -> None:
    response = client.post("/api/auth/login", json={"access_key": key})
    assert response.status_code == 422
    assert "Ключ" in response.json()["detail"]


def test_login_wrong_key(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"access_key": "wrong-key-123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный ключ доступа"
    assert "chat_session" not in response.cookies


def test_login_sets_httponly_cookie(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"access_key": ACCESS_KEY})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert ACCESS_KEY.lower() not in cookie
    assert client.get("/api/auth/me").status_code == 204


def test_logout_invalidates_session(authed: TestClient) -> None:
    token = authed.cookies.get("chat_session")
    assert authed.post("/api/auth/logout").status_code == 204
    authed.cookies.set("chat_session", token)
    assert authed.get("/api/chat/messages").status_code == 401


def test_login_rate_limit(client: TestClient) -> None:
    for _ in range(3):
        client.post("/api/auth/login", json={"access_key": "wrong-key-123"})
    response = client.post("/api/auth/login", json={"access_key": ACCESS_KEY})
    assert response.status_code == 429




@pytest.mark.parametrize("text", ["", "   \n\t ", "x" * 501])
def test_send_rejects_invalid_text(authed: TestClient, llm: FakeLLM, text: str) -> None:
    assert authed.post("/api/chat/messages", json={"text": text}).status_code == 422
    assert llm.calls == []


def test_send_and_history(authed: TestClient, llm: FakeLLM) -> None:
    response = authed.post("/api/chat/messages", json={"text": "  Борщ  "})
    assert response.status_code == 200
    body = response.json()
    assert body["user_message"]["content"] == "Борщ"
    assert body["assistant_message"]["content"] == "Ответ на: Борщ"

    authed.post("/api/chat/messages", json={"text": "Плов"})
    history = authed.get("/api/chat/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert all(m["created_at"] for m in history)
    assert [m.content for m in llm.calls[1][0]] == ["Борщ", "Ответ на: Борщ"]


def test_llm_error_is_reported_and_not_saved(authed: TestClient, llm: FakeLLM) -> None:
    llm.fail_with = "Модель недоступна"
    response = authed.post("/api/chat/messages", json={"text": "Суп"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Модель недоступна"
    assert authed.get("/api/chat/messages").json() == []


def test_clear_history(authed: TestClient) -> None:
    authed.post("/api/chat/messages", json={"text": "Салат"})
    assert authed.delete("/api/chat/messages").status_code == 204
    assert authed.get("/api/chat/messages").json() == []


def test_history_and_session_survive_restart(db_path: Path, llm: FakeLLM) -> None:
    with TestClient(create_app(make_settings(db_path), llm)) as first:
        first.post("/api/auth/login", json={"access_key": ACCESS_KEY})
        first.post("/api/chat/messages", json={"text": "Омлет"})
        token = first.cookies.get("chat_session")

    with TestClient(create_app(make_settings(db_path), llm)) as second:
        second.cookies.set("chat_session", token)
        history = second.get("/api/chat/messages").json()
        assert [m["content"] for m in history] == ["Омлет", "Ответ на: Омлет"]


def test_index_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Шеф" in response.text
