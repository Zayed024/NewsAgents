import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- Model Names ---
GEMINI_PRO = "gemini-2.0-flash"
GEMINI_FLASH = "gemini-2.0-flash"
OLLAMA_MODEL = "qwen2.5vl:3b"

# --- GenAI Client (lazy init) ---
_genai_client = None


def get_genai_client():
    """Get or create the Google GenAI client."""
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client

# --- Smart Model Routing Table ---
MODEL_ROUTING = {
    "extraction": GEMINI_FLASH,
    "classification": GEMINI_FLASH,
    "ranking": GEMINI_FLASH,
    "fact_checking": GEMINI_FLASH,
    "synthesis": GEMINI_PRO,
    "creative_writing": GEMINI_PRO,
    "complex_reasoning": GEMINI_PRO,
    "fallback": OLLAMA_MODEL,
}

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
WINDOWS_FONTS_DIR = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")

# --- Video Config ---
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 1  # for slideshow-style frames
HINDI_TTS_VOICE = "hi-IN-SwaraNeural"
HINDI_FONT_PATH = os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf")
VIDEO_TIMEOUT_SECONDS = 90


def _pick_existing_font(candidates: list[str]) -> str:
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return HINDI_FONT_PATH


LANGUAGE_FONT_CANDIDATES = {
    "bho": [
        os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf"),
        os.path.join(WINDOWS_FONTS_DIR, "Nirmala.ttc"),
        os.path.join(WINDOWS_FONTS_DIR, "Mangal.ttf"),
    ],
    "hi": [
        os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf"),
        os.path.join(WINDOWS_FONTS_DIR, "Nirmala.ttc"),
        os.path.join(WINDOWS_FONTS_DIR, "Mangal.ttf"),
    ],
    "kn": [
        os.path.join(FONTS_DIR, "NotoSansKannada-Regular.ttf"),
        os.path.join(WINDOWS_FONTS_DIR, "Nirmala.ttc"),
        os.path.join(WINDOWS_FONTS_DIR, "Tunga.ttf"),
    ],
    "mr": [
        os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf"),
        os.path.join(WINDOWS_FONTS_DIR, "Nirmala.ttc"),
        os.path.join(WINDOWS_FONTS_DIR, "Mangal.ttf"),
    ],
    "pa": [
        os.path.join(FONTS_DIR, "NotoSansGurmukhi-Regular.ttf"),
        os.path.join(WINDOWS_FONTS_DIR, "Nirmala.ttc"),
        os.path.join(WINDOWS_FONTS_DIR, "Raavi.ttf"),
    ],
    "ta": [
        os.path.join(FONTS_DIR, "NotoSansTamil-Regular.ttf"),
        os.path.join(WINDOWS_FONTS_DIR, "Nirmala.ttc"),
        os.path.join(WINDOWS_FONTS_DIR, "Latha.ttf"),
    ],
    "te": [
        os.path.join(FONTS_DIR, "NotoSansTelugu-Regular.ttf"),
        os.path.join(WINDOWS_FONTS_DIR, "Nirmala.ttc"),
        os.path.join(WINDOWS_FONTS_DIR, "Vani.ttf"),
    ],
}

# --- Language Profiles (Phase 1) ---
DEFAULT_VIDEO_LANGUAGE = "hi"
VIDEO_LANGUAGE_PROFILES = {
    "bho": {
        "label": "Bhojpuri",
        "tts_voice": "hi-IN-SwaraNeural",
        "tts_fallback_voices": ["hi-IN-MadhurNeural"],
        "font_path": _pick_existing_font(LANGUAGE_FONT_CANDIDATES["bho"]),
        "writing_hint": "Write in Bhojpuri using Devanagari script. Avoid English except proper nouns.",
        "validator_hint": "Bhojpuri (Devanagari), no English except proper nouns.",
    },
    "hi": {
        "label": "Hindi",
        "tts_voice": "hi-IN-SwaraNeural",
        "tts_fallback_voices": ["hi-IN-MadhurNeural"],
        "font_path": _pick_existing_font(LANGUAGE_FONT_CANDIDATES["hi"]),
        "writing_hint": "Write in Hindi (Devanagari). Avoid English except proper nouns.",
        "validator_hint": "Hindi (Devanagari), no English except proper nouns.",
    },
    "kn": {
        "label": "Kannada",
        "tts_voice": "kn-IN-SapnaNeural",
        "tts_fallback_voices": ["kn-IN-GaganNeural"],
        "font_path": _pick_existing_font(LANGUAGE_FONT_CANDIDATES["kn"]),
        "writing_hint": "Write in Kannada. Avoid English except proper nouns.",
        "validator_hint": "Kannada, no English except proper nouns.",
    },
    "mr": {
        "label": "Marathi",
        "tts_voice": "mr-IN-AarohiNeural",
        "tts_fallback_voices": ["mr-IN-ManoharNeural"],
        "font_path": _pick_existing_font(LANGUAGE_FONT_CANDIDATES["mr"]),
        "writing_hint": "Write in Marathi using Devanagari script. Avoid English except proper nouns.",
        "validator_hint": "Marathi (Devanagari), no English except proper nouns.",
    },
    "pa": {
        "label": "Punjabi",
        "tts_voice": "",
        "tts_fallback_voices": [],
        "font_path": _pick_existing_font(LANGUAGE_FONT_CANDIDATES["pa"]),
        "writing_hint": "Write in Punjabi. Avoid English except proper nouns.",
        "validator_hint": "Punjabi, no English except proper nouns.",
    },
    "ta": {
        "label": "Tamil",
        "tts_voice": "ta-IN-PallaviNeural",
        "tts_fallback_voices": ["ta-IN-ValluvarNeural"],
        "font_path": _pick_existing_font(LANGUAGE_FONT_CANDIDATES["ta"]),
        "writing_hint": "Write in Tamil. Avoid English except proper nouns.",
        "validator_hint": "Tamil, no English except proper nouns.",
    },
    "te": {
        "label": "Telugu",
        "tts_voice": "te-IN-ShrutiNeural",
        "tts_fallback_voices": ["te-IN-MohanNeural"],
        "font_path": _pick_existing_font(LANGUAGE_FONT_CANDIDATES["te"]),
        "writing_hint": "Write in Telugu. Avoid English except proper nouns.",
        "validator_hint": "Telugu, no English except proper nouns.",
    },
}


def get_video_language_profile(language: str | None = None) -> dict:
    """Return language profile for video generation, with safe fallback."""
    lang = (language or DEFAULT_VIDEO_LANGUAGE).lower()
    return VIDEO_LANGUAGE_PROFILES.get(lang, VIDEO_LANGUAGE_PROFILES[DEFAULT_VIDEO_LANGUAGE])


def get_font_path_for_language(language: str | None = None) -> str:
    """Return resolved font path for a language profile."""
    profile = get_video_language_profile(language)
    font_path = profile.get("font_path", HINDI_FONT_PATH)
    return font_path if os.path.exists(font_path) else HINDI_FONT_PATH

# --- Agent Config ---
MAX_RETRIES = 1
REQUEST_TIMEOUT = 30


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = str(raw).strip().lower()
    return value in {"1", "true", "yes", "on"}


def is_retrieval_contracts_enabled() -> bool:
    """Feature flag for gradual rollout of typed retrieval contracts."""
    return _env_bool("RETRIEVAL_CONTRACTS_ENABLED", default=True)
