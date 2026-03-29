"""Helpers to localize English-heavy event headlines for non-English video outputs."""

import re


def is_english_heavy(text: str) -> bool:
    tokens = re.findall(r"[A-Za-z]{3,}", text or "")
    return len(tokens) > 4


def _infer_event_category(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["dgca", "flight", "airline", "airport", "engine", "aviation"]):
        return "aviation_safety"
    if any(k in t for k in ["bankruptcy", "insolvency", "ibc", "nclt", "default"]):
        return "bankruptcy"
    if any(k in t for k in ["chip", "semiconductor", "atmp", "osat"]):
        return "semiconductor"
    if any(k in t for k in ["rbi", "repo", "rate cut", "inflation"]):
        return "policy"
    return "general"


def localize_event_text(text: str, language: str) -> str:
    """Return a localized event description for non-English pipelines."""
    lang = (language or "hi").lower()
    category = _infer_event_category(text)

    by_lang = {
        "hi": {
            "aviation_safety": "विमानन सुरक्षा से जुड़ी एक बड़ी घटना सामने आई है।",
            "bankruptcy": "एक बड़ी कंपनी के वित्तीय संकट से जुड़ी अहम अपडेट सामने आई है।",
            "semiconductor": "सेमीकंडक्टर निवेश और विनिर्माण से जुड़ी बड़ी कारोबारी खबर सामने आई है।",
            "policy": "नीतिगत फैसले और बाजार पर असर से जुड़ी बड़ी आर्थिक अपडेट सामने आई है।",
            "general": "एक बड़ी कारोबारी घटना पर महत्वपूर्ण अपडेट सामने आई है।",
        },
        "mr": {
            "aviation_safety": "विमान सुरक्षेशी संबंधित मोठी घटना समोर आली आहे.",
            "bankruptcy": "मोठ्या कंपनीच्या आर्थिक ताणाबाबत महत्त्वाचे अपडेट समोर आले आहे.",
            "semiconductor": "सेमिकंडक्टर गुंतवणूक आणि उत्पादनाशी संबंधित मोठे अपडेट आले आहे.",
            "policy": "धोरणात्मक निर्णय आणि बाजार परिणामाबाबत मोठे आर्थिक अपडेट आले आहे.",
            "general": "मोठ्या व्यावसायिक घटनेबाबत महत्त्वाचे अपडेट समोर आले आहे.",
        },
        "bho": {
            "aviation_safety": "विमान सुरक्षा से जुड़ल एक बड़ घटना सामने आइल बा.",
            "bankruptcy": "एक बड़ कंपनी के वित्तीय संकट पर महत्वपूर्ण अपडेट आइल बा.",
            "semiconductor": "सेमीकंडक्टर निवेश आ उत्पादन से जुड़ल बड़ खबर सामने आइल बा.",
            "policy": "नीतिगत फैसला आ बाजार असर से जुड़ल बड़ आर्थिक अपडेट आइल बा.",
            "general": "एक बड़ कारोबारी घटना पर महत्वपूर्ण अपडेट सामने आइल बा.",
        },
        "ta": {
            "aviation_safety": "விமான பாதுகாப்பு தொடர்பான முக்கிய செய்தி வெளியாகியுள்ளது.",
            "bankruptcy": "ஒரு பெரிய நிறுவனத்தின் நிதி நெருக்கடி குறித்து முக்கிய புதுப்பிப்பு வெளியாகியுள்ளது.",
            "semiconductor": "செமிகண்டக்டர் முதலீடு மற்றும் உற்பத்தி குறித்து பெரிய வர்த்தக புதுப்பிப்பு வெளியாகியுள்ளது.",
            "policy": "கொள்கை முடிவுகள் மற்றும் சந்தை தாக்கம் குறித்து பெரிய பொருளாதார புதுப்பிப்பு வெளியாகியுள்ளது.",
            "general": "ஒரு முக்கிய வர்த்தக நிகழ்வுக்கான புதுப்பிப்பு வெளியாகியுள்ளது.",
        },
        "te": {
            "aviation_safety": "విమాన భద్రతకు సంబంధించిన కీలక ఘటన వెలుగులోకి వచ్చింది.",
            "bankruptcy": "పెద్ద కంపెనీ ఆర్థిక ఒత్తిడికి సంబంధించిన ముఖ్య అప్డేట్ వెలువడింది.",
            "semiconductor": "సెమికండక్టర్ పెట్టుబడి మరియు తయారీపై పెద్ద వ్యాపార అప్డేట్ వచ్చింది.",
            "policy": "విధాన నిర్ణయాలు మరియు మార్కెట్ ప్రభావంపై పెద్ద ఆర్థిక అప్డేట్ వచ్చింది.",
            "general": "ఒక ముఖ్య వ్యాపార ఘటనపై తాజా అప్డేట్ వచ్చింది.",
        },
        "kn": {
            "aviation_safety": "ವಿಮಾನ ಸುರಕ್ಷತೆಗೆ ಸಂಬಂಧಿಸಿದ ಪ್ರಮುಖ ಘಟನೆ ಹೊರಬಂದಿದೆ.",
            "bankruptcy": "ದೊಡ್ಡ ಕಂಪನಿಯ ಆರ್ಥಿಕ ಒತ್ತಡದ ಬಗ್ಗೆ ಮಹತ್ವದ ಅಪ್ಡೇಟ್ ಬಂದಿದೆ.",
            "semiconductor": "ಸೆಮಿಕಂಡಕ್ಟರ್ ಹೂಡಿಕೆ ಮತ್ತು ಉತ್ಪಾದನೆ ಕುರಿತು ದೊಡ್ಡ ವ್ಯವಹಾರ ಅಪ್ಡೇಟ್ ಬಂದಿದೆ.",
            "policy": "ಧೋರಣಾ ತೀರ್ಮಾನಗಳು ಮತ್ತು ಮಾರುಕಟ್ಟೆ ಪರಿಣಾಮದ ಬಗ್ಗೆ ದೊಡ್ಡ ಆರ್ಥಿಕ ಅಪ್ಡೇಟ್ ಬಂದಿದೆ.",
            "general": "ಒಂದು ಪ್ರಮುಖ ವ್ಯವಹಾರ ಘಟನೆಯ ಕುರಿತು ಹೊಸ ಅಪ್ಡೇಟ್ ಬಂದಿದೆ.",
        },
        "pa": {
            "aviation_safety": "ਹਵਾਈ ਸੁਰੱਖਿਆ ਨਾਲ ਸੰਬੰਧਿਤ ਇੱਕ ਵੱਡੀ ਘਟਨਾ ਸਾਹਮਣੇ ਆਈ ਹੈ।",
            "bankruptcy": "ਇੱਕ ਵੱਡੀ ਕੰਪਨੀ ਦੇ ਵਿੱਤੀ ਦਬਾਅ ਬਾਰੇ ਮਹੱਤਵਪੂਰਣ ਅਪਡੇਟ ਆਈ ਹੈ।",
            "semiconductor": "ਸੈਮੀਕੰਡਕਟਰ ਨਿਵੇਸ਼ ਅਤੇ ਉਤਪਾਦਨ ਬਾਰੇ ਵੱਡੀ ਕਾਰੋਬਾਰੀ ਅਪਡੇਟ ਆਈ ਹੈ।",
            "policy": "ਨੀਤੀ ਫ਼ੈਸਲਿਆਂ ਅਤੇ ਮਾਰਕੀਟ ਪ੍ਰਭਾਵ ਬਾਰੇ ਵੱਡੀ ਆਰਥਿਕ ਅਪਡੇਟ ਆਈ ਹੈ।",
            "general": "ਇੱਕ ਮਹੱਤਵਪੂਰਣ ਕਾਰੋਬਾਰੀ ਘਟਨਾ ਬਾਰੇ ਅਪਡੇਟ ਸਾਹਮਣੇ ਆਈ ਹੈ।",
        },
    }

    lang_map = by_lang.get(lang, by_lang["hi"])
    return lang_map.get(category, lang_map["general"])
