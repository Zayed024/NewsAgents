"""QueryResponder agent — handles follow-up questions with non-overlapping answers."""

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_PRO
from src.audit import log_agent_step, AuditTimer
from src.models import SynthesisEntry, Article, QueryResponse


SYSTEM_INSTRUCTION = """You are an interactive news briefing assistant for Economic Times.
Users have already read angle-based syntheses of the Union Budget 2026 coverage.
When they ask follow-up questions, you must:

1. Identify which angle(s) are most relevant to the question
2. Provide a SPECIFIC, DATA-BACKED answer using the original articles
3. CRITICAL: Your answer MUST NOT repeat information already provided in previous answers or the angle syntheses
4. Cite sources using [Article ID] notation
5. If the question spans multiple angles, connect insights across them
6. Be concise but information-dense — every sentence should carry new information"""


# In-memory query history per session
_query_history: dict[str, list[dict]] = {}


def get_query_history(session_id: str) -> list[dict]:
    """Get the query history for a session."""
    return _query_history.get(session_id, [])


def clear_query_history(session_id: str):
    """Clear query history for a session."""
    _query_history[session_id] = []


async def respond_to_query(
    question: str,
    syntheses: list[SynthesisEntry],
    articles: list[Article],
    session_id: str = "default",
) -> QueryResponse:
    """Answer a follow-up question with non-overlapping response.

    Args:
        question: The user's question
        syntheses: Previously generated angle syntheses
        articles: Original articles
        session_id: Session ID for audit trail and history tracking

    Returns:
        QueryResponse with answer, sources, and angle
    """
    with AuditTimer() as timer:
        # Build context of what the user has already seen
        history = _query_history.get(session_id, [])

        previous_answers = ""
        if history:
            previous_answers = "\n\nPREVIOUS ANSWERS (DO NOT REPEAT THIS INFORMATION):\n"
            for h in history:
                previous_answers += f"\nQ: {h['question']}\nA: {h['answer'][:300]}...\n"

        syntheses_context = "\n\nANGLE SYNTHESES ALREADY SHOWN TO USER:\n"
        for s in syntheses:
            syntheses_context += f"\n[{s.angle_name}]: {s.synthesis[:200]}...\n"

        # Build article reference
        articles_text = "\n\nFULL ARTICLES FOR REFERENCE:\n"
        for a in articles:
            articles_text += f"\n[{a.id}] {a.title}: {a.content[:300]}...\n"

        prompt = f"""User question: "{question}"

{syntheses_context}
{previous_answers}
{articles_text}

Answer the user's question. Return JSON:
{{
  "answer": "Your detailed answer (150-300 words). Cite articles as [budget-XXX]. Include specific numbers. DO NOT repeat any information from the syntheses or previous answers above.",
  "sources": ["budget-001", "budget-005"],
  "angle": "The most relevant angle name",
  "is_non_overlapping": true
}}"""

        response = await call_llm(
            prompt=prompt,
            model=GEMINI_PRO,
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.5,
        )

        try:
            data = parse_json_response(response)
            result = QueryResponse(**data)
        except Exception:
            result = QueryResponse(
                answer=response if response else "[Could not generate answer. Please try rephrasing your question.]",
                sources=[],
                angle="general",
                is_non_overlapping=True,
            )

        # Update history
        if session_id not in _query_history:
            _query_history[session_id] = []
        _query_history[session_id].append({
            "question": question,
            "answer": result.answer,
        })

    log_agent_step(
        agent_name="QueryResponder",
        action="respond_to_query",
        model_used=GEMINI_PRO,
        input_summary=f"Q: {question[:100]}",
        output_summary=f"A: {result.answer[:100]}... (angle: {result.angle})",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result
