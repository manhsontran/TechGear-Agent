from __future__ import annotations

from pydantic import BaseModel, Field


# ── REST Chat ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096, description="User message text")
    session_id: str = Field(
        default="default",
        max_length=128,
        description="Unique session/conversation identifier",
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Agent response text")
    session_id: str = Field(..., description="Echo of the session_id")


# ── Telegram Webhook ──────────────────────────────────────────────────────────

class TelegramUser(BaseModel):
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""


class TelegramChat(BaseModel):
    id: int
    type: str = "private"


class TelegramMessage(BaseModel):
    message_id: int
    text: str = ""
    chat: TelegramChat
    from_: TelegramUser | None = Field(default=None, alias="from")

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None
