from __future__ import annotations

import logging

from fastapi import APIRouter

from src.agent.agent import invoke_agent
from src.api.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, summary="Send a message to TechBot")
async def chat(request: ChatRequest) -> ChatResponse:
    """REST endpoint for direct interaction with the TechGear AI agent.

    Useful for testing without Telegram. Maintains conversation history per
    ``session_id`` using LangGraph's MemorySaver.
    """
    logger.info(
        "Chat request — session_id='%s', message='%s'",
        request.session_id,
        request.message[:80],
    )
    reply = invoke_agent(
        user_message=request.message,
        session_id=request.session_id,
    )
    return ChatResponse(reply=reply, session_id=request.session_id)
