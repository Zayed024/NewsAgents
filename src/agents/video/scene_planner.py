"""ScenePlanner agent — builds chaptered scene plans for explainer videos."""

import re

from src.llm import call_llm, parse_json_response
from src.config import GEMINI_FLASH
from src.audit import log_agent_step, AuditTimer
from src.models import VideoScene, VideoScenePlan


SYSTEM_INSTRUCTION = """You are a visual story planner for business-news explainers.
Create a clear chapter-based scene plan that feels like a progressing story arc.
Rules:
1. Use 6-10 scenes with meaningful chapter names.
2. Keep on-screen scene text concise (1-3 short lines) but provide richer narration text.
3. Total duration should be close to requested duration.
4. Include at least one timeline/progression scene and one impact scene.
5. Include one contrarian perspective scene and one what-to-watch-next scene.
6. Track sentiment progression through the story.
5. Do not invent unsupported facts.
"""


def _fallback_scene_plan(facts: dict, script_text: str, language: str, target_duration_seconds: int) -> VideoScenePlan:
    is_en = (language or "hi").lower() == "en"
    lang = (language or "hi").lower()
    what = facts.get("what", "Major business update")

    if not is_en and len(re.findall(r"[A-Za-z]{3,}", what or "")) > 4:
        localized_what = {
            "hi": "एक बड़ी इंफ्रास्ट्रक्चर कंपनी के वित्तीय संकट ने कानूनी प्रक्रिया का रूप ले लिया है।",
            "mr": "मोठ्या इन्फ्रास्ट्रक्चर कंपनीचा आर्थिक ताण आता कायदेशीर प्रक्रियेत गेला आहे.",
            "bho": "बड़ इंफ्रास्ट्रक्चर कंपनी के वित्तीय संकट अब कानूनी प्रक्रिया में पहुंच गइल बा.",
            "ta": "பெரிய உள்கட்டமைப்பு நிறுவனத்தின் நிதி நெருக்கடி இப்போது சட்ட செயல்முறைக்கு சென்றுள்ளது.",
            "te": "పెద్ద మౌలిక వసతుల సంస్థ ఆర్థిక ఒత్తిడి ఇప్పుడు చట్టపరమైన ప్రక్రియకు చేరుకుంది.",
            "kn": "ದೊಡ್ಡ ಮೂಲಸೌಕರ್ಯ ಕಂಪನಿಯ ಆರ್ಥಿಕ ಒತ್ತಡ ಇದೀಗ ಕಾನೂನು ಪ್ರಕ್ರಿಯೆಗೆ ಹೋಗಿದೆ.",
            "pa": "ਵੱਡੀ ਢਾਂਚਾਗਤ ਕੰਪਨੀ ਦਾ ਵਿੱਤੀ ਦਬਾਅ ਹੁਣ ਕਾਨੂੰਨੀ ਪ੍ਰਕਿਰਿਆ ਵਿੱਚ ਦਾਖ਼ਲ ਹੋ ਗਿਆ ਹੈ।",
        }
        what = localized_what.get(lang, localized_what["hi"])

    impacts = facts.get("impact_points", [])
    impact_text = "; ".join(impacts[:2]) if impacts else (
        "Watch banking exposure and project continuity" if is_en else "बैंकिंग जोखिम और परियोजना निरंतरता पर नज़र रखें"
    )
    if not is_en and len(re.findall(r"[A-Za-z]{3,}", impact_text or "")) > 4:
        impact_text = "बैंकिंग जोखिम, कर्मचारियों की अनिश्चितता और परियोजनाओं में देरी की संभावना पर ध्यान रखें।"

    if is_en:
        scenes = [
            VideoScene(
                chapter="Chapter 1", heading="The Breaking Update", text=what,
                narration_text=(
                    f"{what} This is a major development for lenders, project stakeholders, and investors. "
                    "In this explainer, we will break down what changed, why it matters, and what signals to track next."
                ),
                sentiment="negative", duration_seconds=12, scene_type="narrative",
            ),
            VideoScene(
                chapter="Chapter 2", heading="What Triggered It", text=facts.get("why", "Debt stress and missed obligations"),
                narration_text=(
                    "The trigger was sustained debt pressure and repeated repayment misses despite restructuring attempts. "
                    "Once liquidity stress persists across quarters, legal insolvency routes become the most likely path."
                ),
                sentiment="negative", duration_seconds=12, scene_type="narrative",
            ),
            VideoScene(
                chapter="Chapter 3", heading="Numbers That Matter", text="Debt, liabilities, and creditor exposure define the risk.",
                narration_text=(
                    "The numbers frame the seriousness: total liabilities, creditor concentration, and exposure to large lenders. "
                    "These figures help estimate recovery stress and ripple effects across related sectors."
                ),
                sentiment="negative", duration_seconds=12, scene_type="numbers",
            ),
            VideoScene(
                chapter="Chapter 4", heading="Story Timeline", text="Default pressure -> legal filing -> creditor process -> resolution path",
                narration_text=(
                    "The storyline moved from financial stress to formal legal filing, and now enters the creditor committee phase. "
                    "From here, the direction depends on resolution bids, project continuity, and timeline discipline."
                ),
                sentiment="neutral", duration_seconds=11, scene_type="timeline",
            ),
            VideoScene(
                chapter="Chapter 5", heading="Contrarian Lens", text="Could restructuring still preserve value?",
                narration_text=(
                    "A contrarian view says not all value is lost if assets remain operational and creditor coordination improves. "
                    "Under disciplined execution, select projects and vendor chains can still stabilize over time."
                ),
                sentiment="neutral", duration_seconds=11, scene_type="contrarian",
            ),
            VideoScene(
                chapter="Chapter 6", heading="Who Gets Impacted", text=impact_text,
                narration_text=(
                    f"Immediate impact zones include lenders, employees, and ongoing project ecosystems. {impact_text} "
                    "For retail investors, risk discipline matters more than headline reaction."
                ),
                sentiment="negative", duration_seconds=11, scene_type="impact",
            ),
            VideoScene(
                chapter="Chapter 7", heading="What To Watch Next", text="Creditor decisions, resolution milestones, and execution updates.",
                narration_text=(
                    "Watch the first creditor committee outcomes, progress on resolution milestones, and signs of project handover stability. "
                    "These signals will likely shape sentiment and valuation direction in the coming weeks."
                ),
                sentiment="cautious", duration_seconds=11, scene_type="watch_next",
            ),
        ]
    elif lang == "mr":
        scenes = [
            VideoScene(chapter="प्रकरण 1", heading="आजचा मोठा अपडेट", text=what, narration_text="ही बातमी बाजार, बँका आणि प्रकल्प साखळीसाठी महत्त्वाचा टर्निंग पॉइंट ठरू शकते.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="प्रकरण 2", heading="स्थिती कशी वाढली", text="कर्जदबाव आणि परतफेडीतील अडथळे", narration_text="दीर्घकाळ चाललेल्या कर्जदबावामुळे कंपनीला कायदेशीर प्रक्रियेकडे जावे लागले.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="प्रकरण 3", heading="महत्त्वाचे आकडे", text="कर्ज, देयके आणि कर्जदारांचा धोका", narration_text="एकाग्र कर्जदार जोखीम आणि मोठे देयक ताण पुढील निर्णयांना आकार देतात.", sentiment="negative", duration_seconds=12, scene_type="numbers"),
            VideoScene(chapter="प्रकरण 4", heading="कथानक टाइमलाइन", text="ताण -> कायदेशीर फाइलिंग -> कर्जदार प्रक्रिया -> निराकरण", narration_text="आता लक्ष कर्जदार समिती, निराकरण प्रस्ताव आणि अंमलबजावणीच्या गतीवर असेल.", sentiment="neutral", duration_seconds=11, scene_type="timeline"),
            VideoScene(chapter="प्रकरण 5", heading="पर्यायी दृष्टीकोन", text="शिस्तबद्ध पुनर्रचनेत मूल्य वाचू शकते", narration_text="काही मालमत्ता आणि प्रकल्प चालू राहिल्यास आंशिक मूल्य संरक्षित होण्याची शक्यता आहे.", sentiment="neutral", duration_seconds=11, scene_type="contrarian"),
            VideoScene(chapter="प्रकरण 6", heading="प्रभाव कुठे", text=impact_text, narration_text="तत्काळ प्रभाव बँका, कर्मचारी आणि चालू प्रकल्पांवर दिसू शकतो.", sentiment="negative", duration_seconds=11, scene_type="impact"),
            VideoScene(chapter="प्रकरण 7", heading="पुढे काय पाहावे", text="कर्जदार समितीचे निर्णय आणि प्रकल्प प्रगती", narration_text="पहिल्या बैठकीतील निर्णय, निराकरणाची वेळ आणि प्रकल्प सातत्य हे महत्त्वाचे संकेत असतील.", sentiment="cautious", duration_seconds=11, scene_type="watch_next"),
        ]
    elif lang == "ta":
        scenes = [
            VideoScene(chapter="அத்தியாயம் 1", heading="முக்கிய புதுப்பிப்பு", text=what, narration_text="இந்த செய்தி சந்தை, வங்கிகள் மற்றும் திட்ட நிறைவேற்றத்துக்கு முக்கிய திருப்பமாக இருக்கலாம்.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="அத்தியாயம் 2", heading="இது எப்படி ஏற்பட்டது", text="கடன் அழுத்தம் மற்றும் தவறிய திருப்பிச் செலுத்தல்", narration_text="நீண்டகால கடன் அழுத்தம் சட்ட செயல்முறையைத் தூண்டியது.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="அத்தியாயம் 3", heading="முக்கிய எண்கள்", text="கடன், பொறுப்புகள், கடனளிப்போர் பாதிப்பு", narration_text="மொத்த பாக்கி மற்றும் கடனளிப்போர் ஒருமுகப்படுதல் அபாயத்தை நிர்ணயிக்கிறது.", sentiment="negative", duration_seconds=12, scene_type="numbers"),
            VideoScene(chapter="அத்தியாயம் 4", heading="கதை நேரவரிசை", text="அழுத்தம் -> சட்ட தாக்கல் -> கடனளிப்போர் செயல்முறை -> தீர்வு", narration_text="அடுத்த கட்டத்தின் வேகம் கடனளிப்போர் முடிவுகள் மற்றும் செயல்பாட்டு தொடர்ச்சியில் உள்ளது.", sentiment="neutral", duration_seconds=11, scene_type="timeline"),
            VideoScene(chapter="அத்தியாயம் 5", heading="மாற்று பார்வை", text="ஒழுங்கான மறுசீரமைப்பு மதிப்பை காக்கலாம்", narration_text="சில செயல்பாட்டு சொத்துகள் இயங்கினால் பகுதி மதிப்பு காக்கப்படும் என்ற மாற்று வாதம் உள்ளது.", sentiment="neutral", duration_seconds=11, scene_type="contrarian"),
            VideoScene(chapter="அத்தியாயம் 6", heading="யாருக்கு தாக்கம்", text=impact_text, narration_text="உடனடி தாக்கம் வங்கிகள், ஊழியர்கள் மற்றும் திட்ட வழங்கல் சங்கிலிகளில் தெரியும்.", sentiment="negative", duration_seconds=11, scene_type="impact"),
            VideoScene(chapter="அத்தியாயம் 7", heading="அடுத்து கவனிக்க", text="கடனளிப்போர் முடிவுகள் மற்றும் திட்ட முன்னேற்றம்", narration_text="முதன்மை சிக்னல்கள்: குழு முடிவுகள், தீர்வு காலக்கட்டம், திட்ட கையளிப்பு முன்னேற்றம்.", sentiment="cautious", duration_seconds=11, scene_type="watch_next"),
        ]
    elif lang == "te":
        scenes = [
            VideoScene(chapter="అధ్యాయం 1", heading="ప్రధాన అప్డేట్", text=what, narration_text="ఈ వార్త బ్యాంకులు, మార్కెట్ మరియు ప్రాజెక్టు అమలుకు కీలక మలుపు కావచ్చు.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="అధ్యాయం 2", heading="ఇది ఎలా జరిగింది", text="రుణ ఒత్తిడి మరియు చెల్లింపు లోపాలు", narration_text="దీర్ఘకాల రుణ ఒత్తిడి సంస్థను చట్టపరమైన మార్గంలోకి నెట్టింది.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="అధ్యాయం 3", heading="కీలక సంఖ్యలు", text="రుణం, బాద్యతలు, రుణదాతల ఎక్స్పోజర్", narration_text="మొత్తం బాద్యతలు మరియు రుణదాతల కేంద్రీకరణ ప్రమాదాన్ని నిర్ణయిస్తాయి.", sentiment="negative", duration_seconds=12, scene_type="numbers"),
            VideoScene(chapter="అధ్యాయం 4", heading="కథ టైమ్‌లైన్", text="ఒత్తిడి -> చట్టపరమైన దాఖలు -> రుణదాతల ప్రక్రియ -> పరిష్కారం", narration_text="తదుపరి దిశ రుణదాతల నిర్ణయాలు మరియు అమలు క్రమశిక్షణపై ఆధారపడుతుంది.", sentiment="neutral", duration_seconds=11, scene_type="timeline"),
            VideoScene(chapter="అధ్యాయం 5", heading="ప్రత్యామ్నాయ దృక్కోణం", text="పునర్వ్యవస్థీకరణలో కొంత విలువ నిలవవచ్చు", narration_text="ఆపరేటింగ్ ఆస్తులు కొనసాగితే భాగిక విలువను కాపాడే అవకాశముంది.", sentiment="neutral", duration_seconds=11, scene_type="contrarian"),
            VideoScene(chapter="అధ్యాయం 6", heading="ఎవరికెంత ప్రభావం", text=impact_text, narration_text="తక్షణ ప్రభావం బ్యాంకులు, ఉద్యోగులు, ప్రాజెక్టు సరఫరా వ్యవస్థలపై పడవచ్చు.", sentiment="negative", duration_seconds=11, scene_type="impact"),
            VideoScene(chapter="అధ్యాయం 7", heading="తరువాత ఏమి చూడాలి", text="రుణదాతల కమిటీ నిర్ణయాలు మరియు ప్రాజెక్టు పురోగతి", narration_text="ముఖ్య సంకేతాలు: తొలి కమిటీ నిర్ణయాలు, పరిష్కార గడువు, హ్యాండోవర్ పురోగతి.", sentiment="cautious", duration_seconds=11, scene_type="watch_next"),
        ]
    elif lang == "kn":
        scenes = [
            VideoScene(chapter="ಅಧ್ಯಾಯ 1", heading="ಮುಖ್ಯ ಅಪ್ಡೇಟ್", text=what, narration_text="ಈ ಸುದ್ದಿ ಬ್ಯಾಂಕುಗಳು, ಮಾರುಕಟ್ಟೆ ಮತ್ತು ಯೋಜನೆಗಳ ನಿರ್ವಹಣೆಗೆ ಮಹತ್ವದ ತಿರುವಾಗಬಹುದು.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="ಅಧ್ಯಾಯ 2", heading="ಪರಿಸ್ಥಿತಿ ಹೇಗೆ ಬೆಳೆದಿತು", text="ಸಾಲದ ಒತ್ತಡ ಮತ್ತು ಮರುಪಾವತಿ ವಿಳಂಬ", narration_text="ನಿರಂತರ ಸಾಲದ ಒತ್ತಡದಿಂದ ಕಾನೂನು ಪ್ರಕ್ರಿಯೆ ಅನಿವಾರ್ಯವಾಯಿತು.", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="ಅಧ್ಯಾಯ 3", heading="ಮುಖ್ಯ ಅಂಕೆಗಳು", text="ಸಾಲ, ಬಾಧ్యత, ಸಾಲದಾರರ ಅನಾವರಣ", narration_text="ಒಟ್ಟು ಬಾಧ్యత ಮತ್ತು ಸಾಲದಾರರ ಕೇಂದ್ರೀಕರಣ ಮುಂದಿನ ಅಪಾಯದ ದಿಕ್ಕು ತೋರಿಸುತ್ತದೆ.", sentiment="negative", duration_seconds=12, scene_type="numbers"),
            VideoScene(chapter="ಅಧ್ಯಾಯ 4", heading="ಕಥೆ ಟೈಮ್‌ಲೈನ್", text="ಒತ್ತಡ -> ಕಾನೂನು ದಾಖಲಾತಿ -> ಸಾಲದಾರರ ಪ್ರಕ್ರಿಯೆ -> ಪರಿಹಾರ", narration_text="ಇನ್ನಷ್ಟು ದಿಕ್ಕು ಸಾಲದಾರರ ತೀರ್ಮಾನಗಳು ಮತ್ತು ಕಾರ್ಯಗತಗೊಳಿಸುವಿಕೆಯ ವೇಗದ ಮೇಲೆ ಇರುತ್ತದೆ.", sentiment="neutral", duration_seconds=11, scene_type="timeline"),
            VideoScene(chapter="ಅಧ್ಯಾಯ 5", heading="ಪರ್ಯಾಯ ದೃಷ್ಟಿಕೋನ", text="ಶಿಸ್ತಿನ ಪುನರ್‌ವ್ಯವಸ್ಥೆಯಿಂದ ಭಾಗಶಃ ಮೌಲ್ಯ ಉಳಿಯಬಹುದು", narration_text="ಚಾಲುವಾಸ್ತಿಗಳು ನಿರಂತರವಾಗಿದ್ದರೆ ಭಾಗಶಃ ಮೌಲ್ಯವನ್ನು ಉಳಿಸುವ ಸಾಧ್ಯತೆ ಇದೆ.", sentiment="neutral", duration_seconds=11, scene_type="contrarian"),
            VideoScene(chapter="ಅಧ್ಯಾಯ 6", heading="ಪ್ರಭಾವ ಎಲ್ಲಿಗೆ", text=impact_text, narration_text="ತಕ್ಷಣದ ಪ್ರಭಾವ ಬ್ಯಾಂಕುಗಳು, ಉದ್ಯೋಗಿಗಳು ಮತ್ತು ಯೋಜನೆ ಸರಪಳಿಗಳಲ್ಲಿ ಕಾಣಬಹುದು.", sentiment="negative", duration_seconds=11, scene_type="impact"),
            VideoScene(chapter="ಅಧ್ಯಾಯ 7", heading="ಮುಂದೆ ಏನು ನೋಡಬೇಕು", text="ಸಾಲದಾರರ ಸಮಿತಿ ತೀರ್ಮಾನಗಳು ಮತ್ತು ಯೋಜನೆ ಪ್ರಗತಿ", narration_text="ಮುಖ್ಯ ಸೂಚನೆಗಳು: ಮೊದಲ ಸಭೆಯ ತೀರ್ಮಾನಗಳು, ಪರಿಹಾರ ಕಾಲಮಾನ, ಯೋಜನೆ ಹಸ್ತಾಂತರ ಪ್ರಗತಿ.", sentiment="cautious", duration_seconds=11, scene_type="watch_next"),
        ]
    elif lang == "pa":
        scenes = [
            VideoScene(chapter="ਅਧਿਆਇ 1", heading="ਵੱਡਾ ਅਪਡੇਟ", text=what, narration_text="ਇਹ ਖ਼ਬਰ ਬੈਂਕਾਂ, ਮਾਰਕੀਟ ਅਤੇ ਪ੍ਰੋਜੈਕਟ ਲੜੀ ਲਈ ਵੱਡਾ ਮੋੜ ਹੋ ਸਕਦੀ ਹੈ।", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="ਅਧਿਆਇ 2", heading="ਇਹ ਹਾਲਤ ਕਿਵੇਂ ਬਣੀ", text="ਕਰਜ਼ ਦਬਾਅ ਅਤੇ ਅਦਾਇਗੀ ਵਿੱਚ ਰੁਕਾਵਟ", narration_text="ਲੰਬੇ ਸਮੇਂ ਦੇ ਕਰਜ਼ ਦਬਾਅ ਨੇ ਕਾਨੂੰਨੀ ਪ੍ਰਕਿਰਿਆ ਨੂੰ ਲਾਜ਼ਮੀ ਬਣਾਇਆ।", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="ਅਧਿਆਇ 3", heading="ਮਹੱਤਵਪੂਰਣ ਅੰਕੜੇ", text="ਕੁੱਲ ਕਰਜ਼ਾ, ਜ਼ਿੰਮੇਵਾਰੀਆਂ, ਕਰਜ਼ਦਾਤਾ ਜੋਖ਼ਮ", narration_text="ਇਹ ਅੰਕੜੇ ਅਗਲੇ ਫ਼ੈਸਲਿਆਂ ਅਤੇ ਜੋਖ਼ਮ ਦੀ ਦਿਸ਼ਾ ਨੂੰ ਨਿਰਧਾਰਤ ਕਰਦੇ ਹਨ।", sentiment="negative", duration_seconds=12, scene_type="numbers"),
            VideoScene(chapter="ਅਧਿਆਇ 4", heading="ਕਹਾਣੀ ਟਾਈਮਲਾਈਨ", text="ਦਬਾਅ -> ਕਾਨੂੰਨੀ ਦਾਖ਼ਲਾ -> ਕਰਜ਼ਦਾਤਾ ਪ੍ਰਕਿਰਿਆ -> ਨਿਪਟਾਰਾ", narration_text="ਹੁਣ ਧਿਆਨ ਕਰਜ਼ਦਾਤਾ ਕਮੇਟੀ ਦੇ ਫ਼ੈਸਲਿਆਂ ਅਤੇ ਅਮਲ ਦੀ ਰਫ਼ਤਾਰ 'ਤੇ ਰਹੇਗਾ।", sentiment="neutral", duration_seconds=11, scene_type="timeline"),
            VideoScene(chapter="ਅਧਿਆਇ 5", heading="ਵਿਕਲਪੀ ਨਜ਼ਰੀਆ", text="ਸੰਯਮਿਤ ਰੀਸਟ੍ਰਕਚਰਿੰਗ ਨਾਲ ਕੁਝ ਮੁੱਲ ਬਚ ਸਕਦਾ ਹੈ", narration_text="ਜੇ ਚਾਲੂ ਸੰਪਤੀਆਂ ਚੱਲਦੀਆਂ ਰਹੀਆਂ ਤਾਂ ਹਿੱਸੇਦਾਰ ਮੁੱਲ ਕੁਝ ਹੱਦ ਤੱਕ ਬਚ ਸਕਦਾ ਹੈ।", sentiment="neutral", duration_seconds=11, scene_type="contrarian"),
            VideoScene(chapter="ਅਧਿਆਇ 6", heading="ਅਸਰ ਕਿਸ 'ਤੇ", text=impact_text, narration_text="ਤੁਰੰਤ ਅਸਰ ਬੈਂਕਾਂ, ਕਰਮਚਾਰੀਆਂ ਅਤੇ ਚੱਲ ਰਹੇ ਪ੍ਰੋਜੈਕਟਾਂ 'ਤੇ ਪੈ ਸਕਦਾ ਹੈ।", sentiment="negative", duration_seconds=11, scene_type="impact"),
            VideoScene(chapter="ਅਧਿਆਇ 7", heading="ਅੱਗੇ ਕੀ ਦੇਖਣਾ", text="ਕਮੇਟੀ ਫ਼ੈਸਲੇ, ਨਿਪਟਾਰੇ ਦੇ ਮਾਈਲਸਟੋਨ, ਪ੍ਰੋਜੈਕਟ ਪ੍ਰਗਤੀ", narration_text="ਮੁੱਖ ਸੰਕੇਤ: ਪਹਿਲੇ ਕਮੇਟੀ ਫ਼ੈਸਲੇ, ਨਿਪਟਾਰੇ ਦੀ ਟਾਈਮਲਾਈਨ ਅਤੇ ਪ੍ਰੋਜੈਕਟ ਹਵਾਲਗੀ ਦੀ ਗਤੀ।", sentiment="cautious", duration_seconds=11, scene_type="watch_next"),
        ]
    elif lang == "bho":
        scenes = [
            VideoScene(chapter="अध्याय 1", heading="बड़ अपडेट", text=what, narration_text="ई खबर बैंक, बाजार आ परियोजना के पूरी चेन खातिर महत्वपूर्ण मोड़ हो सकेला।", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="अध्याय 2", heading="स्थिति कइसे बनल", text="कर्ज दबाव आ भुगतान में चूक", narration_text="लगातार कर्ज दबाव से मामला कानूनी प्रक्रिया तक पहुंच गइल।", sentiment="negative", duration_seconds=12, scene_type="narrative"),
            VideoScene(chapter="अध्याय 3", heading="मुख्य आंकड़ा", text="कुल कर्ज, देनदारी, कर्जदाता जोखिम", narration_text="ई आंकड़ा बतावेला कि आगे जोखिम के दिशा का तरफ जा सकत बा।", sentiment="negative", duration_seconds=12, scene_type="numbers"),
            VideoScene(chapter="अध्याय 4", heading="कहानी टाइमलाइन", text="दबाव -> कानूनी फाइलिंग -> कर्जदाता प्रक्रिया -> समाधान", narration_text="अब नजर कर्जदाता समिति के फैसला आ क्रियान्वयन के रफ्तार पर रही।", sentiment="neutral", duration_seconds=11, scene_type="timeline"),
            VideoScene(chapter="अध्याय 5", heading="विपरीत नजरिया", text="अनुशासित पुनर्गठन से कुछ मूल्य बच सकेला", narration_text="अगर परिचालन संपत्ति चलत रहे त कुछ मूल्य बचल रह सकेला।", sentiment="neutral", duration_seconds=11, scene_type="contrarian"),
            VideoScene(chapter="अध्याय 6", heading="असर कहाँ", text=impact_text, narration_text="तुरंत असर बैंक, कर्मचारी आ चल रहल परियोजना पर देखाई पड़ सकत बा।", sentiment="negative", duration_seconds=11, scene_type="impact"),
            VideoScene(chapter="अध्याय 7", heading="आगे का देखीं", text="समिति फैसला, समाधान माइलस्टोन, परियोजना प्रगति", narration_text="मुख्य संकेत: पहिला समिति फैसला, समाधान के समयसीमा आ परियोजना हस्तांतरण के गति।", sentiment="cautious", duration_seconds=11, scene_type="watch_next"),
        ]
    else:
        scenes = [
            VideoScene(
                chapter="अध्याय 1", heading="आज की बड़ी अपडेट", text=what,
                narration_text=(
                    f"{what} यह खबर बैंकों, परियोजनाओं और निवेशकों के लिए महत्वपूर्ण मोड़ है। "
                    "इस वीडियो में हम समझेंगे कि स्थिति कैसे बनी, असर कहां पड़ेगा और आगे कौन-से संकेत देखने चाहिए।"
                ),
                sentiment="negative", duration_seconds=12, scene_type="narrative",
            ),
            VideoScene(
                chapter="अध्याय 2", heading="यह स्थिति क्यों बनी", text=facts.get("why", "कर्ज़ दबाव और भुगतान में लगातार चूक"),
                narration_text=(
                    "लंबे समय तक कर्ज़ दबाव और किस्त भुगतान में चूक ने स्थिति को कानूनी प्रक्रिया तक पहुंचा दिया। "
                    "जब नकदी प्रवाह कमजोर रहता है और पुनर्गठन सफल नहीं होता, तब जोखिम तेजी से बढ़ता है।"
                ),
                sentiment="negative", duration_seconds=12, scene_type="narrative",
            ),
            VideoScene(
                chapter="अध्याय 3", heading="महत्वपूर्ण आंकड़े", text="कुल कर्ज़, देनदारी और कर्ज़दाता जोखिम कहानी की दिशा तय करेंगे।",
                narration_text=(
                    "मुख्य आंकड़े बताते हैं कि जोखिम कितना गहरा है: कुल देनदारी, बड़े कर्ज़दाताओं का एक्सपोज़र और वसूली की संभावनाएं। "
                    "यही संकेत आगे के निर्णयों और बाजार की धारणा को प्रभावित करते हैं।"
                ),
                sentiment="negative", duration_seconds=12, scene_type="numbers",
            ),
            VideoScene(
                chapter="अध्याय 4", heading="कहानी की टाइमलाइन", text="कर्ज़ दबाव -> कानूनी फाइलिंग -> कर्ज़दाता प्रक्रिया -> समाधान",
                narration_text=(
                    "कहानी की प्रगति साफ है: पहले वित्तीय दबाव बढ़ा, फिर औपचारिक कानूनी फाइलिंग हुई, और अब कर्ज़दाता प्रक्रिया शुरू होगी। "
                    "अगला चरण समाधान प्रस्तावों और क्रियान्वयन की गति पर निर्भर करेगा।"
                ),
                sentiment="neutral", duration_seconds=11, scene_type="timeline",
            ),
            VideoScene(
                chapter="अध्याय 5", heading="विपरीत नजरिया", text="क्या नियंत्रित पुनर्गठन से कुछ मूल्य बच सकता है?",
                narration_text=(
                    "एक विपरीत नजरिया यह कहता है कि अगर परिचालन संपत्तियां चालू रहें और कर्ज़दाता समन्वय बेहतर हो, तो कुछ मूल्य सुरक्षित रह सकता है। "
                    "ऐसे मामलों में क्रियान्वयन अनुशासन सबसे बड़ा अंतर पैदा करता है।"
                ),
                sentiment="neutral", duration_seconds=11, scene_type="contrarian",
            ),
            VideoScene(
                chapter="अध्याय 6", heading="किन पर असर पड़ेगा", text=impact_text,
                narration_text=(
                    f"तुरंत असर बैंकों, कर्मचारियों और चल रही परियोजनाओं पर दिख सकता है। {impact_text} "
                    "खुदरा निवेशकों के लिए इस समय जोखिम प्रबंधन सबसे जरूरी है।"
                ),
                sentiment="negative", duration_seconds=11, scene_type="impact",
            ),
            VideoScene(
                chapter="अध्याय 7", heading="अब आगे क्या देखें", text="कर्ज़दाता समिति के फैसले, समाधान माइलस्टोन और परियोजना प्रगति।",
                narration_text=(
                    "आगे की दिशा तय करने वाले प्रमुख संकेत हैं: कर्ज़दाता समिति के शुरुआती फैसले, समाधान प्रक्रिया की समय-सीमा, और परियोजनाओं का हस्तांतरण। "
                    "इन्हीं संकेतों से आने वाले हफ्तों की धारणा बनेगी।"
                ),
                sentiment="cautious", duration_seconds=11, scene_type="watch_next",
            ),
        ]

    # Scale fallback scenes to target duration.
    total = sum(scene.duration_seconds for scene in scenes) or 1
    scale = max(target_duration_seconds, 70) / total
    for scene in scenes:
        scene.duration_seconds = max(7, int(round(scene.duration_seconds * scale)))

    return VideoScenePlan(
        target_duration_seconds=max(target_duration_seconds, 70),
        scenes=scenes,
        story_arc_summary="Debt stress escalated into legal action and now enters creditor-led resolution.",
        key_players=[facts.get("entities", {}).get("company", "Company"), "Creditors", "Regulators"],
        sentiment_shifts=["Shock", "Risk reassessment", "Cautious monitoring"],
        contrarian_perspective=(
            "Operational assets and disciplined creditor coordination can preserve partial value."
            if is_en else
            "परिचालन संपत्ति और कर्ज़दाता समन्वय से आंशिक मूल्य बचाया जा सकता है।"
        ),
        watch_next=[
            "First creditor committee decisions",
            "Resolution process milestones",
            "Project continuity and handover updates",
        ] if is_en else [
            "कर्ज़दाता समिति के शुरुआती फैसले",
            "समाधान प्रक्रिया के माइलस्टोन",
            "परियोजना प्रगति और हस्तांतरण अपडेट",
        ],
    )


async def plan_scenes(
    facts: dict,
    script_text: str,
    language: str = "hi",
    target_duration_seconds: int = 90,
    session_id: str = "default",
) -> VideoScenePlan:
    """Generate a chaptered scene plan for the video composer."""
    with AuditTimer() as timer:
        prompt = f"""Build a chaptered scene plan for a news explainer video.

Language: {language}
Target total duration (seconds): {target_duration_seconds}

FACTS:
- What: {facts.get('what', '')}
- Who: {facts.get('who', '')}
- When: {facts.get('when', '')}
- Why: {facts.get('why', '')}
- Key numbers: {facts.get('key_numbers', [])}
- Impact points: {facts.get('impact_points', [])}

SCRIPT:
{script_text}

Return strict JSON:
{{
  "target_duration_seconds": {target_duration_seconds},
    "story_arc_summary": "One-line summary of evolving story arc",
    "key_players": ["player 1", "player 2"],
    "sentiment_shifts": ["phase 1 sentiment", "phase 2 sentiment"],
    "contrarian_perspective": "A plausible alternative interpretation based on source facts",
    "watch_next": ["signal 1", "signal 2", "signal 3"],
  "scenes": [
    {{
      "chapter": "Chapter/अध्याय label",
      "heading": "Scene heading",
      "text": "1-3 short lines for on-screen narrative",
            "narration_text": "Detailed voiceover text for this scene (35-55 words)",
            "visual_hint": "Suggested visual cue for this scene",
            "sentiment": "negative|neutral|cautious|positive",
      "duration_seconds": 10,
      "scene_type": "narrative"
    }}
  ]
}}
"""

        try:
            response = await call_llm(
                prompt=prompt,
                model=GEMINI_FLASH,
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,
            )
            data = parse_json_response(response)
            result = VideoScenePlan(
                target_duration_seconds=int(data.get("target_duration_seconds", target_duration_seconds)),
                scenes=[VideoScene(**scene) for scene in data.get("scenes", [])],
                story_arc_summary=data.get("story_arc_summary", ""),
                key_players=data.get("key_players", []),
                sentiment_shifts=data.get("sentiment_shifts", []),
                contrarian_perspective=data.get("contrarian_perspective", ""),
                watch_next=data.get("watch_next", []),
            )
            if len(result.scenes) < 4:
                raise ValueError("Scene plan too short")
            status = "success"
        except Exception:
            result = _fallback_scene_plan(facts, script_text, language, target_duration_seconds)
            status = "fallback"

    log_agent_step(
        agent_name="ScenePlanner",
        action="plan_scenes",
        model_used=GEMINI_FLASH,
        input_summary=f"Lang: {language}, target: {target_duration_seconds}s",
        output_summary=f"Scenes: {len(result.scenes)}, total target: {result.target_duration_seconds}s",
        latency_ms=timer.elapsed_ms,
        status=status,
        session_id=session_id,
    )

    return result
