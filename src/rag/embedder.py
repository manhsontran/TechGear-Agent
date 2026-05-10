from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src.config import get_settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def build_embeddings() -> Embeddings:
    """Build the embedding model based on config (Gemini or sentence-transformers)."""
    settings = get_settings()

    if settings.embedding_provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        logger.info("Using Gemini embeddings: %s", settings.embedding_model)
        return GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.gemini_api_key,
        )

    # Fallback: sentence-transformers (offline, Vietnamese-friendly)
    from langchain_community.embeddings import HuggingFaceEmbeddings

    logger.info("Using HuggingFace embeddings: %s", settings.embedding_model)
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vector_store(embeddings: Embeddings | None = None) -> Chroma:
    """Return a Chroma vector store connected to the persistent ChromaDB."""
    settings = get_settings()
    if embeddings is None:
        embeddings = build_embeddings()

    return Chroma(
        collection_name=settings.chroma_collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_db_path,
    )


def ingest_chunks(chunks: list[Document], embeddings: Embeddings | None = None) -> Chroma:
    """Embed *chunks* and upsert into ChromaDB. Returns the vector store."""
    settings = get_settings()
    if embeddings is None:
        embeddings = build_embeddings()

    logger.info(
        "Ingesting %d chunks into collection '%s' at '%s'",
        len(chunks),
        settings.chroma_collection_name,
        settings.chroma_db_path,
    )

    # Chroma.from_documents handles create-or-update automatically
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=settings.chroma_collection_name,
        persist_directory=settings.chroma_db_path,
    )
    logger.info("Ingestion complete. Collection size: %d", vector_store._collection.count())
    return vector_store


def reset_collection() -> None:
    """Drop and recreate the ChromaDB collection (use before full re-ingestion)."""
    settings = get_settings()
    client = chromadb.PersistentClient(path=settings.chroma_db_path)
    try:
        client.delete_collection(settings.chroma_collection_name)
        logger.info("Deleted existing collection '%s'", settings.chroma_collection_name)
    except Exception:
        logger.info("No existing collection to delete.")
