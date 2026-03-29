"""Phase 8 signal-layer helper tests (shared modules, no UI wiring)."""

from src.agents.contrarian_view import _fallback_contrarian
from src.agents.personal_impact import _fallback_personal_impact
from src.agents.sentiment_pulse import compute_sentiment_pulse


class _Meta:
    def __init__(self, sentiment: str, credibility_score: float):
        self.sentiment = sentiment
        self.credibility_score = credibility_score


def test_personal_impact_fallback_returns_three_bullets():
    profile = {
        "role": "Retail Investor",
        "interests": ["markets", "policy"],
    }
    summary = _fallback_personal_impact(
        profile=profile,
        item_title="RBI keeps rates unchanged amid inflation concerns",
        item_text="Policy stance remains cautious while growth projections are steady.",
    )

    assert summary.confidence in {"low", "medium", "high"}
    assert len(summary.bullet_points) == 3
    assert all(isinstance(p, str) and p.strip() for p in summary.bullet_points)


def test_contrarian_fallback_inverts_bullish_case():
    summary = _fallback_contrarian(
        item_title="Bank stocks rally on strong guidance",
        item_text="Investors cheer better net interest margin outlook.",
        current_sentiment="bullish",
    )

    assert "risk" in summary.other_side_take.lower() or "over" in summary.other_side_take.lower()
    assert summary.what_would_change_my_mind


def test_sentiment_pulse_scores_recent_window():
    items = [
        {"id": "a1"},
        {"id": "a2"},
        {"id": "a3"},
        {"id": "a4"},
        {"id": "a5"},
        {"id": "a6"},
    ]

    metadata_map = {
        "a1": _Meta("bullish", 0.9),
        "a2": _Meta("bullish", 0.8),
        "a3": _Meta("neutral", 0.7),
        "a4": _Meta("bullish", 0.9),
        "a5": _Meta("bearish", 0.4),
        "a6": _Meta("bearish", 1.0),  # outside top-5 window
    }

    pulse = compute_sentiment_pulse(
        topic="markets",
        recent_items=items,
        metadata_map=metadata_map,
        window_size=5,
    )

    assert pulse.sample_size == 5
    assert pulse.label in {"Bullish", "Cautious", "Bearish"}
    assert pulse.score > -1.0 and pulse.score <= 1.0
    assert isinstance(pulse.reason_line, str) and pulse.reason_line.strip()
