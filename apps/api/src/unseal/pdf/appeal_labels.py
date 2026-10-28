"""Fixed strings of the first appeal letter in English, Hindi and Tamil.

The Act name, the Public Information Officer, "first appeal", "appellate authority" and "public
authority" come from the verified glossary (llm/glossary.json), the terms the prompts teach the
model. The closing, signature, date and place labels, the month names and the local footer are the
application's own (labels.py), so the two letters always match. Every other string here is a fixed
template string written once; a native reader should review the Hindi and Tamil ones before the
public demo.

No section number, deadline or fee lives here. The title and the no-reply ground keep a `{section}`
slot that the renderer fills from rules/data/rti_act.json.
"""

from dataclasses import dataclass
from functools import cache

from unseal.pdf.labels import ACT, OFFICER, Language, glossary_term, labels_for

FIRST_APPEAL = "first appeal"  # glossary concept names
APPELLATE = "appellate authority"
PUBLIC_AUTHORITY = "public authority"

_EN_TERMS = {
    FIRST_APPEAL: "first appeal",
    APPELLATE: "Appellate Authority",
    PUBLIC_AUTHORITY: "public authority",
}


def _term(concept: str, language: Language) -> str:
    if language == "en" and concept in _EN_TERMS:
        return _EN_TERMS[concept]
    return glossary_term(concept, language)


@dataclass(frozen=True)
class AppealLabels:
    """Everything the appeal template prints that is not the appellant's own text."""

    title: str  # keeps a {section} slot: the first appeal section, from the rules
    to: str
    authority: str  # the First Appellate Authority
    officer: str
    appellant: str
    respondent: str
    particulars: str
    filed_on: str
    filing_mode: str
    filing_modes: dict[str, str]  # one per FilingMode code in pdf/models.py
    received_on: str
    estimated: str
    reply_due_on: str
    reply_received_on: str
    reply: str
    no_reply: str
    grounds_heading: str
    grounds: dict[str, str]  # one per Ground code; no_reply keeps a {section} slot (deemed refusal)
    details: str
    relief_heading: str
    relief: str
    delay_heading: str
    delay: str
    closing: str
    signature: str
    address: str
    date: str
    place: str
    months: tuple[str, ...]
    footer_local: str | None  # the footer in the document language; English is always printed


_EN = {
    "title": "First appeal under Section {section} of the {act}",
    "authority": "First {appellate}",
    "appellant": "Appellant",
    "respondent": "Respondent",
    "particulars": "Particulars of the application",
    "filed_on": "Application filed on",
    "filing_mode": "Mode of filing",
    "received_on": "Received by the {public_authority} on",
    "estimated": "estimated",
    "reply_due_on": "Reply was due by",
    "reply_received_on": "Reply received on",
    "reply": "Reply",
    "no_reply": "No reply was received",
    "grounds_heading": "Grounds of appeal",
    "details": "Details",
    "relief_heading": "Relief sought",
    "relief": "I request that the {officer} be directed to provide the information sought in my "
    "application.",
    "delay_heading": "Delay in filing",
    "delay": "This {first_appeal} is filed after the time limit. I request that the delay be "
    "condoned, as I was prevented by sufficient cause from filing it in time.",
}
_EN_FILING = {
    "rti_online": "Online, on the RTI portal",
    "post": "By post",
    "in_person": "In person",
}
_EN_GROUNDS = {
    "no_reply": "No information was provided within the time limit, so the request is deemed to "
    "have been refused under Section {section} of the Act.",
    "incomplete": "The information provided is incomplete, or is not the information that was "
    "asked for.",
    "refused": "The request was refused without a valid reason.",
    "fee_demanded": "A fee was demanded that, in my view, is not payable.",
}

# Native review needed: every Hindi string in _HI, _HI_FILING and _HI_GROUNDS below.
_HI = {
    "title": "{act} की धारा {section} के अंतर्गत {first_appeal}",
    "authority": "प्रथम {appellate}",
    "appellant": "अपीलार्थी",
    "respondent": "प्रत्यर्थी",
    "particulars": "आवेदन का विवरण",
    "filed_on": "आवेदन प्रस्तुत करने की तिथि",
    "filing_mode": "आवेदन प्रस्तुत करने का माध्यम",
    "received_on": "{public_authority} को प्राप्त होने की तिथि",
    "estimated": "अनुमानित",
    "reply_due_on": "उत्तर देने की अंतिम तिथि",
    "reply_received_on": "उत्तर प्राप्त होने की तिथि",
    "reply": "उत्तर",
    "no_reply": "कोई उत्तर प्राप्त नहीं हुआ",
    "grounds_heading": "अपील के आधार",
    "details": "अतिरिक्त विवरण",
    "relief_heading": "माँगी गई राहत",
    "relief": "अनुरोध है कि {officer} को मेरे आवेदन में माँगी गई सूचना उपलब्ध कराने का निर्देश दिया जाए।",
    "delay_heading": "अपील प्रस्तुत करने में विलंब",
    "delay": "यह {first_appeal} निर्धारित समय-सीमा के बाद प्रस्तुत की जा रही है। अनुरोध है कि "
    "विलंब को क्षमा किया जाए, क्योंकि पर्याप्त कारण से समय पर अपील प्रस्तुत करना संभव नहीं हो सका।",
}
_HI_FILING = {
    "rti_online": "आरटीआई ऑनलाइन पोर्टल द्वारा",
    "post": "डाक द्वारा",
    "in_person": "व्यक्तिगत रूप से",
}
_HI_GROUNDS = {
    "no_reply": "निर्धारित समय-सीमा के भीतर कोई सूचना नहीं दी गई, अतः अधिनियम की धारा {section} "
    "के अंतर्गत अनुरोध को अस्वीकार किया गया माना जाता है।",
    "incomplete": "दी गई सूचना अधूरी है, अथवा वह सूचना नहीं है जो माँगी गई थी।",
    "refused": "अनुरोध को बिना किसी वैध कारण के अस्वीकार किया गया।",
    "fee_demanded": "ऐसा शुल्क माँगा गया जो मेरे विचार में देय नहीं है।",
}

# Native review needed: every Tamil string in _TA, _TA_FILING and _TA_GROUNDS below.
_TA = {
    "title": "{act} பிரிவு {section}-இன் கீழ் {first_appeal}",
    "authority": "முதல் {appellate}",
    "appellant": "மேல்முறையீட்டாளர்",
    "respondent": "எதிர்மனுதாரர்",
    "particulars": "விண்ணப்ப விவரங்கள்",
    "filed_on": "விண்ணப்பம் தாக்கல் செய்த நாள்",
    "filing_mode": "தாக்கல் செய்த முறை",
    "received_on": "{public_authority} பெற்ற நாள்",
    "estimated": "மதிப்பிடப்பட்டது",
    "reply_due_on": "பதில் அளிக்க வேண்டிய கடைசி நாள்",
    "reply_received_on": "பதில் கிடைத்த நாள்",
    "reply": "பதில்",
    "no_reply": "பதில் எதுவும் கிடைக்கவில்லை",
    "grounds_heading": "மேல்முறையீட்டுக்கான காரணங்கள்",
    "details": "கூடுதல் விவரங்கள்",
    "relief_heading": "கோரும் நிவாரணம்",
    "relief": "எனது விண்ணப்பத்தில் கோரப்பட்ட தகவல்களை {officer} வழங்குமாறு உத்தரவிட வேண்டுமெனக் "
    "கேட்டுக்கொள்கிறேன்.",
    "delay_heading": "தாக்கல் செய்வதில் தாமதம்",
    "delay": "இந்த {first_appeal} உரிய காலக்கெடு கடந்த பின் தாக்கல் செய்யப்படுகிறது. போதுமான "
    "காரணத்தால் உரிய காலத்தில் தாக்கல் செய்ய இயலவில்லை; எனவே தாமதத்தை மன்னித்து ஏற்குமாறு "
    "கேட்டுக்கொள்கிறேன்.",
}
_TA_FILING = {
    "rti_online": "இணையதளம் வழியாக",
    "post": "அஞ்சல் மூலம்",
    "in_person": "நேரில்",
}
_TA_GROUNDS = {
    "no_reply": "உரிய காலக்கெடுவுக்குள் எந்தத் தகவலும் வழங்கப்படவில்லை; எனவே சட்டத்தின் பிரிவு "
    "{section}-இன் கீழ் கோரிக்கை மறுக்கப்பட்டதாகக் கருதப்படுகிறது.",
    "incomplete": "வழங்கப்பட்ட தகவல் முழுமையற்றது, அல்லது கோரப்பட்ட தகவல் அல்ல.",
    "refused": "சரியான காரணம் எதுவும் இன்றி கோரிக்கை மறுக்கப்பட்டது.",
    "fee_demanded": "என் கருத்தில் செலுத்த வேண்டியதில்லாத கட்டணம் கோரப்பட்டது.",
}

_TABLES = {
    "en": (_EN, _EN_FILING, _EN_GROUNDS),
    "hi": (_HI, _HI_FILING, _HI_GROUNDS),
    "ta": (_TA, _TA_FILING, _TA_GROUNDS),
}


@cache
def appeal_labels_for(language: Language) -> AppealLabels:
    text, filing, grounds = _TABLES[language]
    terms = {
        "act": glossary_term(ACT, language),
        "officer": glossary_term(OFFICER, language),
        "first_appeal": _term(FIRST_APPEAL, language),
        "appellate": _term(APPELLATE, language),
        "public_authority": _term(PUBLIC_AUTHORITY, language),
        "section": "{section}",  # left as a slot for the renderer
    }
    base = labels_for(language)
    return AppealLabels(
        to=base.to,
        officer=terms["officer"],
        filing_modes=dict(filing),
        grounds={code: sentence.format(**terms) for code, sentence in grounds.items()},
        closing=base.closing,
        signature=base.signature,
        address=base.address,
        date=base.date,
        place=base.place,
        months=base.months,
        footer_local=base.footer_local,
        **{key: value.format(**terms) for key, value in text.items()},
    )
