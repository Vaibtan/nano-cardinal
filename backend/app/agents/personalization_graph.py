"""LangGraph graph definition for the personalization agent.

The production draft generator in ``app.services.personalization`` uses
deterministic node implementations for local reliability.  This graph keeps
the node topology explicit so future LLM-backed nodes can be swapped in
without changing the API contract.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class PersonalizationState(TypedDict, total=False):
    """State passed through the personalization graph."""

    lead_id: str
    sender_profile: dict[str, Any] | None
    lead_context: dict[str, Any]
    commonality: dict[str, Any]
    retrieved_snippets: list[dict[str, Any]]
    draft: dict[str, str]
    critique: dict[str, Any]
    iterations: int


def build_personalization_graph():
    """Build the PRD node topology as a LangGraph StateGraph."""
    graph = StateGraph(PersonalizationState)
    graph.add_node("1_load_context", _identity_node)
    graph.add_node("1_5_commonality_matcher", _identity_node)
    graph.add_node("2_signal_selector", _identity_node)
    graph.add_node("3_rag_retrieval", _identity_node)
    graph.add_node("4_draft_writer", _identity_node)
    graph.add_node("5_critique_rewrite", _identity_node)
    graph.add_node("6_persist_publish", _identity_node)

    graph.set_entry_point("1_load_context")
    graph.add_edge("1_load_context", "1_5_commonality_matcher")
    graph.add_edge("1_5_commonality_matcher", "2_signal_selector")
    graph.add_edge("2_signal_selector", "3_rag_retrieval")
    graph.add_edge("3_rag_retrieval", "4_draft_writer")
    graph.add_edge("4_draft_writer", "5_critique_rewrite")
    graph.add_edge("5_critique_rewrite", "6_persist_publish")
    graph.add_edge("6_persist_publish", END)
    return graph.compile()


def _identity_node(state: PersonalizationState) -> PersonalizationState:
    """Return state unchanged; services own deterministic node behavior."""
    return state
