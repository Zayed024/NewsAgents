from src.agents.navigator.entity_graph import build_entity_navigation_map
from src.models import EntityMap, AngleCluster


def test_build_entity_navigation_map_links_entities_to_angles():
    entity_map = EntityMap(
        people={"Nirmala Sitharaman": ["budget-001", "budget-003"]},
        companies={"Infosys": ["budget-005"]},
        sectors={"IT": ["budget-005"], "Healthcare": ["budget-006"]},
        policies={"Fiscal deficit": ["budget-001"]},
        keywords={"capex": ["budget-004"]},
    )

    angles = [
        AngleCluster(
            angle_name="Macro Impact",
            description="Macro and fiscal effects",
            article_ids=["budget-001", "budget-003", "budget-004"],
            key_themes=["growth", "fiscal deficit"],
        ),
        AngleCluster(
            angle_name="Sector Winners",
            description="Sector allocation and incentives",
            article_ids=["budget-005", "budget-006"],
            key_themes=["IT", "Healthcare"],
        ),
    ]

    graph = build_entity_navigation_map(entity_map, angles, session_id="test")

    people_nodes = graph["people"]
    assert people_nodes
    assert people_nodes[0]["entity"] == "Nirmala Sitharaman"
    assert "Macro Impact" in people_nodes[0]["angles"]

    company_nodes = graph["companies"]
    assert company_nodes
    assert company_nodes[0]["entity"] == "Infosys"
    assert company_nodes[0]["angles"] == ["Sector Winners"]


def test_build_entity_navigation_map_respects_entity_limit():
    many_people = {f"Person-{i}": ["budget-001"] for i in range(20)}
    entity_map = EntityMap(people=many_people)
    angles = [
        AngleCluster(
            angle_name="Macro Impact",
            description="Macro",
            article_ids=["budget-001"],
            key_themes=["growth"],
        )
    ]

    graph = build_entity_navigation_map(
        entity_map,
        angles,
        session_id="test",
        max_entities_per_type=5,
    )

    assert len(graph["people"]) == 5
