from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    llm_model: str = Field(default="gemini-2.5-flash-lite")
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    # Telegram
    telegram_bot_token: str = Field(default="")
    webhook_base_url: str = Field(default="")

    # Google Sheets
    google_service_account_json: str = Field(default="")
    google_sheet_id: str = Field(default="")

    # ChromaDB
    chroma_db_path: str = Field(default="./chroma_db")
    chroma_collection_name: str = Field(default="techgear_knowledge_base")

    # Embedding
    embedding_provider: Literal["gemini", "sentence-transformers"] = Field(
        default="sentence-transformers"
    )
    embedding_model: str = Field(default="paraphrase-multilingual-mpnet-base-v2")

    # RAG
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_score_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    # LangSmith
    langsmith_tracing: bool = Field(default=False)
    langsmith_api_key: str = Field(default="")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com")
    langsmith_project: str = Field(default="techgear-agent")

    # App
    app_env: Literal["development", "production"] = Field(default="development")
    log_level: str = Field(default="INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
