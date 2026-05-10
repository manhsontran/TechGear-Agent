"""Unit tests for the RAG pipeline (chunker, embedder, retriever)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from src.rag.chunker import chunk_documents, load_documents


# ── Chunker tests ─────────────────────────────────────────────────────────────

class TestChunker:
    def test_chunk_documents_splits_large_doc(self):
        long_text = "Thông số kỹ thuật.\n\n" * 100  # ~2000 chars, exceeds chunk_size=1000
        doc = Document(page_content=long_text, metadata={"source": "test.md"})
        chunks = chunk_documents([doc])
        assert len(chunks) > 1, "Long document should be split into multiple chunks"

    def test_chunk_documents_preserves_metadata(self):
        doc = Document(page_content="MacBook Air M2 giá 27.990.000 ₫", metadata={"source": "macbook.md"})
        chunks = chunk_documents([doc])
        assert all(c.metadata["source"] == "macbook.md" for c in chunks)

    def test_chunk_documents_short_doc_stays_intact(self):
        short_text = "MacBook Air M2 RAM 8GB"
        doc = Document(page_content=short_text, metadata={"source": "test.md"})
        chunks = chunk_documents([doc])
        assert len(chunks) == 1
        assert chunks[0].page_content == short_text

    def test_load_documents_raises_for_missing_dir(self, tmp_path):
        non_existent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            load_documents(non_existent)

    def test_load_documents_reads_markdown(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\nMacBook Air M2", encoding="utf-8")
        docs = load_documents(tmp_path)
        assert len(docs) == 1
        assert "MacBook Air M2" in docs[0].page_content


# ── Retriever tests ───────────────────────────────────────────────────────────

class TestRetriever:
    def test_retriever_filters_by_threshold(self):
        """Results below the score threshold should be excluded."""
        from src.rag.retriever import Retriever

        mock_store = MagicMock()
        mock_store.similarity_search_with_relevance_scores.return_value = [
            (Document(page_content="MacBook Air M2"), 0.85),
            (Document(page_content="Irrelevant text"), 0.10),
        ]

        with patch("src.rag.retriever.get_vector_store", return_value=mock_store):
            with patch("src.config.get_settings") as mock_settings:
                mock_settings.return_value.retrieval_top_k = 5
                mock_settings.return_value.retrieval_score_threshold = 0.3
                retriever = Retriever()
                retriever._store = mock_store
                retriever._threshold = 0.3

                results = retriever.retrieve("MacBook Air")

        assert len(results) == 1
        assert results[0].score == 0.85

    def test_format_context_empty(self):
        from src.rag.retriever import Retriever
        mock_store = MagicMock()
        with patch("src.rag.retriever.get_vector_store", return_value=mock_store):
            with patch("src.config.get_settings") as mock_settings:
                mock_settings.return_value.retrieval_top_k = 5
                mock_settings.return_value.retrieval_score_threshold = 0.3
                retriever = Retriever()
        context = retriever.format_context([])
        assert context == ""

    def test_format_context_includes_source(self):
        from src.rag.retriever import Retriever, RetrievalResult

        mock_store = MagicMock()
        with patch("src.rag.retriever.get_vector_store", return_value=mock_store):
            with patch("src.config.get_settings") as mock_settings:
                mock_settings.return_value.retrieval_top_k = 5
                mock_settings.return_value.retrieval_score_threshold = 0.3
                retriever = Retriever()

        doc = Document(page_content="MacBook Air M2 giá 27.990.000 ₫", metadata={"source": "macbook.md"})
        result = RetrievalResult(document=doc, score=0.92)
        context = retriever.format_context([result])

        assert "macbook.md" in context
        assert "MacBook Air M2" in context
        assert "0.92" in context
