import logging
from typing import Protocol

import httpx

from app.config import Settings
from app.schemas import Message

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — «Шеф», дружелюбный кулинарный ассистент. Твоя тема — только кулинария: \
рецепты, блюда из имеющихся продуктов, техники приготовления, замены ингредиентов, \
меню, хранение продуктов, кухонная утварь.

Правила:
- Отвечай на языке пользователя, по умолчанию — по-русски.
- Пиши кратко и по делу. Рецепты оформляй списком ингредиентов с граммовками \
и пронумерованными шагами, указывай примерное время приготовления.
- Если пользователь перечисляет продукты — предложи 1–3 блюда из них, \
отметь, чего может не хватать.
- Если вопрос не про еду и кулинарию, вежливо откажись одной фразой \
и предложи вернуться к кухонной теме.
- Не давай медицинских рекомендаций; при вопросах об аллергиях и диетах \
советуй проконсультироваться со специалистом.
"""

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(Exception):
    pass


class LLMClient(Protocol):
    def generate(self, history: list[Message], text: str) -> str: ...


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.gemini_api_key
        self._url = GEMINI_URL.format(model=settings.gemini_model)
        self._http = httpx.Client(
            timeout=settings.gemini_timeout_seconds,
            proxy=settings.gemini_proxy,
        )

    def close(self) -> None:
        self._http.close()

    def generate(self, history: list[Message], text: str) -> str:
        if not self._api_key:
            raise LLMError("Сервер не настроен: не задан GEMINI_API_KEY")

        contents = [
            {"role": "user" if m.role == "user" else "model", "parts": [{"text": m.content}]}
            for m in history
        ]
        contents.append({"role": "user", "parts": [{"text": text}]})
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
        }

        try:
            response = self._http.post(
                self._url, json=payload, headers={"x-goog-api-key": self._api_key}
            )
        except httpx.TimeoutException as exc:
            raise LLMError("Модель не ответила вовремя, попробуйте ещё раз") from exc
        except httpx.HTTPError as exc:
            logger.warning("Gemini request failed: %r", exc)
            raise LLMError("Не удалось связаться с моделью") from exc

        if response.status_code == 429:
            raise LLMError("Превышен лимит запросов к модели, подождите немного")
        if response.status_code >= 400:
            logger.warning("Gemini error %s: %s", response.status_code, response.text[:500])
            raise LLMError(f"Модель вернула ошибку ({response.status_code})")

        return self._extract_text(response.json())

    @staticmethod
    def _extract_text(data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError("Модель отклонила запрос, попробуйте переформулировать")
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise LLMError("Модель вернула пустой ответ, попробуйте переформулировать")
        return text
