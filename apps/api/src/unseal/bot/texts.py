"""Every user-facing bot string, in English, Hindi and Tamil.

NATIVE REVIEW NEEDED: the Hindi (`hi`) and Tamil (`ta`) strings were written for the demo and must
be checked by a native reader before launch. RTI terms are not typed here: `{act}`, `{pio}`,
`{first_appeal}`, `{appellate}` and `{bpl}` are filled from the verified glossary
(llm/glossary.json), the same terms the prompts and the PDF use. No fee, deadline or section
number lives here: callers pass them in from the rules engine.
"""

from datetime import date
from functools import cache
from typing import Literal

from unseal.llm.glossary import load_glossary
from unseal.pdf.labels import labels_for

Language = Literal["en", "hi", "ta"]
LANGUAGES: tuple[Language, ...] = ("en", "hi", "ta")
LANGUAGE_BUTTONS: tuple[tuple[Language, str], ...] = (
    ("en", "English"),
    ("hi", "हिन्दी"),
    ("ta", "தமிழ்"),
)
TODAY_WORDS = frozenset({"today", "आज", "இன்று"})
FOOTER_EN = "Prepared with UnSeal. Not legal advice."

# Glossary concept -> placeholder; English wording where the concept name is not the phrase used.
_TERMS = {
    "act": ("Right to Information Act, 2005", "Right to Information Act, 2005"),
    "pio": ("Public Information Officer", "Public Information Officer"),
    "first_appeal": ("first appeal", "first appeal"),
    "appellate": ("appellate authority", "appellate authority"),
    "bpl": ("below poverty line", "below poverty line"),
}

_SAME = "Choose your language.\nअपनी भाषा चुनें।\nஉங்கள் மொழியைத் தேர்ந்தெடுக்கவும்."

TEXTS: dict[str, dict[str, str]] = {
    # ---- start and consent
    "choose_language": {"en": _SAME, "hi": _SAME, "ta": _SAME},
    "privacy": {
        "en": (
            "Before we start, here is how UnSeal handles your data.\n\n"
            "What we store: your language, this chat's id (encrypted), and your case: the office "
            "you write to, your questions, the name and address you give for the application "
            "(encrypted), the PDF we make and your filing dates.\n"
            "Why: only to prepare your application under the {act} and to track its "
            "deadlines.\n"
            "The AI model sees what you describe and your questions, never your name or "
            "address.\n"
            "Delete everything at any time with /delete.\n\n"
            'UnSeal is not legal advice. Tap "I agree" to continue. Nothing is stored until '
            "you do."
        ),
        "hi": (
            "शुरू करने से पहले, UnSeal आपके डेटा के साथ यह करता है।\n\n"
            "हम क्या रखते हैं: आपकी भाषा, इस चैट की आईडी (एन्क्रिप्टेड), और आपका मामला: जिस "
            "कार्यालय को आप लिखते हैं, आपके प्रश्न, आवेदन के लिए दिया गया आपका नाम और पता "
            "(एन्क्रिप्टेड), हमारा बनाया PDF और जमा करने की तारीखें।\n"
            "क्यों: केवल {act} के अंतर्गत आपका आवेदन तैयार करने और उसकी समय-सीमाओं पर नज़र "
            "रखने के लिए।\n"
            "AI मॉडल आपका विवरण और प्रश्न देखता है, आपका नाम या पता कभी नहीं।\n"
            "/delete से कभी भी सब कुछ मिटा दें।\n\n"
            'UnSeal कानूनी सलाह नहीं है। आगे बढ़ने के लिए "मैं सहमत हूँ" दबाएँ। तब तक कुछ भी '
            "संग्रहीत नहीं होता।"
        ),
        "ta": (
            "தொடங்கும் முன், UnSeal உங்கள் தரவை இப்படிக் கையாள்கிறது.\n\n"
            "நாங்கள் சேமிப்பவை: உங்கள் மொழி, இந்த உரையாடலின் அடையாள எண் (மறையாக்கப்பட்டது), "
            "உங்கள் மனு: நீங்கள் எழுதும் அலுவலகம், உங்கள் கேள்விகள், விண்ணப்பத்திற்காக நீங்கள் "
            "தரும் பெயர் மற்றும் முகவரி (மறையாக்கப்பட்டது), நாங்கள் உருவாக்கும் PDF, நீங்கள் "
            "தாக்கல் செய்த தேதிகள்.\n"
            "ஏன்: {act}-ன் கீழ் உங்கள் விண்ணப்பத்தைத் தயாரிக்கவும் அதன் காலக்கெடுக்களைக் "
            "கண்காணிக்கவும் மட்டுமே.\n"
            "AI மாதிரி நீங்கள் விவரிப்பதையும் உங்கள் கேள்விகளையும் மட்டுமே பார்க்கும்; உங்கள் "
            "பெயரையோ முகவரியையோ ஒருபோதும் பார்க்காது.\n"
            "/delete மூலம் எப்போது வேண்டுமானாலும் அனைத்தையும் நீக்கலாம்.\n\n"
            'UnSeal சட்ட ஆலோசனை அல்ல. தொடர "நான் ஒப்புக்கொள்கிறேன்" என்பதைத் தட்டவும். '
            "அதுவரை எதுவும் சேமிக்கப்படாது."
        ),
    },
    "agree": {"en": "I agree", "hi": "मैं सहमत हूँ", "ta": "நான் ஒப்புக்கொள்கிறேன்"},
    # The description goes to the model and names cannot be detected in free text, so ask.
    "describe": {
        "en": (
            "Thank you. Describe your problem in your own words: what happened, which office, "
            "and roughly when. Do not write your name, address or phone number here: you give "
            "those later, and they are never sent to the AI."
        ),
        "hi": (
            "धन्यवाद। अपनी समस्या अपने शब्दों में बताइए: क्या हुआ, कौन-सा कार्यालय, और लगभग कब। "
            "यहाँ अपना नाम, पता या फ़ोन नंबर न लिखें: ये बाद में लिए जाते हैं और AI को कभी नहीं "
            "भेजे जाते।"
        ),
        "ta": (
            "நன்றி. உங்கள் பிரச்சினையை உங்கள் சொந்த வார்த்தைகளில் விவரியுங்கள்: என்ன நடந்தது, "
            "எந்த அலுவலகம், ஏறக்குறைய எப்போது. உங்கள் பெயர், முகவரி அல்லது தொலைபேசி எண்ணை "
            "இங்கே எழுத வேண்டாம்: அவை பின்னர் கேட்கப்படும், AI-க்கு ஒருபோதும் அனுப்பப்படாது."
        ),
    },
    "working": {
        "en": "One moment, I am working on it.",
        "hi": "एक क्षण, मैं इस पर काम कर रहा हूँ।",
        "ta": "ஒரு நிமிடம், இதைத் தயாரித்துக்கொண்டிருக்கிறேன்.",
    },
    "still_working": {
        "en": "Still working on your last message. Please wait.",
        "hi": "आपके पिछले संदेश पर अभी काम चल रहा है। कृपया प्रतीक्षा करें।",
        "ta": "உங்கள் முந்தைய செய்தியில் இன்னும் வேலை நடக்கிறது. சற்றுக் காத்திருக்கவும்.",
    },
    # ---- authority
    "choose_authority": {
        "en": "Which office holds these records? Choose one, or tap Other to type it yourself.",
        "hi": 'ये अभिलेख किस कार्यालय के पास हैं? एक चुनें, या खुद लिखने के लिए "अन्य" दबाएँ।',
        "ta": (
            "இந்த ஆவணங்கள் எந்த அலுவலகத்திடம் உள்ளன? ஒன்றைத் தேர்ந்தெடுக்கவும், அல்லது "
            'நீங்களே எழுத "மற்றவை" என்பதைத் தட்டவும்.'
        ),
    },
    "other": {"en": "Other", "hi": "अन्य", "ta": "மற்றவை"},
    "authority_name": {
        "en": "Type the name of the office (for example, the department and the town).",
        "hi": "कार्यालय का नाम लिखें (जैसे विभाग और शहर)।",
        "ta": "அலுவலகத்தின் பெயரை எழுதவும் (எ.கா. துறை மற்றும் ஊர்).",
    },
    "authority_address": {
        "en": "Type the postal address of that office's {pio}.",
        "hi": "उस कार्यालय के {pio} का डाक पता लिखें।",
        "ta": "அந்த அலுவலகத்தின் {pio} அவர்களின் அஞ்சல் முகவரியை எழுதவும்.",
    },
    "choose_jurisdiction": {
        "en": "Is this a Central Government office or a Tamil Nadu Government office?",
        "hi": "यह केंद्र सरकार का कार्यालय है या तमिलनाडु सरकार का?",
        "ta": "இது மத்திய அரசு அலுவலகமா, தமிழ்நாடு அரசு அலுவலகமா?",
    },
    "jur_central": {"en": "Central Government", "hi": "केंद्र सरकार", "ta": "மத்திய அரசு"},
    "jur_tamil_nadu": {
        "en": "Tamil Nadu Government",
        "hi": "तमिलनाडु सरकार",
        "ta": "தமிழ்நாடு அரசு",
    },
    "confirm_authority": {
        "en": (
            "The application will be addressed to:\n\n{designation}\n{name}\n{address}\n\n"
            "{online}\n\nIs this right?"
        ),
        "hi": (
            "आवेदन इन्हें संबोधित होगा:\n\n{designation}\n{name}\n{address}\n\n{online}\n\nक्या यह सही है?"
        ),
        "ta": (
            "விண்ணப்பம் இவருக்கு அனுப்பப்படும்:\n\n{designation}\n{name}\n{address}\n\n"
            "{online}\n\nஇது சரியா?"
        ),
    },
    "rti_online_yes": {
        "en": "RTI Online: this office accepts online applications.",
        "hi": "RTI ऑनलाइन: यह कार्यालय ऑनलाइन आवेदन स्वीकार करता है।",
        "ta": "RTI ஆன்லைன்: இந்த அலுவலகம் இணைய வழி விண்ணப்பங்களை ஏற்கிறது.",
    },
    "rti_online_no": {
        "en": "RTI Online: not available for this office; file by post or in person.",
        "hi": "RTI ऑनलाइन: इस कार्यालय के लिए उपलब्ध नहीं; डाक से या स्वयं जाकर जमा करें।",
        "ta": "RTI ஆன்லைன்: இந்த அலுவலகத்திற்கு இல்லை; அஞ்சல் மூலம் அல்லது நேரில் தாக்கல் செய்யவும்.",
    },
    "rti_online_unknown": {
        "en": "RTI Online: not checked for this office yet.",
        "hi": "RTI ऑनलाइन: इस कार्यालय के लिए अभी जाँचा नहीं गया।",
        "ta": "RTI ஆன்லைன்: இந்த அலுவலகத்திற்கு இன்னும் சரிபார்க்கப்படவில்லை.",
    },
    "confirm": {"en": "Yes, confirm", "hi": "हाँ, पुष्टि करें", "ta": "ஆம், உறுதிசெய்"},
    "change": {"en": "Change", "hi": "बदलें", "ta": "மாற்று"},
    # ---- questions
    "rewritten": {
        "en": "Your request, rewritten to ask for records:\n\n{text}\n\nWhy: {reason}",
        "hi": "आपका अनुरोध, अभिलेख माँगने के रूप में दोबारा लिखा गया:\n\n{text}\n\nक्यों: {reason}",
        "ta": ("ஆவணங்களைக் கோரும் வகையில் மாற்றி எழுதப்பட்ட உங்கள் கோரிக்கை:\n\n{text}\n\nகாரணம்: {reason}"),
    },
    "personal_info": {
        "en": (
            "Warning: this asks for another person's personal information, which is exempt "
            "from disclosure ({basis}). It will be left out of the application."
        ),
        "hi": (
            "चेतावनी: यह किसी दूसरे व्यक्ति की व्यक्तिगत जानकारी माँगता है, जिसे प्रकट करने से "
            "छूट है ({basis})। इसे आवेदन में शामिल नहीं किया जाएगा।"
        ),
        "ta": (
            "எச்சரிக்கை: இது மற்றொருவரின் தனிப்பட்ட தகவலைக் கோருகிறது; அதை வெளியிடுவதிலிருந்து "
            "விலக்கு உண்டு ({basis}). இது விண்ணப்பத்தில் சேர்க்கப்படாது."
        ),
    },
    "suggestion": {
        "en": "Suggestion: {suggestion}",
        "hi": "सुझाव: {suggestion}",
        "ta": "பரிந்துரை: {suggestion}",
    },
    "accept": {"en": "Accept", "hi": "स्वीकार करें", "ta": "ஏற்கிறேன்"},
    "edit": {"en": "Edit", "hi": "संपादित करें", "ta": "திருத்து"},
    "add": {"en": "Add another question", "hi": "एक और प्रश्न जोड़ें", "ta": "மற்றொரு கேள்வி சேர்"},
    "done": {"en": "Done", "hi": "हो गया", "ta": "முடிந்தது"},
    "accepted": {"en": "Accepted.", "hi": "स्वीकार किया गया।", "ta": "ஏற்கப்பட்டது."},
    "edit_prompt": {
        "en": "Type your version of this question.",
        "hi": "इस प्रश्न का अपना रूप लिखें।",
        "ta": "இந்தக் கேள்வியை நீங்கள் விரும்பும் வடிவில் எழுதவும்.",
    },
    "saved_edit": {
        "en": "Saved your version.",
        "hi": "आपका रूप सहेज लिया गया।",
        "ta": "உங்கள் வடிவம் சேமிக்கப்பட்டது.",
    },
    "add_prompt": {
        "en": "Type your next question.",
        "hi": "अपना अगला प्रश्न लिखें।",
        "ta": "உங்கள் அடுத்த கேள்வியை எழுதவும்.",
    },
    # ---- applicant (never echoed back)
    "ask_name": {
        "en": (
            "Now your details for the application. They are stored encrypted, printed only on "
            "your application, and never sent to the AI model.\n\nWhat is your full name?"
        ),
        "hi": (
            "अब आवेदन के लिए आपका विवरण। यह एन्क्रिप्ट करके रखा जाता है, केवल आपके आवेदन पर "
            "छपता है, और AI मॉडल को कभी नहीं भेजा जाता।\n\nआपका पूरा नाम क्या है?"
        ),
        "ta": (
            "இப்போது விண்ணப்பத்திற்கான உங்கள் விவரங்கள். இவை மறையாக்கம் செய்து சேமிக்கப்படும், "
            "உங்கள் விண்ணப்பத்தில் மட்டுமே அச்சிடப்படும், AI மாதிரிக்கு ஒருபோதும் "
            "அனுப்பப்படாது.\n\nஉங்கள் முழுப் பெயர் என்ன?"
        ),
    },
    "ask_address": {
        "en": "Your postal address? The reply will be sent there.",
        "hi": "आपका डाक पता? उत्तर वहीं भेजा जाएगा।",
        "ta": "உங்கள் அஞ்சல் முகவரி? பதில் அங்கே அனுப்பப்படும்.",
    },
    "ask_bpl": {
        "en": (
            "Do you hold a {bpl} (BPL) card? BPL applicants pay no application fee and attach "
            "a copy of the card."
        ),
        "hi": (
            "क्या आपके पास {bpl} (BPL) का कार्ड है? ऐसे आवेदकों को आवेदन शुल्क नहीं देना होता; "
            "कार्ड की प्रति संलग्न करें।"
        ),
        "ta": (
            "உங்களிடம் {bpl} (BPL) அட்டை உள்ளதா? அத்தகைய விண்ணப்பதாரர்கள் விண்ணப்பக் கட்டணம் "
            "செலுத்தத் தேவையில்லை; அட்டையின் நகலை இணைக்கவும்."
        ),
    },
    "yes": {"en": "Yes", "hi": "हाँ", "ta": "ஆம்"},
    "no": {"en": "No", "hi": "नहीं", "ta": "இல்லை"},
    "ask_payment": {
        "en": "How will you pay the Rs {fee} application fee?",
        "hi": "आप ₹{fee} आवेदन शुल्क कैसे देंगे?",
        "ta": "₹{fee} விண்ணப்பக் கட்டணத்தை எப்படிச் செலுத்துவீர்கள்?",
    },
    "ask_place": {
        "en": "Which town or city are you signing from? It is printed as the place.",
        "hi": "आप किस शहर या कस्बे से हस्ताक्षर कर रहे हैं? यह स्थान के रूप में छपेगा।",
        "ta": "எந்த ஊரில் இருந்து கையொப்பமிடுகிறீர்கள்? இது இடமாக அச்சிடப்படும்.",
    },
    # ---- the application and the checklist
    "pdf_caption": {
        "en": "Your application under the {act}",
        "hi": "{act} के अंतर्गत आपका आवेदन",
        "ta": "{act}-ன் கீழ் உங்கள் விண்ணப்பம்",
    },
    "check_header": {
        "en": "Before you file:",
        "hi": "आवेदन जमा करने से पहले:",
        "ta": "தாக்கல் செய்யும் முன்:",
    },
    "check_sign": {
        "en": "Print the application and sign it.",
        "hi": "आवेदन प्रिंट करके उस पर हस्ताक्षर करें।",
        "ta": "விண்ணப்பத்தை அச்சிட்டு கையொப்பமிடவும்.",
    },
    "check_fee": {
        "en": "Fee: Rs {fee}. Accepted ways to pay: {modes}.",
        "hi": "शुल्क: ₹{fee}। भुगतान के स्वीकार्य माध्यम: {modes}।",
        "ta": "கட்டணம்: ₹{fee}. ஏற்கப்படும் செலுத்தும் முறைகள்: {modes}.",
    },
    "fee_bpl": {
        "en": "No fee ({bpl}).",
        "hi": "कोई शुल्क नहीं ({bpl})।",
        "ta": "கட்டணம் இல்லை ({bpl}).",
    },
    "bpl_copy": {
        "en": "Attach a copy of your BPL card.",
        "hi": "अपने BPL कार्ड की प्रति संलग्न करें।",
        "ta": "உங்கள் BPL அட்டையின் நகலை இணைக்கவும்.",
    },
    "check_send": {
        "en": "Send it to the {pio} at the address on the application. Ways to file: {channels}.",
        "hi": "इसे आवेदन पर लिखे पते पर {pio} को भेजें। जमा करने के तरीके: {channels}।",
        "ta": ("விண்ணப்பத்தில் உள்ள முகவரியில் {pio} அவர்களுக்கு அனுப்பவும். தாக்கல் செய்யும் வழிகள்: {channels}."),
    },
    "check_proof": {
        "en": (
            "Keep proof: the postal receipt or the acknowledgement, and a copy of the application."
        ),
        "hi": "प्रमाण रखें: डाक रसीद या पावती, और आवेदन की एक प्रति।",
        "ta": "சான்று வைத்துக்கொள்ளவும்: அஞ்சல் ரசீது அல்லது ஒப்புகைச் சீட்டு, விண்ணப்பத்தின் ஒரு நகல்.",
    },
    "check_confirm": {
        "en": (
            "Fees and payment modes can differ between offices: confirm with the authority "
            "before you pay."
        ),
        "hi": "शुल्क और भुगतान के माध्यम कार्यालयों में अलग हो सकते हैं: भुगतान से पहले प्राधिकारी से पुष्टि करें।",
        "ta": (
            "கட்டணமும் செலுத்தும் முறைகளும் அலுவலகத்திற்கு அலுவலகம் வேறுபடலாம்: செலுத்தும் "
            "முன் அந்த அலுவலகத்திடம் உறுதிப்படுத்திக்கொள்ளவும்."
        ),
    },
    "channel_rti_online": {
        "en": "RTI Online portal",
        "hi": "RTI ऑनलाइन पोर्टल",
        "ta": "RTI ஆன்லைன் தளம்",
    },
    "channel_post": {"en": "by post", "hi": "डाक से", "ta": "அஞ்சல் மூலம்"},
    "channel_in_person": {"en": "in person", "hi": "स्वयं जाकर", "ta": "நேரில்"},
    # ---- filing and deadlines
    "ask_filed": {
        "en": (
            "When you have filed it, send me the date you filed it as YYYY-MM-DD, or send "
            '"today". I will work out the reply and appeal deadlines.'
        ),
        "hi": (
            'आवेदन जमा करने के बाद, जमा करने की तारीख YYYY-MM-DD के रूप में भेजें, या "आज" '
            "भेजें। मैं उत्तर और अपील की समय-सीमाएँ बता दूँगा।"
        ),
        "ta": (
            "தாக்கல் செய்த பிறகு, தாக்கல் செய்த தேதியை YYYY-MM-DD வடிவில் அனுப்பவும், அல்லது "
            '"இன்று" என்று அனுப்பவும். பதில் மற்றும் மேல்முறையீட்டுக் காலக்கெடுக்களைச் '
            "சொல்கிறேன்."
        ),
    },
    "bad_date": {
        "en": (
            "I could not read that date. Send it as YYYY-MM-DD (for example 2026-10-27), or "
            'send "today".'
        ),
        "hi": 'मैं वह तारीख नहीं पढ़ पाया। इसे YYYY-MM-DD के रूप में भेजें (जैसे 2026-10-27), या "आज" भेजें।',
        "ta": (
            "அந்தத் தேதியைப் படிக்க முடியவில்லை. YYYY-MM-DD வடிவில் அனுப்பவும் "
            '(எ.கா. 2026-10-27), அல்லது "இன்று" என்று அனுப்பவும்.'
        ),
    },
    "future_date": {
        "en": "That date is in the future. Send the date you actually filed it.",
        "hi": "वह तारीख भविष्य की है। वह तारीख भेजें जिस दिन आपने वास्तव में आवेदन जमा किया।",
        "ta": "அந்தத் தேதி எதிர்காலத்தில் உள்ளது. நீங்கள் உண்மையில் தாக்கல் செய்த தேதியை அனுப்பவும்.",
    },
    "ask_mode": {
        "en": "How did you file it?",
        "hi": "आपने आवेदन कैसे जमा किया?",
        "ta": "எப்படித் தாக்கல் செய்தீர்கள்?",
    },
    "mode_rti_online": {
        "en": "Online (RTI Online)",
        "hi": "ऑनलाइन (RTI ऑनलाइन)",
        "ta": "இணைய வழி (RTI ஆன்லைன்)",
    },
    "mode_post": {"en": "By post", "hi": "डाक से", "ta": "அஞ்சல் மூலம்"},
    "mode_in_person": {"en": "In person", "hi": "स्वयं जाकर", "ta": "நேரில்"},
    "deadlines": {
        "en": (
            "Recorded. You filed it on {filed}.\n\n"
            "Last day for the {pio} to reply: {pio_reply}.\n"
            "If there is no reply, or the reply is not enough, last day to file the "
            "{first_appeal}: {appeal}."
        ),
        "hi": (
            "दर्ज कर लिया। आपने {filed} को आवेदन जमा किया।\n\n"
            "{pio} के उत्तर देने की अंतिम तारीख: {pio_reply}।\n"
            "यदि उत्तर न मिले या उत्तर पर्याप्त न हो, तो {first_appeal} दायर करने की अंतिम "
            "तारीख: {appeal}।"
        ),
        "ta": (
            "பதிவு செய்யப்பட்டது. நீங்கள் தாக்கல் செய்த நாள்: {filed}.\n\n"
            "{pio} பதில் அளிக்க வேண்டிய கடைசி நாள்: {pio_reply}.\n"
            "பதில் வராவிட்டாலோ, பதில் போதுமானதாக இல்லாவிட்டாலோ, {first_appeal} செய்ய "
            "வேண்டிய கடைசி நாள்: {appeal}."
        ),
    },
    "estimated": {"en": "(estimated)", "hi": "(अनुमानित)", "ta": "(மதிப்பிடப்பட்டது)"},
    "estimated_note": {
        "en": (
            "Estimated dates assume the office received your application {days} days after "
            "you sent it."
        ),
        "hi": "अनुमानित तारीखें मानती हैं कि कार्यालय को आपका आवेदन भेजने के {days} दिन बाद मिला।",
        "ta": (
            "மதிப்பிடப்பட்ட தேதிகள், நீங்கள் அனுப்பி {days} நாட்களுக்குப் பிறகு அலுவலகம் "
            "விண்ணப்பத்தைப் பெற்றதாகக் கொள்கின்றன."
        ),
    },
    # ---- /cases
    "no_cases": {
        "en": "You have no cases yet. Send /start to begin.",
        "hi": "आपका अभी कोई मामला नहीं है। शुरू करने के लिए /start भेजें।",
        "ta": "உங்களுக்கு இன்னும் மனு எதுவும் இல்லை. தொடங்க /start அனுப்பவும்.",
    },
    "cases_header": {"en": "Your cases:", "hi": "आपके मामले:", "ta": "உங்கள் மனுக்கள்:"},
    "case_line": {
        "en": "{n}. {authority}: {status}",
        "hi": "{n}. {authority}: {status}",
        "ta": "{n}. {authority}: {status}",
    },
    "case_next": {
        "en": "   Next: {kind}, last day {date}",
        "hi": "   अगला: {kind}, अंतिम तारीख {date}",
        "ta": "   அடுத்தது: {kind}, கடைசி நாள் {date}",
    },
    "no_authority": {
        "en": "(office not chosen yet)",
        "hi": "(कार्यालय अभी नहीं चुना गया)",
        "ta": "(அலுவலகம் இன்னும் தேர்ந்தெடுக்கப்படவில்லை)",
    },
    "status_draft": {"en": "Draft", "hi": "मसौदा", "ta": "வரைவு"},
    "status_filed": {"en": "Filed", "hi": "जमा किया गया", "ta": "தாக்கல் செய்யப்பட்டது"},
    "status_reply_due": {
        "en": "Waiting for the reply",
        "hi": "उत्तर की प्रतीक्षा",
        "ta": "பதிலுக்காகக் காத்திருக்கிறது",
    },
    "status_replied": {"en": "Reply received", "hi": "उत्तर मिला", "ta": "பதில் கிடைத்தது"},
    "status_deemed_refused": {
        "en": "No reply in time (deemed refused)",
        "hi": "समय पर उत्तर नहीं (अस्वीकृत माना गया)",
        "ta": "காலத்தில் பதில் இல்லை (மறுக்கப்பட்டதாகக் கருதப்படும்)",
    },
    "status_appealed": {"en": "Appealed", "hi": "अपील की गई", "ta": "மேல்முறையீடு செய்யப்பட்டது"},
    "status_closed": {"en": "Closed", "hi": "बंद", "ta": "முடிக்கப்பட்டது"},
    "kind_pio_reply": {
        "en": "reply from the {pio}",
        "hi": "{pio} का उत्तर",
        "ta": "{pio} அவர்களின் பதில்",
    },
    "kind_first_appeal": {"en": "{first_appeal}", "hi": "{first_appeal}", "ta": "{first_appeal}"},
    "kind_faa_decision": {
        "en": "decision of the {appellate}",
        "hi": "{appellate} का निर्णय",
        "ta": "{appellate} அவர்களின் முடிவு",
    },
    "kind_second_appeal": {
        "en": "second appeal",
        "hi": "द्वितीय अपील",
        "ta": "இரண்டாம் மேல்முறையீடு",
    },
    # ---- reminders (FR-9): no personal data, only the deadline and its date
    "reminder_ahead": {
        "en": "UnSeal reminder: {kind}, last day {date} ({days} days from today).",
        "hi": "UnSeal अनुस्मारक: {kind}, अंतिम तारीख {date} (आज से {days} दिन बाद)।",
        "ta": "UnSeal நினைவூட்டல்: {kind}, கடைசி நாள் {date} (இன்றிலிருந்து {days} நாட்கள்).",
    },
    "reminder_tomorrow": {
        "en": "UnSeal reminder: {kind}, last day tomorrow, {date}.",
        "hi": "UnSeal अनुस्मारक: {kind}, अंतिम तारीख कल, {date}।",
        "ta": "UnSeal நினைவூட்டல்: {kind}, கடைசி நாள் நாளை, {date}.",
    },
    "reminder_today": {
        "en": "UnSeal reminder: {kind}, last day today, {date}.",
        "hi": "UnSeal अनुस्मारक: {kind}, अंतिम तारीख आज, {date}।",
        "ta": "UnSeal நினைவூட்டல்: {kind}, கடைசி நாள் இன்று, {date}.",
    },
    "reminder_more": {
        "en": "Send /cases to see all your dates.",
        "hi": "अपनी सभी तारीखें देखने के लिए /cases भेजें।",
        "ta": "உங்கள் எல்லாத் தேதிகளையும் பார்க்க /cases அனுப்பவும்.",
    },
    # ---- /delete (FR-8)
    "delete_confirm": {
        "en": (
            "This deletes all your data: your cases, questions, the details you entered and "
            "the PDFs. It cannot be undone. Delete everything?"
        ),
        "hi": (
            "इससे आपका सारा डेटा मिट जाएगा: आपके मामले, प्रश्न, आपके दिए विवरण और PDF। इसे वापस "
            "नहीं लाया जा सकता। सब कुछ मिटा दें?"
        ),
        "ta": (
            "இது உங்கள் எல்லாத் தரவையும் நீக்கும்: உங்கள் மனுக்கள், கேள்விகள், நீங்கள் தந்த "
            "விவரங்கள், PDF-கள். இதைத் திரும்பப் பெற முடியாது. அனைத்தையும் நீக்கவா?"
        ),
    },
    "delete_yes": {
        "en": "Yes, delete everything",
        "hi": "हाँ, सब मिटा दें",
        "ta": "ஆம், அனைத்தையும் நீக்கு",
    },
    "delete_no": {"en": "No, keep it", "hi": "नहीं, रहने दें", "ta": "இல்லை, வைத்திரு"},
    "deleted": {
        "en": "Done. All your data is deleted. Send /start if you want to begin again.",
        "hi": "हो गया। आपका सारा डेटा मिटा दिया गया। फिर से शुरू करने के लिए /start भेजें।",
        "ta": "முடிந்தது. உங்கள் எல்லாத் தரவும் நீக்கப்பட்டது. மீண்டும் தொடங்க /start அனுப்பவும்.",
    },
    "kept": {
        "en": "Nothing was deleted.",
        "hi": "कुछ भी नहीं मिटाया गया।",
        "ta": "எதுவும் நீக்கப்படவில்லை.",
    },
    "nothing_stored": {
        "en": "Nothing is stored for this chat.",
        "hi": "इस चैट के लिए कुछ भी संग्रहीत नहीं है।",
        "ta": "இந்த உரையாடலுக்கு எதுவும் சேமிக்கப்படவில்லை.",
    },
    # ---- errors and guidance
    "busy": {
        "en": "The AI service is busy right now. Please try again in a minute.",
        "hi": "AI सेवा अभी व्यस्त है। कृपया एक मिनट बाद फिर कोशिश करें।",
        "ta": "AI சேவை இப்போது பரபரப்பாக உள்ளது. ஒரு நிமிடம் கழித்து மீண்டும் முயலவும்.",
    },
    "rephrase": {
        "en": "I could not make sense of that well enough. Could you say it again in other words?",
        "hi": "मैं इसे ठीक से समझ नहीं पाया। क्या आप इसे दूसरे शब्दों में फिर से कह सकते हैं?",
        "ta": "அதைச் சரியாகப் புரிந்துகொள்ள முடியவில்லை. வேறு வார்த்தைகளில் மீண்டும் சொல்ல முடியுமா?",
    },
    "incomplete": {
        "en": "My answer was cut off. Tap Retry to try again.",
        "hi": 'मेरा उत्तर बीच में कट गया। फिर से कोशिश करने के लिए "फिर से कोशिश करें" दबाएँ।',
        "ta": 'என் பதில் பாதியில் நின்றுவிட்டது. மீண்டும் முயல "மீண்டும் முயல்" என்பதைத் தட்டவும்.',
    },
    "retry": {"en": "Retry", "hi": "फिर से कोशिश करें", "ta": "மீண்டும் முயல்"},
    "try_again": {
        "en": "Something went wrong while preparing the application. Please try again.",
        "hi": "आवेदन तैयार करते समय कुछ गड़बड़ हुई। कृपया फिर से कोशिश करें।",
        "ta": "விண்ணப்பத்தைத் தயாரிக்கும்போது ஏதோ தவறு நடந்தது. மீண்டும் முயலவும்.",
    },
    "rate_limited": {
        "en": "You are sending requests too quickly. Please wait a minute and try again.",
        "hi": "आप बहुत जल्दी-जल्दी अनुरोध भेज रहे हैं। कृपया एक मिनट रुककर फिर कोशिश करें।",
        "ta": "மிக விரைவாகக் கோரிக்கைகளை அனுப்புகிறீர்கள். ஒரு நிமிடம் காத்திருந்து மீண்டும் முயலவும்.",
    },
    "blocked": {
        "en": "The application cannot be made yet. Missing:\n{items}",
        "hi": "आवेदन अभी नहीं बन सकता। कमी:\n{items}",
        "ta": "விண்ணப்பத்தை இன்னும் உருவாக்க முடியாது. இல்லாதவை:\n{items}",
    },
    "flag_missing_pio_address": {
        "en": "the address of the {pio}",
        "hi": "{pio} का पता",
        "ta": "{pio} அவர்களின் முகவரி",
    },
    "flag_missing_applicant_address": {"en": "your address", "hi": "आपका पता", "ta": "உங்கள் முகவரி"},
    "flag_no_questions": {
        "en": (
            "at least one question that asks for records (a question about another person's "
            "personal information is left out)"
        ),
        "hi": (
            "कम से कम एक प्रश्न जो अभिलेख माँगता हो (किसी दूसरे व्यक्ति की व्यक्तिगत जानकारी वाला "
            "प्रश्न शामिल नहीं होता)"
        ),
        "ta": (
            "ஆவணங்களைக் கோரும் குறைந்தது ஒரு கேள்வி (மற்றொருவரின் தனிப்பட்ட தகவல் பற்றிய கேள்வி சேர்க்கப்படாது)"
        ),
    },
    "flag_other": {
        "en": "a required detail",
        "hi": "एक आवश्यक विवरण",
        "ta": "தேவையான ஒரு விவரம்",
    },
    "error": {
        "en": "Something went wrong on our side. Please try again, or send /start to begin again.",
        "hi": "हमारी ओर से कुछ गड़बड़ हुई। कृपया फिर से कोशिश करें, या दोबारा शुरू करने के लिए /start भेजें।",
        "ta": "எங்கள் பக்கம் ஏதோ தவறு நடந்தது. மீண்டும் முயலவும், அல்லது மீண்டும் தொடங்க /start அனுப்பவும்.",
    },
    "need_start": {
        "en": "Send /start to begin.",
        "hi": "शुरू करने के लिए /start भेजें।",
        "ta": "தொடங்க /start அனுப்பவும்.",
    },
    "use_buttons": {
        "en": "Please reply with text, or use the buttons above.",
        "hi": "कृपया लिखकर उत्तर दें, या ऊपर दिए गए बटन इस्तेमाल करें।",
        "ta": "எழுத்தில் பதில் அளிக்கவும், அல்லது மேலே உள்ள பொத்தான்களைப் பயன்படுத்தவும்.",
    },
    "stale": {
        "en": "This button is no longer active.",
        "hi": "यह बटन अब सक्रिय नहीं है।",
        "ta": "இந்தப் பொத்தான் இப்போது செயலில் இல்லை.",
    },
    "not_found": {
        "en": "That case no longer exists. Send /start to begin a new one.",
        "hi": "वह मामला अब मौजूद नहीं है। नया शुरू करने के लिए /start भेजें।",
        "ta": "அந்த மனு இப்போது இல்லை. புதியதைத் தொடங்க /start அனுப்பவும்.",
    },
    "wrong_status": {
        "en": "This case is already recorded as filed. Send /cases to see its deadlines.",
        "hi": "यह मामला पहले से जमा के रूप में दर्ज है। समय-सीमाएँ देखने के लिए /cases भेजें।",
        "ta": "இந்த மனு ஏற்கெனவே தாக்கல் செய்யப்பட்டதாகப் பதிவாகியுள்ளது. காலக்கெடுக்களைப் பார்க்க /cases அனுப்பவும்.",
    },
    "empty": {
        "en": "Please send some text.",
        "hi": "कृपया कुछ लिखकर भेजें।",
        "ta": "தயவுசெய்து ஏதாவது எழுதி அனுப்பவும்.",
    },
    "too_long": {
        "en": "That is too long. Please keep it under {limit} characters.",
        "hi": "यह बहुत लंबा है। कृपया इसे {limit} अक्षरों से कम रखें।",
        "ta": "இது மிக நீளமாக உள்ளது. {limit} எழுத்துகளுக்குள் வைக்கவும்.",
    },
}


@cache
def _terms(language: Language) -> dict[str, str]:
    if language == "en":
        return {name: english for name, (_, english) in _TERMS.items()}
    by_concept = {entry.concept: entry.local(language).term for entry in load_glossary()}
    return {name: by_concept[concept] for name, (concept, _) in _TERMS.items()}


def language_of(value: object) -> Language:
    """A supported language code; anything else falls back to English."""
    return next((code for code in LANGUAGES if code == value), "en")


def term(name: str, language: str) -> str:
    """A glossary term by placeholder name (`act`, `pio`, `first_appeal`, `appellate`, `bpl`)."""
    return _terms(language_of(language))[name]


def t(key: str, language: str, **values: object) -> str:
    """The text `key` in `language` (English when unsupported), glossary terms and `values`
    filled in. Values are inserted as-is and never re-parsed, so model text with braces is safe."""
    code = language_of(language)
    return TEXTS[key][code].format(**_terms(code), **values)


def label(prefix: str, code: str, language: str) -> str:
    """The text for a code (a case status, a deadline kind), or the code itself if unknown."""
    key = f"{prefix}_{code}"
    return t(key, language) if key in TEXTS else code


def format_date(day: date, language: str) -> str:
    """`3 December 2026`, with the month name in the language (the PDF's month names)."""
    months = labels_for(language_of(language)).months
    return f"{day.day} {months[day.month - 1]} {day.year}"


def footer(language: str) -> str:
    """The "Prepared with UnSeal. Not legal advice." line, in the language when it has one."""
    return labels_for(language_of(language)).footer_local or FOOTER_EN
