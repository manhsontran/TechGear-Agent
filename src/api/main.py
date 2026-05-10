from __future__ import annotations

import logging
import logging.config
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agent.agent import get_graph
from src.api.routers import chat, webhook
from src.config import get_settings
from src.integrations.telegram_bot import set_webhook

# ── Logging setup ─────────────────────────────────────────────────────────────

def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    _configure_logging(settings.log_level)

    logger = logging.getLogger("techgear.startup")
    logger.info("Starting TechGear Agent API (env=%s)...", settings.app_env)

    # Configure LangSmith tracing
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        logger.info("LangSmith tracing enabled (project='%s').", settings.langsmith_project)
    else:
        logger.info("LangSmith tracing disabled.")

    # Pre-warm the LangGraph agent (loads ChromaDB + embedding model)
    get_graph()
    logger.info("Agent graph initialized.")

    # Register Telegram webhook if configured
    if settings.telegram_bot_token and settings.webhook_base_url:
        webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook/telegram"
        try:
            await set_webhook(webhook_url)
        except Exception as exc:
            logging.getLogger("techgear.startup").warning(
                "Telegram webhook registration skipped: %s", exc
            )

    yield

    logger.info("Shutting down TechGear Agent API.")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="TechGear Agent API",
        description=(
            "AI-powered retail assistant for TechGear — "
            "Agentic RAG + Google Sheets CRM + Telegram integration"
        ),
        version="1.0.0",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url="/redoc" if settings.app_env == "development" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else [],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(chat.router)
    app.include_router(webhook.router)

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        return {"status": "ok", "service": "TechGear Agent API"}

    return app


app = create_app()
