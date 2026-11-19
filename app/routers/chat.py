from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_session
from app.config import Settings
from app.db import Database
from app.dependencies import get_db, get_llm, get_settings_dep
from app.llm import LLMClient, LLMError
from app.schemas import ChatRequest, ChatResponse, Message

router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[Depends(require_session)])


@router.get("/messages", response_model=list[Message])
def list_messages(db: Database = Depends(get_db)) -> list[Message]:
    return db.list_messages()


@router.post("/messages", response_model=ChatResponse)
def send_message(
    body: ChatRequest,
    db: Database = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
    settings: Settings = Depends(get_settings_dep),
) -> ChatResponse:
    history = db.last_messages(settings.context_messages)
    try:
        answer = llm.generate(history, body.text)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    user_message = db.add_message("user", body.text)
    assistant_message = db.add_message("assistant", answer)
    return ChatResponse(user_message=user_message, assistant_message=assistant_message)


@router.delete("/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_messages(db: Database = Depends(get_db)) -> None:
    db.clear_messages()
