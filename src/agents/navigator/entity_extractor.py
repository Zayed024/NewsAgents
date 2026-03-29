"""EntityExtractor agent — builds entity-to-article index from ingested metadata."""

from src.llm import call_llm, parse_json_response
from src.audit import log_agent_step, AuditTimer
from src.models import EntityMap


SYSTEM_INSTRUCTION = """You are a named entity extraction specialist for financial news.
Given article metadata, build a comprehensive entity index mapping each entity to the articles it appears in.
Focus on: people (ministers, economists, CEOs), companies, sectors, and policy items.
Return valid JSON."""


async def extract_entities(article_metadata: list[dict], session_id: str = "default") -> EntityMap:
    """Build entity-to-article index from article metadata.

    Args:
        article_metadata: List of enriched article metadata from ingestor
        session_id: Session ID for audit trail

    Returns:
        EntityMap with people, companies, sectors, policies, keywords
    """
    with AuditTimer() as timer:
        # Build prompt
        meta_text = ""
        for m in article_metadata:
            entities = m.get("key_entities", {})
            meta_text += f"\nArticle {m['id']}: {m['title']}\n"
            meta_text += f"  People: {entities.get('people', [])}\n"
            meta_text += f"  Companies: {entities.get('companies', [])}\n"
            meta_text += f"  Sectors: {entities.get('sectors', [])}\n"
            meta_text += f"  Policies: {entities.get('policies', [])}\n"
            meta_text += f"  Tags: {m.get('relevance_tags', [])}\n"

        prompt = f"""Build a comprehensive entity index from these {len(article_metadata)} articles.
Group entities by type and map each to the list of article IDs where it appears.
Normalize entity names (e.g. "FM" and "Finance Minister" should be the same entry).

{meta_text}

Return JSON:
{{
  "people": {{"person_name": ["article_id1", "article_id2"]}},
  "companies": {{"company_name": ["article_id1"]}},
  "sectors": {{"sector_name": ["article_id1", "article_id2"]}},
  "policies": {{"policy_item": ["article_id1"]}},
  "keywords": {{"keyword": ["article_id1", "article_id2"]}}
}}"""

        response = await call_llm(
            prompt=prompt,
            model="flash",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,
        )

        try:
            data = parse_json_response(response)
            entity_map = EntityMap(**data)
        except Exception:
            # Build from metadata directly as fallback
            entity_map = _build_entity_map_from_metadata(article_metadata)

    total_entities = (
        len(entity_map.people) + len(entity_map.companies)
        + len(entity_map.sectors) + len(entity_map.policies)
    )

    log_agent_step(
        agent_name="EntityExtractor",
        action="extract_entities",
        model_used="flash",
        input_summary=f"{len(article_metadata)} article metadata entries",
        output_summary=f"{total_entities} unique entities indexed",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return entity_map


def _build_entity_map_from_metadata(metadata: list[dict]) -> EntityMap:
    """Fallback: build entity map directly from metadata without LLM."""
    people, companies, sectors, policies, keywords = {}, {}, {}, {}, {}

    for m in metadata:
        aid = m["id"]
        entities = m.get("key_entities", {})
        for p in entities.get("people", []):
            people.setdefault(p, []).append(aid)
        for c in entities.get("companies", []):
            companies.setdefault(c, []).append(aid)
        for s in entities.get("sectors", []):
            sectors.setdefault(s, []).append(aid)
        for pol in entities.get("policies", []):
            policies.setdefault(pol, []).append(aid)
        for t in m.get("relevance_tags", []):
            keywords.setdefault(t, []).append(aid)

    return EntityMap(
        people=people, companies=companies, sectors=sectors,
        policies=policies, keywords=keywords,
    )
