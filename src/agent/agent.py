from __future__ import annotations

import logging
from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools.order_tool import create_order
from src.agent.tools.rag_tool import search_product_knowledge
from src.config import get_settings

logger = logging.getLogger(__name__)

TOOLS = [search_product_knowledge, create_order]


# ── State definition ──────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ── LLM & Tool Node ───────────────────────────────────────────────────────────

def _build_llm() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        google_api_key=settings.gemini_api_key,
    ).bind_tools(TOOLS)


def _llm_node(state: AgentState) -> dict[str, Any]:
    """Call the LLM with the current conversation history."""
    llm = _build_llm()
    # Prepend system prompt if not already present
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    response: AIMessage = llm.invoke(messages)
    logger.debug("LLM response: tool_calls=%d", len(response.tool_calls or []))
    return {"messages": [response]}


def _should_continue(state: AgentState) -> str:
    """Route to tool execution or end based on whether the LLM called a tool."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


# ── Graph construction ────────────────────────────────────────────────────────

def _build_graph() -> Any:
    tool_node = ToolNode(TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")  # After tool execution, feed results back to LLM

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# Singleton compiled graph
_graph = None


def get_graph() -> Any:
    global _graph
    if _graph is None:
        _graph = _build_graph()
        logger.info("LangGraph agent compiled and ready.")
    return _graph


# ── Public interface ──────────────────────────────────────────────────────────

def invoke_agent(user_message: str, session_id: str) -> str:
    """Process a user message and return the agent's text response.

    Args:
        user_message: The raw text message from the user.
        session_id: Unique identifier for the conversation session
                    (e.g., Telegram chat_id as string).

    Returns:
        The agent's response as a plain string.
    """
    from langchain_core.messages import HumanMessage

    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    result = graph.invoke(
        {"messages": [HumanMessage(content=user_message)]},
        config=config,
    )

    last_message = result["messages"][-1]

    # Extract text content, skipping any ToolMessage at the end
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not isinstance(msg, ToolMessage):
            content = msg.content
            if isinstance(content, list):
                # Handle multi-part content (text + tool_use blocks)
                text_parts = [p["text"] for p in content if isinstance(p, dict) and p.get("type") == "text"]
                return "\n".join(text_parts) if text_parts else ""
            return str(content)

    return str(last_message.content)
