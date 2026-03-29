"""Topic-level sentiment pulse derived from recent article metadata."""

from src.models import SentimentPulse


_SENTIMENT_TO_SCORE = {
    "bullish": 1.0,
    "neutral": 0.0,
    "bearish": -1.0,
}


def compute_sentiment_pulse(
    topic: str,
    recent_items: list[dict],
    metadata_map: dict,
    window_size: int = 5,
) -> SentimentPulse:
    """Compute a live sentiment pulse over the most recent items for a topic.

    Args:
        topic: Topic or section label
        recent_items: Feed item dicts sorted newest-first or already filtered
        metadata_map: Map of article_id -> metadata model/object
        window_size: Number of items to include in pulse

    Returns:
        SentimentPulse with label, score, and one-line reason
    """
    if window_size <= 0:
        window_size = 5

    sample = recent_items[:window_size]
    sentiment_values: list[float] = []
    weighted_values: list[float] = []
    sentiment_counts = {"bullish": 0, "neutral": 0, "bearish": 0}

    for item in sample:
        article_id = item.get("id")
        metadata = metadata_map.get(article_id)
        if not metadata:
            continue

        sentiment = (getattr(metadata, "sentiment", "neutral") or "neutral").lower()
        base = _SENTIMENT_TO_SCORE.get(sentiment, 0.0)
        credibility = float(getattr(metadata, "credibility_score", 0.5) or 0.5)

        sentiment_counts[sentiment if sentiment in sentiment_counts else "neutral"] += 1
        sentiment_values.append(base)
        weighted_values.append(base * max(0.25, min(1.0, credibility)))

    if not weighted_values:
        return SentimentPulse(
            topic=topic,
            label="Cautious",
            score=0.0,
            reason_line="Not enough recent signals yet; waiting for additional coverage.",
            sample_size=0,
        )

    raw_score = sum(weighted_values) / len(weighted_values)

    if raw_score >= 0.25:
        label = "Bullish"
    elif raw_score <= -0.25:
        label = "Bearish"
    else:
        label = "Cautious"

    reason = _build_reason_line(label, sentiment_counts, len(weighted_values))

    return SentimentPulse(
        topic=topic,
        label=label,
        score=round(raw_score, 3),
        reason_line=reason,
        sample_size=len(weighted_values),
    )


def _build_reason_line(label: str, sentiment_counts: dict[str, int], sample_size: int) -> str:
    bull = sentiment_counts.get("bullish", 0)
    neutral = sentiment_counts.get("neutral", 0)
    bear = sentiment_counts.get("bearish", 0)

    if label == "Bullish":
        return (
            f"Positive signals dominate ({bull}/{sample_size}) with limited negative pressure ({bear}/{sample_size})."
        )
    if label == "Bearish":
        return (
            f"Negative signals dominate ({bear}/{sample_size}) while supportive coverage remains thin ({bull}/{sample_size})."
        )

    return (
        f"Signals are mixed ({bull} bullish, {neutral} neutral, {bear} bearish), so conviction remains balanced."
    )
