"""Integration tests for the FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture(scope="module")
def client():
    """Create a TestClient with agent and ChromaDB mocked out."""
    with patch("src.api.main.get_graph"):  # skip LangGraph init
        with patch("src.api.main.set_webhook"):  # skip Telegram webhook
            app = create_app()
            with TestClient(app) as c:
                yield c


# ── Health check ──────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ── Chat endpoint ─────────────────────────────────────────────────────────────

class TestChatEndpoint:
    def test_chat_returns_reply(self, client: TestClient):
        with patch("src.api.routers.chat.invoke_agent", return_value="Xin chào! Tôi là TechBot."):
            response = client.post("/chat", json={"message": "Xin chào", "session_id": "test_001"})

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Xin chào! Tôi là TechBot."
        assert data["session_id"] == "test_001"

    def test_chat_empty_message_returns_422(self, client: TestClient):
        response = client.post("/chat", json={"message": "", "session_id": "test"})
        assert response.status_code == 422

    def test_chat_missing_message_returns_422(self, client: TestClient):
        response = client.post("/chat", json={"session_id": "test"})
        assert response.status_code == 422


# ── Telegram webhook ──────────────────────────────────────────────────────────

class TestTelegramWebhook:
    def _make_update(self, text: str = "Hello", chat_id: int = 123456) -> dict:
        return {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "text": text,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": chat_id, "first_name": "Test"},
            },
        }

    def test_webhook_processes_message(self, client: TestClient):
        with patch("src.api.routers.webhook.invoke_agent", return_value="MacBook giá 28 triệu"):
            with patch("src.api.routers.webhook.send_typing_action", new_callable=AsyncMock):
                with patch("src.api.routers.webhook.send_message", new_callable=AsyncMock) as mock_send:
                    response = client.post("/webhook/telegram", json=self._make_update("MacBook giá bao nhiêu"))

        assert response.status_code == 200
        mock_send.assert_called_once()

    def test_webhook_ignores_empty_text(self, client: TestClient):
        update = self._make_update(text="")
        response = client.post("/webhook/telegram", json=update)
        assert response.status_code == 200

    def test_webhook_handles_invalid_payload(self, client: TestClient):
        response = client.post("/webhook/telegram", json={"bad": "payload"})
        assert response.status_code == 200  # Always 200 to Telegram

    def test_webhook_rate_limit(self, client: TestClient):
        from src.api.routers.webhook import _rate_limit_store

        chat_id = 999999
        _rate_limit_store[chat_id] = []  # reset

        with patch("src.api.routers.webhook.invoke_agent", return_value="ok"):
            with patch("src.api.routers.webhook.send_typing_action", new_callable=AsyncMock):
                with patch("src.api.routers.webhook.send_message", new_callable=AsyncMock):
                    # First 10 requests should go through
                    for _ in range(10):
                        response = client.post(
                            "/webhook/telegram", json=self._make_update(chat_id=chat_id)
                        )
                        assert response.status_code == 200

                    # 11th request should be rate limited
                    with patch("src.api.routers.webhook.send_message", new_callable=AsyncMock) as mock_send:
                        response = client.post(
                            "/webhook/telegram", json=self._make_update(chat_id=chat_id)
                        )
                    assert response.status_code == 200
                    # Rate limit message should be sent
                    mock_send.assert_called_once()
                    assert "quá nhanh" in mock_send.call_args[0][1]
