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

# --- Video Config ---
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 1  # for slideshow-style frames
HINDI_TTS_VOICE = "hi-IN-SwaraNeural"
HINDI_FONT_PATH = os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf")
VIDEO_TIMEOUT_SECONDS = 90

# --- Agent Config ---
MAX_RETRIES = 1
REQUEST_TIMEOUT = 30
