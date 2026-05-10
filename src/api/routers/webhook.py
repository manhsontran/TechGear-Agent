from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Request, Response

from src.agent.agent import invoke_agent
from src.api.schemas import TelegramUpdate
from src.config import get_settings
from src.integrations.telegram_bot import (
    delete_webhook,
    get_webhook_info,
    send_message,
    send_typing_action,
    set_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])

# Simple in-memory rate limiter: {chat_id: [timestamps]}
_rate_limit_store: dict[int, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 10  # max requests
RATE_LIMIT_WINDOW = 60  # per N seconds


def _is_rate_limited(chat_id: int) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    timestamps = _rate_limit_store[chat_id]
    # Remove timestamps outside the window
    _rate_limit_store[chat_id] = [t for t in timestamps if t > window_start]
    if len(_rate_limit_store[chat_id]) >= RATE_LIMIT_MAX:
        return True
    _rate_limit_store[chat_id].append(now)
    return False


@router.post("/telegram", summary="Telegram webhook receiver")
async def telegram_webhook(request: Request) -> Response:
    """Receive Telegram updates, process through the agent, and send reply."""
    try:
        body = await request.json()
        update = TelegramUpdate.model_validate(body)
    except Exception as exc:
        logger.warning("Invalid Telegram update payload: %s", exc)
        # Always return 200 to Telegram to avoid repeated retries
        return Response(status_code=200)

    if update.message is None or not update.message.text:
        return Response(status_code=200)

    chat_id = update.message.chat.id
    user_text = update.message.text.strip()

    logger.info("Telegram message — chat_id=%d, text='%s'", chat_id, user_text[:80])

    if _is_rate_limited(chat_id):
        logger.warning("Rate limit exceeded for chat_id=%d", chat_id)
        await send_message(
            chat_id,
            "⚠️ Bạn đang gửi tin nhắn quá nhanh. Vui lòng thử lại sau ít giây.",
        )
        return Response(status_code=200)

    # Show typing indicator while processing
    await send_typing_action(chat_id)

    try:
        reply = invoke_agent(
            user_message=user_text,
            session_id=str(chat_id),
        )
    except Exception as exc:
        logger.exception("Agent error for chat_id=%d: %s", chat_id, exc)
        reply = (
            "❌ Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn. "
            "Vui lòng thử lại hoặc liên hệ hotline **1800-TECHGEAR**."
        )

    await send_message(chat_id, reply)
    return Response(status_code=200)


# ── Webhook management ────────────────────────────────────────────────────────

@router.get("/telegram/info", summary="Get Telegram webhook status")
async def telegram_webhook_info() -> dict:
    """Return current webhook registration info from Telegram API."""
    return await get_webhook_info()


@router.post("/telegram/refresh", summary="Re-register Telegram webhook")
async def telegram_webhook_refresh() -> dict:
    """Re-register webhook URL without restarting the server.

    Useful after changing WEBHOOK_BASE_URL (e.g., new ngrok URL).
    """
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.webhook_base_url:
        return {
            "ok": False,
            "description": "TELEGRAM_BOT_TOKEN or WEBHOOK_BASE_URL not configured in .env",
        }
    webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook/telegram"
    return await set_webhook(webhook_url)


@router.delete("/telegram", summary="Delete Telegram webhook")
async def telegram_webhook_delete() -> dict:
    """Unregister the webhook (switches bot to polling mode)."""
    return await delete_webhook()
