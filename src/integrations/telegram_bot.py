from __future__ import annotations

import logging

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _api_url(method: str) -> str:
    token = get_settings().telegram_bot_token
    return TELEGRAM_API_BASE.format(token=token, method=method)


async def send_message(chat_id: int | str, text: str) -> None:
    """Send a text message to a Telegram chat.

    Tries with Markdown parse_mode first; if Telegram rejects the formatting
    (e.g. unbalanced entities from LLM output), retries as plain text.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _api_url("sendMessage"),
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )
        if response.status_code == 400:
            # Markdown parse error — retry without formatting
            logger.warning(
                "sendMessage Markdown parse failed, retrying as plain text. "
                "Error: %s",
                response.text,
            )
            response = await client.post(
                _api_url("sendMessage"),
                json={"chat_id": chat_id, "text": text},
            )

        if response.status_code != 200:
            logger.error(
                "Telegram sendMessage failed [%d]: %s",
                response.status_code,
                response.text,
            )
        else:
            logger.debug("Message sent to chat_id=%s", chat_id)


async def send_typing_action(chat_id: int | str) -> None:
    """Show 'typing...' indicator in the chat while the agent processes."""
    payload = {"chat_id": chat_id, "action": "typing"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(_api_url("sendChatAction"), json=payload)


async def set_webhook(webhook_url: str) -> dict:
    """Register the webhook URL with Telegram."""
    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(_api_url("setWebhook"), json=payload)
        data = response.json()
        if data.get("ok"):
            logger.info("Telegram webhook set to: %s", webhook_url)
        else:
            logger.error("Failed to set Telegram webhook: %s", data)
        return data


async def delete_webhook() -> dict:
    """Remove the current webhook (useful for switching to polling)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(_api_url("deleteWebhook"))
        return response.json()


async def get_webhook_info() -> dict:
    """Get current webhook registration info from Telegram."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(_api_url("getWebhookInfo"))
        return response.json()
