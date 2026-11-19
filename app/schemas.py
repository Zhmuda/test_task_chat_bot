from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config import ACCESS_KEY_PATTERN

Role = Literal["user", "assistant"]

MESSAGE_MAX_LENGTH = 500


class LoginRequest(BaseModel):
    access_key: str = Field(pattern=ACCESS_KEY_PATTERN)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MESSAGE_MAX_LENGTH)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Сообщение не может быть пустым")
        return value


class Message(BaseModel):
    id: int
    role: Role
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    user_message: Message
    assistant_message: Message


class ErrorResponse(BaseModel):
    detail: str
