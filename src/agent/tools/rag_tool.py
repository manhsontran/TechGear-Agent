from __future__ import annotations

import logging

from langchain_core.tools import tool

from src.rag.retriever import get_retriever

logger = logging.getLogger(__name__)


@tool
def search_product_knowledge(query: str) -> str:
    """Search the TechGear product knowledge base for technical specs, prices, and policies.

    Use this tool when the customer asks about:
    - Product specifications (CPU, RAM, GPU, display, battery, etc.)
    - Prices and available configurations
    - Warranty policies and duration
    - Return/exchange policies
    - Product comparisons or recommendations
    - Store information

    Args:
        query: The customer's question or search keywords in Vietnamese or English.

    Returns:
        Relevant product information retrieved from the knowledge base, or an empty
        string if nothing relevant is found.
    """
    retriever = get_retriever()
    results = retriever.retrieve(query)

    if not results:
        logger.debug("No results found for query: %s", query[:80])
        return ""

    context = retriever.format_context(results)
    logger.debug(
        "Retrieved %d chunks for query '%s'",
        len(results),
        query[:60],
    )
    return context
