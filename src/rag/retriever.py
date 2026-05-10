from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.documents import Document

from src.config import get_settings
from src.rag.embedder import get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    document: Document
    score: float

    @property
    def content(self) -> str:
        return self.document.page_content

    @property
    def source(self) -> str:
        return self.document.metadata.get("source", "unknown")


class Retriever:
    """Wraps ChromaDB similarity search with score filtering."""

    def __init__(self) -> None:
        settings = get_settings()
        self._top_k = settings.retrieval_top_k
        self._threshold = settings.retrieval_score_threshold
        self._store = get_vector_store()

    def retrieve(self, query: str) -> list[RetrievalResult]:
        """Return top-k documents above the score threshold for *query*."""
        results_with_scores = self._store.similarity_search_with_relevance_scores(
            query=query,
            k=self._top_k,
        )

        filtered: list[RetrievalResult] = []
        for doc, score in results_with_scores:
            if score >= self._threshold:
                filtered.append(RetrievalResult(document=doc, score=score))

        logger.debug(
            "Query '%s': retrieved %d/%d results above threshold %.2f",
            query[:60],
            len(filtered),
            len(results_with_scores),
            self._threshold,
        )
        return filtered

    def format_context(self, results: list[RetrievalResult]) -> str:
        """Format retrieved results into a single context string for the LLM."""
        if not results:
            return ""

        parts: list[str] = []
        for i, result in enumerate(results, start=1):
            parts.append(
                f"[Tài liệu {i}] (nguồn: {result.source}, độ liên quan: {result.score:.2f})\n"
                f"{result.content}"
            )
        return "\n\n---\n\n".join(parts)


_retriever_instance: Retriever | None = None


def get_retriever() -> Retriever:
    """Singleton retriever to avoid reloading the model on every request."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance
