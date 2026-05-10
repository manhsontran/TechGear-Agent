"""Unit tests for agent tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.tools.order_tool import _validate_phone, create_order
from src.agent.tools.rag_tool import search_product_knowledge


# ── Phone validation ──────────────────────────────────────────────────────────

class TestPhoneValidation:
    @pytest.mark.parametrize("phone", [
        "0901234567",
        "0312345678",
        "0812345678",
        "+84901234567",
    ])
    def test_valid_phones(self, phone: str):
        assert _validate_phone(phone) is True

    @pytest.mark.parametrize("phone", [
        "12345",
        "090123456",       # too short
        "09012345678",     # too long
        "1901234567",      # doesn't start with 0 or +84
        "abcdefghij",
        "",
    ])
    def test_invalid_phones(self, phone: str):
        assert _validate_phone(phone) is False


# ── create_order tool ─────────────────────────────────────────────────────────

class TestCreateOrderTool:
    def test_invalid_phone_returns_error(self):
        result = create_order.invoke({
            "customer_name": "Test User",
            "phone_number": "123",
            "product": "MacBook Air",
        })
        assert "không hợp lệ" in result

    def test_valid_order_calls_append_order(self):
        with patch("src.agent.tools.order_tool.append_order") as mock_append:
            result = create_order.invoke({
                "customer_name": "Nguyễn Văn An",
                "phone_number": "0901234567",
                "product": "MacBook Air M3",
                "note": "Màu Midnight",
            })

        mock_append.assert_called_once_with(
            name="Nguyễn Văn An",
            phone="0901234567",
            product="MacBook Air M3",
            note="Màu Midnight",
        )
        assert "Đơn hàng đã được ghi nhận" in result
        assert "Nguyễn Văn An" in result

    def test_sheets_error_returns_fallback_message(self):
        with patch("src.agent.tools.order_tool.append_order", side_effect=Exception("Sheets error")):
            result = create_order.invoke({
                "customer_name": "Test",
                "phone_number": "0901234567",
                "product": "RTX 4070",
            })
        assert "lỗi" in result.lower()


# ── RAG tool ──────────────────────────────────────────────────────────────────

class TestRagTool:
    def test_returns_context_when_results_found(self):
        from src.rag.retriever import RetrievalResult
        from langchain_core.documents import Document

        mock_result = RetrievalResult(
            document=Document(page_content="MacBook Air M2 giá 27.990.000 ₫", metadata={"source": "macbook.md"}),
            score=0.9,
        )
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [mock_result]
        mock_retriever.format_context.return_value = "MacBook Air M2 giá 27.990.000 ₫"

        with patch("src.agent.tools.rag_tool.get_retriever", return_value=mock_retriever):
            result = search_product_knowledge.invoke({"query": "MacBook Air M2 giá bao nhiêu"})

        assert "MacBook Air M2" in result

    def test_returns_empty_string_when_no_results(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = []

        with patch("src.agent.tools.rag_tool.get_retriever", return_value=mock_retriever):
            result = search_product_knowledge.invoke({"query": "sản phẩm không tồn tại xyz"})

        assert result == ""
