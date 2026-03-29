"""Phase 6: Feed Organizer — Structure personalized feed into thematic sections.

Organization strategies:
- By user interests (primary grouping)
- By topic relevance (secondary sorting within section)
- By recency (latest first within section)
- By sentiment/urgency (market-moving news first)
"""

import json
import time
from typing import Optional
from src.models import UserProfile, FeedItem


def _normalize_topic(topic: str) -> str:
    """Normalize topic name (handle singular/plural variants)."""
    singular_to_plural = {
        "market": "markets",
        "sector": "sectors",
        "tech": "tech",
        "technolog": "tech",
        "polic": "policy",
        "macro": "macro",
        "econom": "macro",
    }
    
    topic_lower = topic.lower()
    
    # Check for exact match or prefix match
    for singular, plural in singular_to_plural.items():
        if topic_lower == singular or topic_lower == plural:
            return plural
        if topic_lower.startswith(singular):
            return plural
    
    return topic_lower


# ============================================================
# Feed Section Models
# ============================================================

class FeedSection:
    """A thematic section within the personalized feed."""
    
    def __init__(
        self,
        section_id: str,
        section_name: str,
        topic: str,
        description: str,
        articles: list[dict],
        icon: str = "📰",
        color: str = "#2563eb",
    ):
        self.section_id = section_id
        self.section_name = section_name  # e.g., "Markets & Investing"
        self.topic = topic  # e.g., "markets"
        self.description = description
        self.articles = articles  # List of FeedItems
        self.icon = icon
        self.color = color
    
    @property
    def article_count(self) -> int:
        """Return current count of articles (dynamic)."""
        return len(self.articles)
    
    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "section_name": self.section_name,
            "topic": self.topic,
            "description": self.description,
            "article_count": self.article_count,
            "icon": self.icon,
            "color": self.color,
            "articles": self.articles,
        }


class OrganizedFeed:
    """A personalized feed organized into sections."""
    
    def __init__(
        self,
        user_id: str,
        user_profile: UserProfile,
        sections: list[FeedSection],
        headline_articles: list[dict] = None,  # Top 2-3 articles across all sections
    ):
        self.user_id = user_id
        self.user_profile = user_profile
        self.sections = sections
        self.headline_articles = headline_articles or []
        self.total_articles = sum(s.article_count for s in sections)
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "user_profile": self.user_profile.model_dump(),
            "sections": [s.to_dict() for s in self.sections],
            "headline_articles": self.headline_articles,
            "total_articles": self.total_articles,
        }


# ============================================================
# Feed Organizer
# ============================================================

def organize_feed_into_sections(
    user_id: str,
    user_profile: UserProfile,
    feed_items: list[dict],  # With explanations included
    explanations: list[dict],
) -> OrganizedFeed:
    """
    Organize personalized feed items into thematic sections.
    
    Args:
        user_id: User identifier
        user_profile: UserProfile object
        feed_items: List of FeedItem dicts with article metadata
        explanations: List of explanation dicts (from Phase 3/5)
    
    Returns:
        OrganizedFeed with articles grouped into sections
    """
    # Section templates based on user profile interests
    section_config = _get_section_config_for_profile(user_profile)
    
    # Initialize sections
    sections: dict[str, FeedSection] = {}
    for config in section_config:
        sections[config["topic"]] = FeedSection(
            section_id=config["topic"],
            section_name=config["name"],
            topic=config["topic"],
            description=config["description"],
            articles=[],
            icon=config["icon"],
            color=config["color"],
        )
    
    # Assign articles to sections
    for item, explanation in zip(feed_items, explanations):
        # Use matched tags or fallback to primary interest
        matched_tags = explanation.get("matched_tags", [])
        assigned = False
        
        # Try to match tags to sections
        for tag in matched_tags:
            topic = tag.split(":")[0].lower() if ":" in tag else None
            if topic:
                # Normalize topic to match section keys
                normalized_topic = _normalize_topic(topic)
                if normalized_topic in sections:
                    sections[normalized_topic].articles.append({
                        "item": item,
                        "explanation": explanation,
                    })
                    assigned = True
                    break
        
        # Fallback: assign to first interest section that exists in sections
        if not assigned and user_profile.interests:
            for interest in user_profile.interests:
                normalized_interest = _normalize_topic(interest)
                if normalized_interest in sections:
                    sections[normalized_interest].articles.append({
                        "item": item,
                        "explanation": explanation,
                    })
                    assigned = True
                    break
        
        # Final fallback: use first section available
        if not assigned and sections:
            first_section = list(sections.values())[0]
            first_section.articles.append({
                "item": item,
                "explanation": explanation,
            })
    
    # Sort articles within each section by relevance score (descending)
    for section in sections.values():
        section.articles.sort(
            key=lambda x: x["explanation"].get("relevance_score", 0),
            reverse=True,
        )
    
    # Select headline articles (top 2-3 from highest relevance sections)
    headline_articles = []
    section_list = sorted(
        sections.values(),
        key=lambda s: max(
            (a["explanation"].get("relevance_score", 0) for a in s.articles),
            default=0,
        ),
        reverse=True,
    )
    
    for section in section_list:
        for article in section.articles[:1]:  # Top 1 from each section
            headline_articles.append({
                "item": article["item"],
                "explanation": article["explanation"],
                "section": section.section_name,
            })
            if len(headline_articles) >= 3:
                break
        if len(headline_articles) >= 3:
            break
    
    # Return organized feed
    organized = OrganizedFeed(
        user_id=user_id,
        user_profile=user_profile,
        sections=list(sections.values()),
        headline_articles=headline_articles,
    )
    
    return organized


def _get_section_config_for_profile(profile: UserProfile) -> list[dict]:
    """Get section configuration based on user profile interests."""
    
    all_sections = {
        "markets": {
            "name": "📈 Markets & Investing",
            "description": "Stock indices, portfolio news, investor insights",
            "icon": "📈",
            "color": "#059669",
        },
        "policy": {
            "name": "🏛️ Policy & Regulation",
            "description": "Government policy, regulatory changes, sector impact",
            "icon": "🏛️",
            "color": "#dc2626",
        },
        "tech": {
            "name": "🚀 Technology",
            "description": "Tech companies, startups, innovation, IT sector",
            "icon": "🚀",
            "color": "#7c3aed",
        },
        "sectors": {
            "name": "🏢 Sectors & Industries",
            "description": "Auto, pharma, finance, energy, banking trends",
            "icon": "🏢",
            "color": "#0891b2",
        },
        "macro": {
            "name": "🌍 Macroeconomics",
            "description": "GDP, inflation, global trends, economic cycles",
            "icon": "🌍",
            "color": "#ea580c",
        },
    }
    
    # Map user interests to sections
    interest_to_section = {
        "portfolio": "markets",
        "markets": "markets",
        "investing": "markets",
        "sectors": "sectors",
        "policy": "policy",
        "regulation": "policy",
        "tech": "tech",
        "startups": "tech",
        "innovation": "tech",
        "macro": "macro",
        "economics": "macro",
    }
    
    # Build sections from user's interests
    selected_sections = []
    for interest in profile.interests:
        topic = interest_to_section.get(interest.lower(), interest.lower())
        if topic in all_sections:
            config = all_sections[topic]
            selected_sections.append({
                "topic": topic,
                "name": config["name"],
                "description": config["description"],
                "icon": config["icon"],
                "color": config["color"],
            })
    
    # Deduplicate by topic
    seen = set()
    deduped = []
    for s in selected_sections:
        if s["topic"] not in seen:
            deduped.append(s)
            seen.add(s["topic"])
    
    # Ensure at least 3 sections
    if len(deduped) == 0:
        deduped = [
            {
                "topic": "markets",
                "name": all_sections["markets"]["name"],
                "description": all_sections["markets"]["description"],
                "icon": all_sections["markets"]["icon"],
                "color": all_sections["markets"]["color"],
            },
            {
                "topic": "tech",
                "name": all_sections["tech"]["name"],
                "description": all_sections["tech"]["description"],
                "icon": all_sections["tech"]["icon"],
                "color": all_sections["tech"]["color"],
            },
            {
                "topic": "policy",
                "name": all_sections["policy"]["name"],
                "description": all_sections["policy"]["description"],
                "icon": all_sections["policy"]["icon"],
                "color": all_sections["policy"]["color"],
            },
        ]
    elif len(deduped) < 3:
        # Add popular sections
        for topic, config in all_sections.items():
            if topic not in seen and len(deduped) < 3:
                deduped.append({
                    "topic": topic,
                    "name": config["name"],
                    "description": config["description"],
                    "icon": config["icon"],
                    "color": config["color"],
                })
                seen.add(topic)
    
    return deduped[:5]  # Cap at 5 sections


def filter_section_by_search(
    section: FeedSection,
    search_query: str,
) -> FeedSection:
    """Filter articles within a section by search query."""
    
    if not search_query:
        return section
    
    query_lower = search_query.lower()
    filtered_articles = [
        a for a in section.articles
        if query_lower in (a["item"].get("title", "") or "").lower()
        or query_lower in (a["item"].get("content", "") or "").lower()
    ]
    
    return FeedSection(
        section_id=section.section_id,
        section_name=section.section_name,
        topic=section.topic,
        description=section.description,
        articles=filtered_articles,
        icon=section.icon,
        color=section.color,
    )


def get_section_summary_stats(section: FeedSection) -> dict:
    """Get summary statistics for a feed section."""
    
    if not section.articles:
        return {
            "article_count": 0,
            "avg_relevance": 0.0,
            "confidence_distribution": {},
        }
    
    relevances = [
        a["explanation"].get("relevance_score", 0)
        for a in section.articles
    ]
    confidences = [
        a["explanation"].get("confidence", "low")
        for a in section.articles
    ]
    
    confidence_dist = {
        "high": confidences.count("high"),
        "medium": confidences.count("medium"),
        "low": confidences.count("low"),
    }
    
    return {
        "article_count": len(section.articles),
        "avg_relevance": sum(relevances) / len(relevances),
        "confidence_distribution": confidence_dist,
        "has_boosted": any(a["explanation"].get("boosted", False) for a in section.articles),
    }


# ============================================================
# For Phase 6 Testing
# ============================================================

def save_organized_feed(
    feed: OrganizedFeed,
    output_path: str = "output/organized_feeds.json",
) -> None:
    """Save organized feed structure for analysis."""
    import os
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    feeds = {}
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            feeds = json.load(f)
    
    key = f"{feed.user_id}_{int(time.time())}"
    feeds[key] = feed.to_dict()
    
    with open(output_path, "w") as f:
        json.dump(feeds, f, indent=2)
