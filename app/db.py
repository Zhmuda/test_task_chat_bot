import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import Message, Role

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role        TEXT    NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    expires_at  TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, path: Path) -> None:
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._tx() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._conn:
            yield self._conn

    def close(self) -> None:
        self._conn.close()

    def add_message(self, role: Role, content: str) -> Message:
        created_at = utcnow()
        with self._tx() as conn:
            cur = conn.execute(
                "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, created_at.isoformat()),
            )
        return Message(id=cur.lastrowid, role=role, content=content, created_at=created_at)

    def list_messages(self) -> list[Message]:
        with self._tx() as conn:
            rows = conn.execute("SELECT * FROM messages ORDER BY id").fetchall()
        return [self._to_message(row) for row in rows]

    def last_messages(self, limit: int) -> list[Message]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._to_message(row) for row in reversed(rows)]

    def clear_messages(self) -> None:
        with self._tx() as conn:
            conn.execute("DELETE FROM messages")

    @staticmethod
    def _to_message(row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def add_session(self, token_hash: str, expires_at: datetime) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO sessions (token_hash, expires_at) VALUES (?, ?)",
                (token_hash, expires_at.isoformat()),
            )

    def session_is_valid(self, token_hash: str) -> bool:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT expires_at FROM sessions WHERE token_hash = ?", (token_hash,)
            ).fetchone()
        return row is not None and datetime.fromisoformat(row["expires_at"]) > utcnow()

    def delete_session(self, token_hash: str) -> None:
        with self._tx() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def delete_expired_sessions(self) -> None:
        with self._tx() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (utcnow().isoformat(),))
