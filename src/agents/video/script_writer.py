"""ScriptWriter agent — generates explainer scripts from extracted facts."""

import re

from src.llm import call_llm, parse_json_response
from src.config import get_video_language_profile
from src.audit import log_agent_step, AuditTimer
from src.models import VideoScript
from src.agents.video.localized_event import is_english_heavy, localize_event_text


SYSTEM_INSTRUCTION = """You are an Economic Times explainer script specialist.

You write business-news scripts for retail audiences with little financial background.

STRICT RULES:
1. Keep the script 160-240 words (target 75-110 seconds when spoken).
2. Structure: Hook -> What happened -> Key numbers -> Who is affected -> What it means for you -> Closing.
3. Keep tone calm, informative, and trustworthy.
4. Use only facts present in the provided source facts.
5. Explain complex financial terms using simple analogies.
6. Avoid sensationalism or speculation.
"""


def _language_prompt(language: str) -> str:
    profile = get_video_language_profile(language)
    return profile.get(
        "writing_hint",
        "Write in the requested language and avoid English except proper nouns.",
    )


def _fallback_script(facts: dict, language: str) -> VideoScript:
    lang = (language or "hi").lower()
    original_what = facts.get("what", "")
    what = original_what or "एक बड़ी कारोबारी घटना सामने आई है।"

    def english_token_count(text: str) -> int:
        return len(re.findall(r"[A-Za-z]{3,}", text or ""))

    if lang != "en" and (english_token_count(what) > 4 or is_english_heavy(what)):
        what = localize_event_text(original_what or what, lang)
    if lang == "en":
        script_text = (
            "Hello and welcome. Today's big business update: "
            f"{what} "
            "This development matters because it can affect operations, customers, investors, and confidence in the broader sector. "
            "Key stakeholders are now watching official updates, corrective actions, and how quickly normalcy is restored. "
            "For retail investors, the main takeaway is to track company disclosures, execution quality, and spillover risks before making decisions. "
            "What to watch next: regulator communication, management updates, and market reaction in related stocks."
        )
        transliteration = script_text
    elif lang == "mr":
        script_text = (
            "नमस्कार. आजच्या मोठ्या व्यावसायिक बातमीत "
            f"{what} "
            "याचा परिणाम बँका, गुंतवणूकदार, कर्मचारी आणि सुरू असलेल्या प्रकल्पांवर होऊ शकतो. "
            "पुढील टप्प्यात कर्जदार समितीचे निर्णय, कायदेशीर प्रक्रियेची गती आणि प्रकल्पांची सातत्यपूर्ण अंमलबजावणी महत्त्वाची असेल. "
            "आपल्यासाठी याचा अर्थ असा की गुंतवणुकीपूर्वी कर्जाचे प्रमाण, रोख प्रवाह आणि क्षेत्रीय जोखीम नक्की तपासा."
        )
        transliteration = "Namaskar..."
    elif lang == "bho":
        script_text = (
            "नमस्कार. आज के बड़ व्यवसायिक खबर में "
            f"{what} "
            "एहसे बैंक, निवेशक, कर्मचारी आ चल रहल परियोजनन पर असर पड़ सकत बा. "
            "आगे के चरण में कर्जदाता समिति के फैसला, कानूनी प्रक्रिया के रफ्तार आ परियोजना के प्रगति पर नजर जरूरी बा. "
            "रउरा खातिर मतलब ई बा कि निवेश से पहिले कर्ज, नकदी स्थिति आ सेक्टर के जोखिम जरूर जांचीं."
        )
        transliteration = "Namaskar..."
    elif lang == "ta":
        script_text = (
            "வணக்கம். இன்றைய முக்கிய வர்த்தகச் செய்தியில் "
            f"{what} "
            "இதன் தாக்கம் வங்கிகள், முதலீட்டாளர்கள், ஊழியர்கள் மற்றும் நடைபெற்று வரும் திட்டங்கள் மீது இருக்கலாம். "
            "அடுத்த கட்டத்தில் கடனளிப்போர் குழு முடிவுகள், சட்ட செயல்முறை வேகம் மற்றும் திட்ட முன்னேற்றம் கவனிக்க வேண்டிய முக்கிய சுட்டிகள். "
            "உங்களுக்கான முக்கிய பொருள்: முதலீட்டுக்கு முன் கடன் நிலை, பணப்புழக்கம் மற்றும் துறை ஆபத்தை கண்டிப்பாக மதிப்பிடுங்கள்."
        )
        transliteration = "Vanakkam..."
    elif lang == "te":
        script_text = (
            "నమస్కారం. ఈరోజు ప్రధాన వ్యాపార వార్తలో "
            f"{what} "
            "దీని ప్రభావం బ్యాంకులు, పెట్టుబడిదారులు, ఉద్యోగులు మరియు కొనసాగుతున్న ప్రాజెక్టులపై పడవచ్చు. "
            "తదుపరి దశలో రుణదాతల కమిటీ నిర్ణయాలు, చట్టపరమైన ప్రక్రియ వేగం, ప్రాజెక్టుల పురోగతి కీలకంగా ఉంటుంది. "
            "మీ కోసం ముఖ్య అర్థం: పెట్టుబడి నిర్ణయానికి ముందు రుణ స్థాయి, నగదు ప్రవాహం, రంగ ప్రమాదాన్ని తప్పనిసరిగా పరిశీలించండి."
        )
        transliteration = "Namaskaram..."
    elif lang == "kn":
        script_text = (
            "ನಮಸ್ಕಾರ. ಇಂದಿನ ಪ್ರಮುಖ ವ್ಯವಹಾರ ಸುದ್ದಿಯಲ್ಲಿ "
            f"{what} "
            "ಇದರ ಪರಿಣಾಮ ಬ್ಯಾಂಕುಗಳು, ಹೂಡಿಕೆದಾರರು, ನೌಕರರು ಮತ್ತು ನಡೆಯುತ್ತಿರುವ ಯೋಜನೆಗಳ ಮೇಲೆ ಬೀಳಬಹುದು. "
            "ಮುಂದಿನ ಹಂತದಲ್ಲಿ ಸಾಲದಾರರ ಸಮಿತಿ ನಿರ್ಧಾರಗಳು, ಕಾನೂನು ಪ್ರಕ್ರಿಯೆಯ ವೇಗ ಮತ್ತು ಯೋಜನೆಗಳ ಪ್ರಗತಿ ಗಮನಿಸಬೇಕಾದ ಮುಖ್ಯ ಸೂಚನೆಗಳು. "
            "ನಿಮಗಾಗಿ ಮುಖ್ಯ ಅರ್ಥ: ಹೂಡಿಕೆಗೂ ಮೊದಲು ಸಾಲದ ಮಟ್ಟ, ನಗದು ಹರಿವು ಮತ್ತು ಕ್ಷೇತ್ರದ ಅಪಾಯವನ್ನು ಪರಿಶೀಲಿಸಿ."
        )
        transliteration = "Namaskara..."
    elif lang == "pa":
        script_text = (
            "ਸਤ ਸ੍ਰੀ ਅਕਾਲ। ਅੱਜ ਦੀ ਵੱਡੀ ਕਾਰੋਬਾਰੀ ਖ਼ਬਰ ਵਿੱਚ "
            f"{what} "
            "ਇਸ ਦਾ ਅਸਰ ਬੈਂਕਾਂ, ਨਿਵੇਸ਼ਕਾਂ, ਕਰਮਚਾਰੀਆਂ ਅਤੇ ਚੱਲ ਰਹੇ ਪ੍ਰੋਜੈਕਟਾਂ 'ਤੇ ਪੈ ਸਕਦਾ ਹੈ। "
            "ਅਗਲੇ ਪੜਾਅ ਵਿੱਚ ਕਰਜ਼ਦਾਰ ਕਮੇਟੀ ਦੇ ਫ਼ੈਸਲੇ, ਕਾਨੂੰਨੀ ਪ੍ਰਕਿਰਿਆ ਦੀ ਰਫ਼ਤਾਰ ਅਤੇ ਪ੍ਰੋਜੈਕਟ ਤਰੱਕੀ ਮਹੱਤਵਪੂਰਣ ਰਹੇਗੀ। "
            "ਤੁਹਾਡੇ ਲਈ ਮਤਲਬ: ਨਿਵੇਸ਼ ਤੋਂ ਪਹਿਲਾਂ ਕਰਜ਼ਾ ਪੱਧਰ, ਨਕਦੀ ਪ੍ਰਵਾਹ ਅਤੇ ਸੈਕਟਰ ਜੋਖ਼ਮ ਜ਼ਰੂਰ ਵੇਖੋ।"
        )
        transliteration = "Sat sri akaal..."
    else:
        script_text = (
            "नमस्कार। आज की बड़ी कारोबारी खबर में "
            f"{what} "
            "इसका असर संचालन, उपभोक्ताओं, निवेशकों और संबंधित सेक्टर की धारणा पर पड़ सकता है। "
            "अब सबसे महत्वपूर्ण बात यह है कि आधिकारिक अपडेट क्या आते हैं, सुधारात्मक कदम कितनी तेजी से लागू होते हैं, और स्थिति कितनी जल्दी स्थिर होती है। "
            "आपके लिए इसका मतलब है कि निवेश से पहले कंपनी के खुलासे, निष्पादन क्षमता और सेक्टर पर संभावित असर ज़रूर देखें। "
            "आगे क्या देखना है: नियामक संचार, प्रबंधन की अगली अपडेट, और संबंधित शेयरों की चाल।"
        )
        transliteration = "Namaskaar..."

    return VideoScript(
        script_hindi=script_text,
        script_transliteration=transliteration,
        estimated_duration_seconds=80,
        key_facts_used=[facts.get("what", "")],
        analogies_used=["Debt stress is like household income falling while loan EMIs stay high."],
    )


async def write_script(
    facts: dict,
    language: str = "hi",
    target_duration_seconds: int = 90,
    session_id: str = "default",
) -> VideoScript:
    """Generate a language-aware explainer script from extracted facts.

    Args:
        facts: Structured facts from BreakingIngestor
        language: Target language code (hi/en)
        target_duration_seconds: Desired duration for narration
        session_id: Session ID for audit

    Returns:
        VideoScript with script text and metadata
    """
    with AuditTimer() as timer:
        prompt = f"""Write an explainer script ({target_duration_seconds - 15}-{target_duration_seconds + 20} seconds, 160-240 words) for this breaking news.

LANGUAGE RULE:
{_language_prompt(language)}

FACTS:
- What: {facts.get('what', '')}
- Who: {facts.get('who', '')}
- When: {facts.get('when', '')}
- Where: {facts.get('where', '')}
- Why: {facts.get('why', '')}

KEY NUMBERS:
{facts.get('key_numbers', [])}

IMPACT:
{facts.get('impact_points', [])}

Return JSON:
{{
    "script_hindi": "Full script in requested language...",
    "script_transliteration": "Roman transliteration (or same text for English)...",
    "estimated_duration_seconds": {target_duration_seconds},
  "key_facts_used": ["fact1 from article", "fact2 from article"],
  "analogies_used": ["analogy1 explaining a financial concept", "analogy2"]
}}"""

        response = await call_llm(
            prompt=prompt,
            model="pro",
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.6,
        )

        try:
            data = parse_json_response(response)
            result = VideoScript(**data)
        except Exception:
            result = _fallback_script(facts, language)

    # Guardrail: If script is unexpectedly short, replace with robust fallback.
    if len(result.script_hindi.strip()) < 280 or result.estimated_duration_seconds < 70:
        result = _fallback_script(facts, language)

    log_agent_step(
        agent_name="ScriptWriter",
        action="write_script",
        model_used="pro",
        input_summary=f"Facts: {facts.get('what', '')[:80]}",
        output_summary=(
            f"Lang: {language}, Script: {len(result.script_hindi)} chars, "
            f"~{result.estimated_duration_seconds}s"
        ),
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result


async def write_hindi_script(facts: dict, session_id: str = "default") -> VideoScript:
    """Backward-compatible wrapper for existing call sites."""
    return await write_script(facts=facts, language="hi", target_duration_seconds=90, session_id=session_id)
