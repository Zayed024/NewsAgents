"""ScriptWriter agent — generates Hindi explainer script from extracted facts."""

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_PRO
from src.audit import log_agent_step, AuditTimer
from src.models import VideoScript


SYSTEM_INSTRUCTION = """आप Economic Times के लिए हिंदी न्यूज़ एक्सप्लेनर स्क्रिप्ट लिखने वाले विशेषज्ञ हैं।

You write Hindi news explainer scripts for semi-urban retail investors with NO financial background.

STRICT RULES:
1. Write ENTIRELY in Hindi (Devanagari script). NO English words except proper nouns (company names, "NCLT").
2. Replace ALL English financial jargon with Hindi equivalents + everyday analogies:
   - "Bankruptcy" → "दिवालिया — जैसे कोई दुकानदार अपना कर्ज़ न चुका पाए और अदालत में जाए"
   - "Debt" → "कर्ज़"
   - "Creditors" → "कर्ज़दाता (जिन्होंने पैसा उधार दिया)"
   - "Resolution Professional" → "समाधान पेशेवर (जो कंपनी की संपत्ति बेचकर कर्ज़ चुकाने का रास्ता निकालेगा)"
   - "Assets" → "संपत्ति"
   - "Liabilities" → "देनदारी"
3. Use relatable comparisons for large numbers:
   - "47,000 करोड़ — यानी लगभग 60 लाख भारतीय परिवारों की सालाना आमदनी के बराबर"
4. Keep the script 150-200 words (60-90 seconds when spoken)
5. Structure: Hook → What happened → Key numbers → Who is affected → What it means for you → Closing
6. End with "आपके लिए इसका क्या मतलब है" section
7. Tone: Calm, informative, trustworthy — NOT sensationalist"""


async def write_hindi_script(facts: dict, session_id: str = "default") -> VideoScript:
    """Generate a Hindi explainer script from extracted facts.

    Args:
        facts: Structured facts from BreakingIngestor
        session_id: Session ID for audit

    Returns:
        VideoScript with Hindi text and metadata
    """
    with AuditTimer() as timer:
        prompt = f"""Write a Hindi explainer script (60-90 seconds, 150-200 words in Devanagari) for this breaking news:

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
  "script_hindi": "Full Hindi script in Devanagari...",
  "script_transliteration": "Transliteration in Roman script for reference...",
  "estimated_duration_seconds": 75,
  "key_facts_used": ["fact1 from article", "fact2 from article"],
  "analogies_used": ["analogy1 explaining a financial concept", "analogy2"]
}}"""

        response = await call_llm(
            prompt=prompt,
            model=GEMINI_PRO,
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.6,
        )

        try:
            data = parse_json_response(response)
            result = VideoScript(**data)
        except Exception:
            # Fallback: create a basic script
            result = VideoScript(
                script_hindi="नमस्कार दोस्तों। आज एक बड़ी खबर आई है। "
                            + facts.get("what", "एक बड़ी कंपनी ने दिवालिया होने की अर्ज़ी दायर की है।")
                            + " इसका असर बैंकिंग सेक्टर और शेयर बाज़ार पर पड़ सकता है।"
                            + " अधिक जानकारी के लिए Economic Times पढ़ते रहिए।",
                script_transliteration="Namaskaar doston...",
                estimated_duration_seconds=30,
                key_facts_used=[facts.get("what", "")],
                analogies_used=[],
            )

    log_agent_step(
        agent_name="ScriptWriter",
        action="write_hindi_script",
        model_used=GEMINI_PRO,
        input_summary=f"Facts: {facts.get('what', '')[:80]}",
        output_summary=f"Script: {len(result.script_hindi)} chars, ~{result.estimated_duration_seconds}s",
        latency_ms=timer.elapsed_ms,
        session_id=session_id,
    )

    return result
