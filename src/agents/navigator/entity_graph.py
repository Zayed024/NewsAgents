"""Build entity-driven navigation graph for the deep briefing."""

from src.audit import log_agent_step, AuditTimer
from src.models import AngleCluster, EntityMap


def build_entity_navigation_map(
    entity_map: EntityMap,
    angles: list[AngleCluster],
    session_id: str = "default",
    max_entities_per_type: int = 12,
) -> dict[str, list[dict]]:
    """Map entities to related angles and source article IDs for navigation."""
    with AuditTimer() as timer:
        angle_articles = {
            angle.angle_name: set(angle.article_ids)
            for angle in angles
        }

        result = {
            "people": _build_type_navigation(entity_map.people, angle_articles, max_entities_per_type),
            "companies": _build_type_navigation(entity_map.companies, angle_articles, max_entities_per_type),
            "sectors": _build_type_navigation(entity_map.sectors, angle_articles, max_entities_per_type),
            "policies": _build_type_navigation(entity_map.policies, angle_articles, max_entities_per_type),
            "keywords": _build_type_navigation(entity_map.keywords, angle_articles, max_entities_per_type),
        }

    total_nodes = sum(len(nodes) for nodes in result.values())
    log_agent_step(
        agent_name="EntityGraphBuilder",
        action="build_entity_navigation_map",
        model_used="deterministic",
        input_summary=f"angles={len(angles)}",
        output_summary=f"entity_nodes={total_nodes}",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result


def _build_type_navigation(
    entities: dict[str, list[str]],
    angle_articles: dict[str, set[str]],
    max_entities_per_type: int,
) -> list[dict]:
    rows: list[dict] = []

    for entity_name, article_ids in entities.items():
        deduped_ids = sorted({aid for aid in article_ids if aid})
        if not deduped_ids:
            continue

        entity_article_set = set(deduped_ids)
        related_angles = [
            angle_name
            for angle_name, article_set in angle_articles.items()
            if entity_article_set.intersection(article_set)
        ]

        if not related_angles:
            continue

        rows.append({
            "entity": entity_name,
            "article_ids": deduped_ids,
            "angles": related_angles,
            "article_count": len(deduped_ids),
            "angle_count": len(related_angles),
        })

    rows.sort(key=lambda row: (row["angle_count"], row["article_count"], row["entity"].lower()), reverse=True)
    return rows[:max_entities_per_type]
