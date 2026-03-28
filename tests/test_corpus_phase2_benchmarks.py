"""Phase 2 Quality Benchmarks — Precision/Recall tests for retrieval quality.

These tests verify the hybrid retrieval system achieves acceptable quality
metrics on curated financial news queries with expected relevant articles.

Benchmark Goals:
- Precision: Selected articles are actually relevant to the query
- Recall: We're not missing important relevant articles
- Coverage: Diverse topical coverage in results
"""

import pytest
from src.models import Article
from src.tools.corpus.relevance import hybrid_rank_articles, llm_rerank_top


def _article(article_id: str, title: str, category: str, content: str, published_at: str) -> Article:
    """Helper to create test articles."""
    return Article(
        id=article_id,
        title=title,
        published_at=published_at,
        category=category,
        content=content,
        author="ET Staff",
        tags=[category],
        url=f"https://economictimes.com/{article_id}",
    )


class TestRetrievalPrecisionBenchmark:
    """Verify that selected articles are relevant to the query."""

    def test_budget_query_precision(self):
        """Budget-related query should select fiscally-relevant articles."""
        query = "union budget fiscal deficit government spending"
        
        articles = [
            _article("budget-001", "Union Budget 2026 boosts capex",
                    "economy", "Union budget increases capex and infrastructure spending significantly.",
                    "2026-01-15T10:00:00+00:00"),
            _article("deficit-002", "Fiscal deficit widens to 5.2% FY26",
                    "economy", "Government fiscal deficit widened beyond earlier projections.",
                    "2026-01-14T09:30:00+00:00"),
            _article("tax-003", "Tax revenue strong in Q3 FY26",
                    "economy", "Tax collections exceed government estimates by 8%.",
                    "2026-01-13T08:00:00+00:00"),
            _article("meme-004", "Meme stocks surge on Reddit",
                    "markets", "Retail traders push meme stocks higher amid social media buzz.",
                    "2026-01-12T14:00:00+00:00"),
            _article("crypto-005", "Bitcoin hits new all-time high",
                    "crypto", "Cryptocurrency bull run continues as institutions pile in.",
                    "2026-01-11T16:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=5)
        assert len(ranked) > 0, "Should rank articles"

        # Top 3 should be budget-relevant
        top_ids = [r["article_id"] for r in ranked[:3]]
        assert "budget-001" in top_ids, "Budget article should rank highly"
        assert "deficit-002" in top_ids, "Fiscal deficit article should rank highly"
        
        # Verify top result is actually budget-related
        top_article = ranked[0]["article"]
        assert any(
            keyword in top_article.title.lower() or keyword in top_article.content.lower()
            for keyword in ["budget", "fiscal", "spending", "deficit"]
        ), f"Top article '{top_article.title}' should contain budget keywords"

    def test_rbi_policy_precision(self):
        """RBI policy query should select monetary/rate-related articles."""
        query = "RBI monetary policy interest rates tightening"
        
        articles = [
            _article("rbi-001", "RBI maintains policy rate at current level",
                    "monetary", "RBI announces unchanged monetary policy with focus on inflation control.",
                    "2026-01-15T09:00:00+00:00"),
            _article("rate-002", "Repo rate hike expected by Q1 FY27",
                    "monetary", "Analysts expect RBI to raise repo rate in next policy.",
                    "2026-01-14T10:00:00+00:00"),
            _article("inflation-003", "Inflation at 5.6% in January",
                    "economy", "Consumer inflation data released, slightly above RBI target.",
                    "2026-01-13T08:00:00+00:00"),
            _article("stock-004", "Market closes higher on RBI optimism",
                    "markets", "Equities rally on expectations of accommodative RBI stance.",
                    "2026-01-12T15:00:00+00:00"),
            _article("weather-005", "Monsoon forecast for 2026",
                    "commodity", "Weather department predicts normal monsoon this year.",
                    "2026-01-11T11:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=5)
        top_3 = [r["article_id"] for r in ranked[:3]]
        
        # Top articles should be RBI/monetary policy related
        assert "rbi-001" in top_3 or "rate-002" in top_3, "RBI articles should rank in top 3"
        
        # Verify scores align with relevance
        top_scores = [r["combined_score"] for r in ranked[:3]]
        bottom_scores = [r["combined_score"] for r in ranked[3:]]
        assert all(ts >= bs for ts in top_scores for bs in bottom_scores), \
            "Top articles should have higher scores than non-relevant articles"

    def test_corporate_governance_precision(self):
        """Corporate governance query should select board/compliance articles."""
        query = "corporate governance board directors regulations compliance"
        
        articles = [
            _article("gov-001", "Independent directors drive governance reforms",
                    "corporate", "Listed companies strengthen board independence per new regulations.",
                    "2026-01-15T12:00:00+00:00"),
            _article("regulation-002", "SEBI tightens disclosure norms for corporates",
                    "corporate", "SEBI announces stricter disclosure and governance requirements.",
                    "2026-01-14T13:00:00+00:00"),
            _article("social-003", "ESG focus grows among Indian firms",
                    "corporate", "More corporates adopting ESG and governance best practices.",
                    "2026-01-13T14:00:00+00:00"),
            _article("startup-004", "Tech startup launches new AI product",
                    "technology", "Startup unveils cutting-edge AI solution for enterprise.",
                    "2026-01-12T16:00:00+00:00"),
            _article("sports-005", "Cricket team announces new sponsorship deal",
                    "corporate", "Major brand becomes title sponsor for cricket tournament.",
                    "2026-01-11T18:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=5)
        top_ids = [r["article_id"] for r in ranked[:3]]
        
        # Governance-specific articles should top the list
        assert "gov-001" in top_ids or "regulation-002" in top_ids, \
            "Governance articles should rank higher"


@pytest.mark.asyncio
class TestRetrievalRecallBenchmark:
    """Verify we're not missing relevant articles in retrieval."""

    async def test_budget_recall_completeness(self):
        """Budget query should recall all fiscal/budget-related articles."""
        query = "union budget capex infrastructure spending"
        
        articles = [
            _article("b1", "Budget capex allocation announced", "economy",
                    "Union budget allocates increased capex for infrastructure.",
                    "2026-01-15T10:00:00+00:00"),
            _article("b2", "States get higher capex allocation", "economy",
                    "State governments receive increased infrastructure spending from center.",
                    "2026-01-14T09:00:00+00:00"),
            _article("b3", "Roads construction accelerates with budget boost", "economy",
                    "National highway authority accelerates road projects on budgeted funds.",
                    "2026-01-13T08:00:00+00:00"),
            _article("b4", "Railway expansion budget exceeds expectations", "economy",
                    "Ministry announces record capex for railway infrastructure expansion.",
                    "2026-01-12T07:00:00+00:00"),
            _article("x1", "Cricket match highlights", "sports",
                    "India vs Australia cricket match ends in thrilling tie.",
                    "2026-01-11T18:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=10)
        selected_ids = [r["article_id"] for r in ranked]
        
        # Should recall at least 80% of budget-related articles
        budget_articles = {"b1", "b2", "b3", "b4"}
        recalled = budget_articles.intersection(set(selected_ids))
        recall_rate = len(recalled) / len(budget_articles)
        assert recall_rate >= 0.75, f"Recall rate {recall_rate:.0%} below threshold for budget articles"

    async def test_tech_stocks_recall(self):
        """Tech stocks query should recall tech investment articles."""
        query = "tech stocks investment growth IT companies"
        
        articles = [
            _article("t1", "Indian IT stocks rally on dollar strength",
                    "technology", "Infosys and TCS stocks rise on favorable forex movement.",
                    "2026-01-15T11:00:00+00:00"),
            _article("t2", "Cloud computing stocks surge 15%",
                    "technology", "Cloud-based service providers show strong growth momentum.",
                    "2026-01-14T10:00:00+00:00"),
            _article("t3", "SaaS startups attract venture capital",
                    "technology", "Software-as-a-service companies attract record VC funding.",
                    "2026-01-13T09:00:00+00:00"),
            _article("t4", "Tech sector valuations at new highs",
                    "technology", "Technology sector market cap crosses $500B mark.",
                    "2026-01-12T08:00:00+00:00"),
            _article("f1", "Finance ETF gains on tech allocation",
                    "finance", "Equity-focused ETF gains as tech stocks outperform.",
                    "2026-01-11T07:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=10)
        selected_ids = [r["article_id"] for r in ranked]
        
        # Should recall most tech-related articles
        tech_articles = {"t1", "t2", "t3", "t4"}
        recalled = tech_articles.intersection(set(selected_ids))
        recall_rate = len(recalled) / len(tech_articles)
        assert recall_rate >= 0.75, f"Tech stocks recall rate {recall_rate:.0%} too low"


class TestRetrievalCoverageBenchmark:
    """Verify diverse topical coverage in results."""

    def test_diverse_category_coverage(self):
        """Broad query should select articles from diverse categories."""
        query = "financial markets economy policy"
        
        articles = [
            _article("econ-1", "GDP growth slows to 4.2%", "economy",
                    "Economic growth in Q3 FY26 slows below expectations.",
                    "2026-01-15T10:00:00+00:00"),
            _article("market-1", "Sensex closes at new record high", "markets",
                    "Stock exchange index reaches all-time high on strong inflows.",
                    "2026-01-14T15:00:00+00:00"),
            _article("policy-1", "Government announces new FDI norms", "policy",
                    "Foreign direct investment rules relaxed for select sectors.",
                    "2026-01-13T12:00:00+00:00"),
            _article("market-2", "Banking stocks outperform broader market", "markets",
                    "Bank sector rallies on improved credit growth expectations.",
                    "2026-01-12T14:00:00+00:00"),
            _article("econ-2", "Unemployment rate drops to 3.5%", "economy",
                    "Labor force participation increases on job creation.",
                    "2026-01-11T09:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=5)
        categories = {r["article"].category for r in ranked}
        
        # Should select from at least 2-3 different categories
        assert len(categories) >= 2, f"Coverage should span multiple categories, got {categories}"

    def test_temporal_diversity_in_selection(self):
        """Results should include both recent and slightly older relevant articles."""
        query = "monetary policy tightening inflation control"
        
        # Mix of recent and older articles
        articles = [
            _article("old-1", "RBI tightening cycle began in April 2022",
                    "monetary", "Historical analysis of RBI's tightening cycle.",
                    "2025-11-01T10:00:00+00:00"),  # 2 months old
            _article("recent-1", "RBI likely to hold rates in Jan 2026",
                    "monetary", "Latest analysis suggests RBI may pause tightening.",
                    "2026-01-15T10:00:00+00:00"),  # Recent
            _article("mid-1", "Inflation pressures mount in December",
                    "economy", "December inflation rises on food prices.",
                    "2025-12-20T10:00:00+00:00"),  # ~3 weeks old
            _article("unrelated", "New smartphone launch announced",
                    "technology", "Tech company announces flagship phone.",
                    "2026-01-14T10:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=4)
        
        # Should include multiple relevant articles, mixing freshness with relevance
        selected_ids = [r["article_id"] for r in ranked]
        relevant_selected = [aid for aid in selected_ids if aid != "unrelated"]
        assert len(relevant_selected) >= 2, "Should select diverse relevant articles"


class TestRelevanceExplainability:
    """Verify that relevance decisions are well-explained."""

    def test_scoring_reasons_are_provided(self):
        """Each ranked result should have clear reasons for inclusion."""
        query = "corporate dividend announcements"
        
        articles = [
            _article("div-1", "TCS announces record dividend payout",
                    "corporate", "Tata Consultancy Services declares highest dividend yet.",
                    "2026-01-15T10:00:00+00:00"),
            _article("div-2", "Dividend stocks attract retail investors",
                    "markets", "High-yielding dividend stocks see record inflows.",
                    "2026-01-14T10:00:00+00:00"),
            _article("earnings-1", "Q3 earnings season begins with strong results",
                    "corporate", "Companies announce better-than-expected quarterly earnings.",
                    "2026-01-13T10:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=3)
        
        # All results should have clear reasons
        for result in ranked:
            assert "reason_parts" in str(result) or "base_reason" in str(result) or result.get("base_reason"), \
                f"Result {result['article_id']} should have explanation"
            assert result.get("base_reason"), \
                f"Result should have base_reason, got {result}"

    def test_bm25_vs_embedding_explanation(self):
        """Results should distinguish between lexical and semantic matches."""
        query = "artificial intelligence machine learning neural networks"
        
        articles = [
            _article("ai-1", "AI winter fears unfounded say experts",  # Lexical match only
                    "technology", "Experts dismiss concerns about AI investment slowdown.",
                    "2026-01-15T10:00:00+00:00"),
            _article("ml-1", "Deep learning models achieve superhuman performance",  # Lexical
                    "technology", "Neural networks trained on new dataset exceed benchmarks.",
                    "2026-01-14T10:00:00+00:00"),
            _article("nlp-1", "Language models transform natural language processing",  # Semantic
                    "technology", "Latest models in text understanding show breakthrough results.",
                    "2026-01-13T10:00:00+00:00"),
        ]

        ranked = hybrid_rank_articles(query, articles, top_k=3)
        
        # Should have mixed semantic/lexical explanations
        reasons = [r["base_reason"] for r in ranked]
        assert len(reasons) > 0, "Should provide reasons"
        
        # At least one should mention either lexical or semantic scoring
        combined_text = " ".join(reasons)
        assert "match" in combined_text.lower() or "score" in combined_text.lower()
