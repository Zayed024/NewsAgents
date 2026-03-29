"""QueryResponder agent — handles follow-up questions with non-overlapping answers."""

import re

from src.llm import call_llm, parse_json_response, is_llm_unavailable_response
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
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.5,
        )

        try:
            data = parse_json_response(response)
            result = QueryResponse(**data)
        except Exception:
            result = _deterministic_query_answer(question, syntheses, articles)

        if is_llm_unavailable_response(result.answer):
            result = _deterministic_query_answer(question, syntheses, articles)

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
        model_used="pro",
        input_summary=f"Q: {question[:100]}",
        output_summary=f"A: {result.answer[:100]}... (angle: {result.angle})",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result


def _deterministic_query_answer(
    question: str,
    syntheses: list[SynthesisEntry],
    articles: list[Article],
) -> QueryResponse:
    q_tokens = _tokens(question)

    angle_scores: list[tuple[int, str]] = []
    for s in syntheses:
        hay = f"{s.angle_name} {s.synthesis} {' '.join(s.key_takeaways)}".lower()
        score = sum(1 for t in q_tokens if t in hay)
        angle_scores.append((score, s.angle_name))

    angle_scores.sort(key=lambda x: x[0], reverse=True)
    best_angle = angle_scores[0][1] if angle_scores else "general"

    article_scored: list[tuple[int, Article]] = []
    for article in articles:
        hay = f"{article.title} {article.content}".lower()
        score = sum(1 for t in q_tokens if t in hay)
        if score > 0:
            article_scored.append((score, article))

    article_scored.sort(key=lambda x: x[0], reverse=True)
    selected_articles = [a for _, a in article_scored[:3]]
    if not selected_articles:
        selected_articles = articles[:2]

    evidence_lines = []
    for article in selected_articles:
        sent = _best_sentence_for_question(article.content, q_tokens)
        evidence_lines.append(f"{sent} [{article.id}]")

    answer = (
        f"Based on the available ET coverage, the most relevant lens is {best_angle}. "
        + " ".join(evidence_lines)
        + " Overall, the key implication depends on execution timelines, market absorption, and policy follow-through."
    )

    return QueryResponse(
        answer=answer,
        sources=[a.id for a in selected_articles],
        angle=best_angle,
        is_non_overlapping=True,
    )


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3]


def _best_sentence_for_question(content: str, q_tokens: list[str]) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content) if s.strip()]
    if not sentences:
        return content[:180]
    scored = []
    for s in sentences:
        lowered = s.lower()
        score = sum(1 for t in q_tokens if t in lowered)
        if re.search(r"\b\d+(?:\.\d+)?\b", s):
            score += 1
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    return best[:220] + ("..." if len(best) > 220 else "")
