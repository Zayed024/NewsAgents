"""Onboarding agent — converts user answers to preference vectors and user profiles."""

import json
import os
from datetime import datetime
from src.config import DATA_DIR
from src.models import UserProfile
from src.llm import call_llm, parse_json_response
from src.config import GEMINI_FLASH
from src.audit import log_agent_step, AuditTimer


# Quick start questions (4 essentials)
QUICK_START_QUESTIONS = [
    {
        "id": "role",
        "question": "What best describes your investment/financial role?",
        "options": [
            "Student / Just Starting",
            "Salaried Professional",
            "Business Owner / Entrepreneur",
            "Financial Professional / Trader",
            "Retiree / Wealth Manager",
        ],
        "type": "single_choice",
    },
    {
        "id": "investing_experience",
        "question": "How long have you been investing?",
        "options": [
            "Just starting",
            "Less than 1 year",
            "1-3 years",
            "3-10 years",
            "10+ years",
        ],
        "type": "single_choice",
    },
    {
        "id": "primary_interests",
        "question": "What excites you most? (Pick up to 3)",
        "options": [
            "Personal savings & tax optimization",
            "Stock market & equity investing",
            "Mutual funds & passive investing",
            "Cryptocurrency & crypto assets",
            "Real estate & property",
            "Startup funding & venture",
            "Macro policy & economy",
            "Commodity & forex markets",
        ],
        "type": "multi_choice",
    },
    {
        "id": "content_preference",
        "question": "How do you prefer to consume financial news?",
        "options": [
            "Quick 2-min explainers with examples",
            "Data tables and numbers",
            "Long-form analysis (10+ min reads)",
            "Mix of formats",
        ],
        "type": "single_choice",
    },
]

# Deep setup additional questions
DEEP_SETUP_QUESTIONS = [
    {
        "id": "age_range",
        "question": "Age range?",
        "options": ["18-25", "26-35", "36-45", "46-60", "60+"],
        "type": "single_choice",
    },
    {
        "id": "risk_appetite",
        "question": "Your risk appetite?",
        "options": [
            "Conservative (safety first)",
            "Moderate (balanced growth)",
            "Aggressive (maximum growth)",
        ],
        "type": "single_choice",
    },
    {
        "id": "portfolio_exposure",
        "question": "Where is your money invested? (Pick all that apply)",
        "options": [
            "Cash / Savings account",
            "Index funds & ETFs",
            "Active mutual funds",
            "Individual stocks",
            "Bonds & fixed income",
            "Real estate / Property",
            "Cryptocurrency",
            "Commodities",
        ],
        "type": "multi_choice",
    },
    {
        "id": "news_frequency",
        "question": "How often do you check financial news?",
        "options": [
            "Daily",
            "Multiple times a week",
            "Weekly",
            "Monthly",
            "Only during major events",
        ],
        "type": "single_choice",
    },
    {
        "id": "learning_goal",
        "question": "Primary reason for reading ET news:",
        "options": [
            "Stay informed about markets",
            "Make investment decisions",
            "Learn concepts & fundamentals",
            "Track specific stocks/sectors",
            "Understand policy & economy",
        ],
        "type": "single_choice",
    },
    {
        "id": "languages",
        "question": "Languages you're comfortable with (pick all):",
        "options": [
            "English",
            "Hindi",
            "Marathi",
            "Tamil",
            "Telugu",
            "Kannada",
        ],
        "type": "multi_choice",
    },
]


def answers_to_preference_vector(answers: dict) -> dict:
    """Convert onboarding answers to a preference vector used by profiler, ranker, adapter.
    
    Args:
        answers: Dict of question_id -> selected_option(s)
    
    Returns:
        Preference vector dict with content_depth, format_preference, tone, etc.
    """
    # Map experience level to content depth
    exp = answers.get("investing_experience", "Less than 1 year").lower()
    if "just starting" in exp or "less than 1 year" in exp:
        depth = "beginner"
    elif "1-3 years" in exp:
        depth = "intermediate"
    else:
        depth = "expert"

    # Map content preference to format
    content_pref = answers.get("content_preference", "Mix of formats").lower()
    if "2-min" in content_pref or "short" in content_pref:
        format_pref = "explainer"
    elif "data" in content_pref or "numbers" in content_pref:
        format_pref = "data_table"
    elif "long" in content_pref:
        format_pref = "standard"
    else:
        format_pref = "standard"

    # Build priority topics from primary interests
    interests = answers.get("primary_interests", [])
    if isinstance(interests, str):
        interests = [interests]

    # Role-based tone
    role = answers.get("role", "").lower()
    if "professional" in role or "cfo" in role or "trader" in role:
        tone = "formal_analytical"
    elif "student" in role or "just" in role:
        tone = "educational"
    else:
        tone = "conversational"

    # Risk appetite -> jargon level (conservative users prefer less jargon)
    risk = answers.get("risk_appetite", "Moderate").lower()
    if "conservative" in risk:
        jargon = "low"
    elif "moderate" in risk:
        jargon = "medium"
    else:
        jargon = "high"

    return {
        "content_depth": depth,
        "format_preference": format_pref,
        "tone": tone,
        "jargon_level": jargon,
        "priority_topics": interests,
        "depriority_topics": [],
        "data_preference": "inline_numbers" if "data" in content_pref else "minimal_numbers" if depth == "beginner" else "inline_numbers",
        "framing_style": _get_framing_style(depth, interests),
        "reading_grade_level": {"expert": 14, "intermediate": 11, "beginner": 8}.get(depth, 11),
        "max_article_length_words": {"expert": 800, "intermediate": 500, "beginner": 300}.get(depth, 500),
        "language_preference": answers.get("languages", ["English"])[0] if answers.get("languages") else "English",
    }


def _get_framing_style(depth: str, interests: list) -> str:
    """Generate a framing style description based on depth and interests."""
    if depth == "expert":
        return "Data-dense executive briefing with policy implications and market impact analysis"
    elif depth == "beginner":
        return "Simple explanations with everyday analogies, no jargon, focus on personal impact"
    else:
        return "Balanced coverage with context, explain key terms, connect to user interests"


def answers_to_user_profile(
    user_id: str,
    name: str,
    answers: dict,
    is_deep_setup: bool = False,
) -> UserProfile:
    """Convert answers to a full UserProfile object.
    
    Args:
        user_id: Unique user identifier
        name: User's full name
        answers: Onboarding answers dict
        is_deep_setup: Whether answers came from deep setup (more questions)
    
    Returns:
        UserProfile object ready to save
    """
    pref_vector = answers_to_preference_vector(answers)
    
    # Extract standard fields
    age_range = answers.get("age_range", "26-35")
    age = int(age_range.split("-")[0]) if "-" in age_range else 30  # Use start of range
    
    role = answers.get("role", "Salaried Professional")
    interests = answers.get("primary_interests", [])
    if isinstance(interests, str):
        interests = [interests]
    
    investing_exp = answers.get("investing_experience", "1-3 years")
    portfolio = answers.get("portfolio_exposure", [])
    if isinstance(portfolio, str):
        portfolio = [portfolio]
    
    news_freq = answers.get("news_frequency", "Multiple times a week")
    
    return UserProfile(
        user_id=user_id,
        name=name,
        age=age,
        role=role,
        interests=interests,
        reading_level=pref_vector["content_depth"],
        preferred_format=pref_vector["format_preference"],
        portfolio_exposure=portfolio,
        news_consumption=f"Checks news {news_freq.lower()}; prefers {pref_vector['format_preference']} format",
        investing_experience=investing_exp,
        company_type=_extract_company_type(role),
    )


def _extract_company_type(role: str) -> str:
    """Infer company type from role."""
    if "startup" in role.lower() or "entrepreneur" in role.lower():
        return "startup"
    elif "financial" in role.lower():
        return "financial_services"
    elif "student" in role.lower():
        return "education"
    return ""


def save_user_profile(profile: UserProfile) -> bool:
    """Save user profile to JSON file in data/user_profiles.
    
    Args:
        profile: UserProfile to save
    
    Returns:
        True if successful, False otherwise
    """
    try:
        profile_dir = os.path.join(DATA_DIR, "user_profiles")
        os.makedirs(profile_dir, exist_ok=True)
        
        filename = f"{profile.user_id}.json"
        filepath = os.path.join(profile_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error saving profile: {e}")
        return False


def load_user_by_id(user_id: str) -> UserProfile | None:
    """Load a user profile by user_id.
    
    Args:
        user_id: User identifier
    
    Returns:
        UserProfile if found, None otherwise
    """
    try:
        profile_dir = os.path.join(DATA_DIR, "user_profiles")
        filepath = os.path.join(profile_dir, f"{user_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return UserProfile(**data)
    except Exception as e:
        print(f"Error loading profile: {e}")
        return None


def list_all_user_profiles() -> list[dict]:
    """List all saved user profiles with basic info.
    
    Returns:
        List of dicts with user_id, name, role, age
    """
    try:
        profile_dir = os.path.join(DATA_DIR, "user_profiles")
        if not os.path.exists(profile_dir):
            return []
        
        users = []
        for filename in os.listdir(profile_dir):
            if not filename.endswith(".json"):
                continue
            
            filepath = os.path.join(profile_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            users.append({
                "user_id": data.get("user_id"),
                "name": data.get("name"),
                "role": data.get("role"),
                "age": data.get("age"),
                "reading_level": data.get("reading_level"),
            })
        
        return sorted(users, key=lambda x: x.get("name", ""))
    except Exception:
        return []
