"""Executable LangGraph graph for deterministic personalization."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, TypedDict, cast

from langgraph.graph import END, StateGraph
from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.embeddings import VECTOR_DIMENSION, generate_mock_embedding
from app.models.enums import HookType
from app.models.lead import Lead
from app.models.sender import SenderProfile
from app.models.signal import Signal
from app.models.snippet import WinningSnippet


NEGATIVE_KEYWORDS = (
    "hope this finds you well",
    "circle back",
    "synergy",
    "leverage",
    "touch base",
    "just checking in",
    "quick question",
)


@dataclass(frozen=True)
class CommonalityResult:
    """Strongest sender/lead commonality."""

    strongest_hook: str | None
    hook_type: str
    hook_strength: float


class PersonalizationState(TypedDict, total=False):
    """State passed through the personalization graph."""

    db: AsyncSession
    lead: Lead
    signal_id: uuid.UUID | None
    sender: SenderProfile | None
    candidate_signals: list[Signal]
    selected_signal: Signal | None
    commonality: CommonalityResult
    retrieved_snippets: list[WinningSnippet]
    draft_output: dict[str, str]
    critique_score: float
    critique_breakdown: dict[str, float]
    rewrite_note: str | None
    iterations: int


_COMPILED_GRAPH = None


def build_personalization_graph():
    """Build and cache the executable PRD personalization graph."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is not None:
        return _COMPILED_GRAPH

    graph = StateGraph(PersonalizationState)
    graph.add_node("1_load_context", _load_context)
    graph.add_node("1_5_commonality_matcher", _commonality_matcher)
    graph.add_node("2_signal_selector", _signal_selector)
    graph.add_node("3_rag_retrieval", _rag_retrieval)
    graph.add_node("4_draft_writer", _draft_writer)
    graph.add_node("5_critique_rewrite", _critique_rewrite)
    graph.add_node("6_tone_adapter", _tone_adapter)

    graph.set_entry_point("1_load_context")
    graph.add_edge("1_load_context", "1_5_commonality_matcher")
    graph.add_edge("1_5_commonality_matcher", "2_signal_selector")
    graph.add_edge("2_signal_selector", "3_rag_retrieval")
    graph.add_edge("3_rag_retrieval", "4_draft_writer")
    graph.add_edge("4_draft_writer", "5_critique_rewrite")
    graph.add_conditional_edges(
        "5_critique_rewrite",
        _should_rewrite,
        {"rewrite": "4_draft_writer", "done": "6_tone_adapter"},
    )
    graph.add_edge("6_tone_adapter", END)
    _COMPILED_GRAPH = graph.compile()
    return _COMPILED_GRAPH


async def seed_winning_snippets(db: AsyncSession) -> int:
    """Seed deterministic snippet fixtures if none exist."""
    existing = await db.execute(select(WinningSnippet.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return 0

    fixtures = [
        {
            "title": "Funding trigger",
            "subject_line": "Pipeline after the raise",
            "body": (
                "Congrats on the recent raise. Teams usually revisit "
                "pipeline coverage right after funding closes."
            ),
            "industry": "SaaS",
            "persona": "Founder",
            "hook_type": HookType.SIGNAL.value,
            "role_seniority": "Executive",
            "channel": "EMAIL",
            "reply_rate": 0.31,
        },
        {
            "title": "Hiring trigger",
            "subject_line": "GTM hiring signal",
            "body": (
                "Your open GTM roles suggest demand is outpacing the "
                "current outbound motion."
            ),
            "industry": "B2B Software",
            "persona": "Revenue",
            "hook_type": HookType.SIGNAL.value,
            "role_seniority": "Director",
            "channel": "EMAIL",
            "reply_rate": 0.27,
        },
        {
            "title": "Technical peer hook",
            "subject_line": "Same GTM stack pattern",
            "body": (
                "I noticed your team ships with a similar Python and "
                "TypeScript stack, so I kept this concrete."
            ),
            "industry": "Developer Tools",
            "persona": "Engineering",
            "hook_type": HookType.COMMONALITY.value,
            "role_seniority": "Manager",
            "channel": "LINKEDIN_MESSAGE",
            "reply_rate": 0.24,
        },
    ]
    for fixture in fixtures:
        db.add(
            WinningSnippet(
                **fixture,
                embedding=generate_mock_embedding(
                    f"{fixture['subject_line']}. {fixture['body']}",
                ),
            ),
        )
    await db.flush()
    return len(fixtures)


async def run_personalization_graph(
    db: AsyncSession,
    lead: Lead,
    signal_id: uuid.UUID | None = None,
) -> PersonalizationState:
    """Run the compiled personalization graph and return final state."""
    graph = build_personalization_graph()
    state = await graph.ainvoke(
        PersonalizationState(db=db, lead=lead, signal_id=signal_id),
    )
    return cast(PersonalizationState, state)


async def _load_context(state: PersonalizationState) -> dict[str, Any]:
    db = state["db"]
    lead = state["lead"]
    sender_result = await db.execute(select(SenderProfile).limit(1))
    signal_result = await db.execute(
        select(Signal)
        .where(Signal.lead_id == lead.id)
        .where(Signal.is_read.is_(False))
        .order_by(Signal.signal_strength.desc().nullslast())
        .limit(5),
    )
    await seed_winning_snippets(db)
    return {
        "sender": sender_result.scalars().first(),
        "candidate_signals": list(signal_result.scalars().all()),
        "iterations": state.get("iterations", 0),
    }


async def _commonality_matcher(state: PersonalizationState) -> dict[str, Any]:
    return {"commonality": match_commonality(state.get("sender"), state["lead"])}


async def _signal_selector(state: PersonalizationState) -> dict[str, Any]:
    db = state["db"]
    signal_id = state.get("signal_id")
    selected: Signal | None = None
    if signal_id is not None:
        selected = await db.get(Signal, signal_id)
    if selected is None:
        signals = state.get("candidate_signals") or []
        selected = signals[0] if signals else None
    return {"selected_signal": selected}


async def _rag_retrieval(state: PersonalizationState) -> dict[str, Any]:
    db = state["db"]
    lead = state["lead"]
    signal = state.get("selected_signal")
    commonality = state.get("commonality") or CommonalityResult(
        None,
        HookType.NONE.value,
        0.0,
    )
    query_text = " ".join(
        [
            commonality.strongest_hook or "",
            lead.industry or "",
            lead.title or "",
            signal.signal_title if signal else "",
        ],
    )
    embedding_param = bindparam(
        "query_embedding",
        value=generate_mock_embedding(query_text),
        type_=Vector(VECTOR_DIMENSION),
    )
    result = await db.execute(
        select(WinningSnippet)
        .where(WinningSnippet.embedding.isnot(None))
        .order_by(WinningSnippet.embedding.cosine_distance(embedding_param))
        .limit(3),
    )
    return {"retrieved_snippets": list(result.scalars().all())}


async def _draft_writer(state: PersonalizationState) -> dict[str, Any]:
    output = compose_output(
        lead=state["lead"],
        commonality=state.get("commonality")
        or CommonalityResult(None, HookType.NONE.value, 0.0),
        signal=state.get("selected_signal"),
        snippets=state.get("retrieved_snippets") or [],
        rewrite_note=state.get("rewrite_note"),
    )
    return {
        "draft_output": output,
        "iterations": (state.get("iterations") or 0) + 1,
    }


async def _critique_rewrite(state: PersonalizationState) -> dict[str, Any]:
    score, breakdown = critique_output(state["draft_output"], state["lead"])
    rewrite_note = None
    if (
        score < settings.CRITIQUE_REWRITE_THRESHOLD
        and (state.get("iterations") or 0) < 3
    ):
        rewrite_note = (
            "Make the message more specific, preserve one clear CTA, "
            "and remove generic sales phrasing."
        )
    return {
        "critique_score": score,
        "critique_breakdown": breakdown,
        "rewrite_note": rewrite_note,
    }


async def _tone_adapter(state: PersonalizationState) -> dict[str, Any]:
    output = dict(state["draft_output"])
    lead = state["lead"]
    mode = _tone_mode(lead)
    if mode == "formal":
        output["email_body"] = output["email_body"].replace(
            "Worth comparing notes",
            "Would it be useful to compare notes",
        )
        output["linkedin_message"] = output["linkedin_message"].replace(
            "Worth comparing notes",
            "Would it be useful to compare notes",
        )
    elif mode == "direct":
        output["email_body"] = output["email_body"].replace(
            "Would it be useful to compare notes",
            "Worth comparing notes",
        )
    output["email_body"] = enforce_negative_keywords(output["email_body"])
    output["linkedin_message"] = enforce_negative_keywords(
        output["linkedin_message"],
    )
    return {"draft_output": output}


def _should_rewrite(state: PersonalizationState) -> str:
    if (
        state.get("critique_score", 0) < settings.CRITIQUE_REWRITE_THRESHOLD
        and (state.get("iterations") or 0) < 3
    ):
        return "rewrite"
    return "done"


def match_commonality(
    sender: SenderProfile | None,
    lead: Lead,
) -> CommonalityResult:
    """Find strict commonality JSON-equivalent from sender profile."""
    if sender is None:
        return CommonalityResult(None, HookType.NONE.value, 0.0)

    enriched = lead.enriched_data or {}
    linkedin = enriched.get("linkedin", {})
    education = linkedin.get("education", [])
    universities = {
        str(item.get("university")).lower()
        for item in education
        if item.get("university")
    }
    sender_education = {item.lower() for item in sender.education or []}
    overlap = universities & sender_education
    if overlap:
        school = sorted(overlap)[0]
        return CommonalityResult(
            f"We both have a connection to {school.title()}.",
            HookType.COMMONALITY.value,
            0.92,
        )

    sender_employers = {item.lower() for item in sender.past_employers or []}
    past_companies = {
        str(item).lower()
        for item in linkedin.get("past_companies", [])
    }
    overlap = sender_employers & past_companies
    if overlap:
        company = sorted(overlap)[0]
        return CommonalityResult(
            f"We have both crossed paths with {company.title()}.",
            HookType.COMMONALITY.value,
            0.86,
        )

    return CommonalityResult(None, HookType.NONE.value, 0.0)


def compose_output(
    lead: Lead,
    commonality: CommonalityResult,
    signal: Signal | None,
    snippets: list[WinningSnippet],
    rewrite_note: str | None = None,
) -> dict[str, str]:
    """Compose a short, concrete outbound draft from graph state."""
    name = lead.first_name or "there"
    company = lead.company_name or lead.company_domain or "your team"
    hook = commonality.strongest_hook
    if hook is None and signal is not None:
        hook = signal.signal_title
    if hook is None:
        hook = f"I was looking at {company}'s current GTM motion"

    snippet = snippets[0].body if snippets else (
        "Teams usually benefit from a tighter account-priority loop "
        "when buying signals start moving."
    )
    cta = "Worth comparing notes for 15 minutes?"
    if rewrite_note:
        cta = "Worth a focused 15-minute account review?"

    body = (
        f"Hi {name},\n\n"
        f"{hook} {snippet}\n\n"
        "Orion helps prioritize accounts, explain why now, and draft "
        f"outreach around the signal behind {company}.\n\n"
        f"{cta}"
    )
    linkedin = (
        f"Hi {name}, noticed {hook.lower()} Orion turns that account "
        "signal into precise outbound. Worth comparing notes?"
    )
    subject = snippets[0].subject_line if snippets and snippets[0].subject_line else (
        f"Signal around {company}"
    )
    return {
        "subject_line": enforce_negative_keywords(subject),
        "email_body": enforce_negative_keywords(_trim_words(body, 75)),
        "linkedin_message": enforce_negative_keywords(_trim_words(linkedin, 50)),
    }


def critique_output(
    output: dict[str, str],
    lead: Lead,
) -> tuple[float, dict[str, float]]:
    """Score PRD's five quality dimensions on a 0-10 scale."""
    body = output["email_body"]
    body_lower = body.lower()
    company = (lead.company_name or lead.company_domain or "").lower()
    subject_words = output["subject_line"].split()
    contains_negative = any(item in body_lower for item in NEGATIVE_KEYWORDS)
    breakdown = {
        "specificity": 9.0 if company and company in body_lower else 7.0,
        "relevance": 9.0 if "signal" in body_lower else 6.5,
        "tone": 8.5 if not contains_negative and len(body.split()) <= 90 else 6.0,
        "cta_clarity": 9.0 if "15" in body and "?" in body else 6.0,
        "subject_line": 8.5 if 2 <= len(subject_words) <= 8 else 6.0,
    }
    score = round(sum(breakdown.values()) / len(breakdown), 2)
    return min(score, 10.0), breakdown


def enforce_negative_keywords(text: str) -> str:
    """Remove generic outbound cliches before critique/persistence."""
    sanitized = text
    for phrase in NEGATIVE_KEYWORDS:
        sanitized = re.sub(
            rf"\b{re.escape(phrase)}\b[,.!?;:\s]*",
            "",
            sanitized,
            flags=re.IGNORECASE,
        )
    return re.sub(r"\s{2,}", " ", sanitized).strip()


def _trim_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(".,;:") + "."


def _tone_mode(lead: Lead) -> str:
    title = (lead.title or "").lower()
    industry = (lead.industry or "").lower()
    formal_titles = ("ceo", "cfo", "cto", "founder", "vp", "chief")
    formal_industries = ("finance", "fintech", "legal", "government")
    if any(item in title for item in formal_titles) or any(
        item in industry for item in formal_industries
    ):
        return "formal"
    direct_industries = ("developer", "software", "saas", "security")
    if any(item in industry for item in direct_industries):
        return "direct"
    return "neutral"
