"""Fixed strings of the application letter in English, Hindi and Tamil.

The Act name, the Public Information Officer title and "below poverty line" come from the verified
glossary (llm/glossary.json), the same terms the prompts teach the model. Every other label and
sentence here is a fixed template string written once; a native reader should review them before
the public demo. No fee, deadline or section number lives here: the fee comes from
rules/data/*.json at render time.
"""

from dataclasses import dataclass
from functools import cache
from typing import Literal

from unseal.llm.glossary import load_glossary

Language = Literal["en", "hi", "ta"]

ACT = "Right to Information Act, 2005"  # glossary concept names
OFFICER = "Public Information Officer"
BPL = "below poverty line"


@dataclass(frozen=True)
class Labels:
    """Everything the template prints that is not the applicant's own text."""

    title: str
    to: str
    officer: str
    salutation: str
    request: str
    subject: str
    fee: str
    fee_amount: str  # keeps a {rupees} slot: the amount is filled in from the rules
    fee_nil: str
    bpl_note: str
    payment_mode: str
    payment_modes: dict[str, str]
    closing: str
    signature: str
    applicant: str
    address: str
    date: str
    place: str
    months: tuple[str, ...]
    footer_local: str | None  # the footer in the document language; English is always printed


_EN_TERMS = {ACT: ACT, OFFICER: "Public Information Officer", BPL: "BPL"}


def glossary_term(concept: str, language: Language) -> str:
    """The fixed term for `concept`: the glossary's Hindi or Tamil term, or the English wording."""
    if language == "en":
        return _EN_TERMS[concept]
    for entry in load_glossary():
        if entry.concept == concept:
            return entry.local(language).term
    raise KeyError(f"glossary has no entry for {concept!r}")


_EN = {
    "title": "Application for information under the {act}",
    "to": "To",
    "salutation": "Sir/Madam,",
    "request": "I request the following information under the {act}:",
    "subject": "Subject",
    "fee": "Application fee",
    "fee_amount": "Rs {rupees}",
    "fee_nil": "Nil ({bpl})",
    "bpl_note": "A copy of my {bpl} certificate is enclosed.",
    "payment_mode": "Payment mode",
    "closing": "Yours faithfully,",
    "signature": "Signature",
    "applicant": "Applicant",
    "address": "Address",
    "date": "Date",
    "place": "Place",
}
_EN_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
# One label per payment mode code that appears in rules/data/*.json (central.json and
# tamil_nadu.json); a unit test fails when a rules file gains a mode that has no label here.
_EN_PAYMENT = {
    "cash": "Cash",
    "demand_draft": "Demand draft",
    "bankers_cheque": "Banker's cheque",
    "indian_postal_order": "Indian Postal Order",
    "electronic": "Electronic payment",
    "court_fee_stamp": "Court fee stamp",
    "postal_money_order": "Postal money order",
}

_HI = {
    "title": "{act} के अंतर्गत सूचना हेतु आवेदन",
    "to": "सेवा में",
    "salutation": "महोदय/महोदया,",
    "request": "{act} के अंतर्गत कृपया निम्नलिखित सूचना उपलब्ध कराई जाए:",
    "subject": "विषय",
    "fee": "आवेदन शुल्क",
    "fee_amount": "₹{rupees}",
    "fee_nil": "शून्य ({bpl})",
    "bpl_note": "{bpl} होने के प्रमाण पत्र की प्रति संलग्न है।",
    "payment_mode": "भुगतान का माध्यम",
    "closing": "भवदीय,",
    "signature": "हस्ताक्षर",
    "applicant": "आवेदक",
    "address": "पता",
    "date": "दिनांक",
    "place": "स्थान",
}
_HI_MONTHS = (
    "जनवरी",
    "फरवरी",
    "मार्च",
    "अप्रैल",
    "मई",
    "जून",
    "जुलाई",
    "अगस्त",
    "सितंबर",
    "अक्टूबर",
    "नवंबर",
    "दिसंबर",
)
_HI_PAYMENT = {
    "cash": "नकद",
    "demand_draft": "डिमांड ड्राफ्ट",
    "bankers_cheque": "बैंकर्स चेक",
    "indian_postal_order": "भारतीय पोस्टल ऑर्डर",
    "electronic": "इलेक्ट्रॉनिक भुगतान",
    # Native review needed: the two Tamil Nadu modes below.
    "court_fee_stamp": "न्यायालय शुल्क टिकट",
    "postal_money_order": "डाक मनीऑर्डर",
}
_HI_FOOTER = "UnSeal द्वारा तैयार किया गया। यह कानूनी सलाह नहीं है।"

_TA = {
    "title": "{act}-ன் கீழ் தகவல் கோரும் விண்ணப்பம்",
    "to": "பெறுநர்",
    "salutation": "ஐயா/அம்மா,",
    "request": "{act}-ன் கீழ் பின்வரும் தகவல்களை வழங்குமாறு கேட்டுக்கொள்கிறேன்:",
    "subject": "பொருள்",
    "fee": "விண்ணப்பக் கட்டணம்",
    "fee_amount": "₹{rupees}",
    "fee_nil": "இல்லை ({bpl})",
    "bpl_note": "{bpl} உள்ளவர் என்பதற்கான சான்றிதழின் நகல் இணைக்கப்பட்டுள்ளது.",
    "payment_mode": "செலுத்தும் முறை",
    "closing": "இப்படிக்கு,",
    "signature": "கையொப்பம்",
    "applicant": "விண்ணப்பதாரர்",
    "address": "முகவரி",
    "date": "நாள்",
    "place": "இடம்",
}
_TA_MONTHS = (
    "ஜனவரி",
    "பிப்ரவரி",
    "மார்ச்",
    "ஏப்ரல்",
    "மே",
    "ஜூன்",
    "ஜூலை",
    "ஆகஸ்ட்",
    "செப்டம்பர்",
    "அக்டோபர்",
    "நவம்பர்",
    "டிசம்பர்",
)
_TA_PAYMENT = {
    "cash": "ரொக்கம்",
    "demand_draft": "வரைவோலை",
    "bankers_cheque": "வங்கி காசோலை",
    "indian_postal_order": "இந்திய அஞ்சல் ஆணை",
    "electronic": "மின்னணு முறை",
    # Native review needed: the two Tamil Nadu modes below. The task brief wrote "அஞ்சல் பண அணை"
    # for postal money order; அணை means a dam, so this uses ஆணை (order), as in the Indian Postal
    # Order label above. Flip it back if a native reader prefers the brief's wording.
    "court_fee_stamp": "நீதிமன்றக் கட்டண வில்லை",
    "postal_money_order": "அஞ்சல் பண ஆணை",
}
_TA_FOOTER = "UnSeal மூலம் தயாரிக்கப்பட்டது. இது சட்ட ஆலோசனை அல்ல."

_TABLES = {
    "en": (_EN, _EN_MONTHS, _EN_PAYMENT, None),
    "hi": (_HI, _HI_MONTHS, _HI_PAYMENT, _HI_FOOTER),
    "ta": (_TA, _TA_MONTHS, _TA_PAYMENT, _TA_FOOTER),
}


@cache
def labels_for(language: Language) -> Labels:
    text, months, payment, footer = _TABLES[language]
    terms = {
        "act": glossary_term(ACT, language),
        "bpl": glossary_term(BPL, language),
    }
    fixed = {
        key: value.format(**terms) if key != "fee_amount" else value for key, value in text.items()
    }
    return Labels(
        officer=glossary_term(OFFICER, language),
        payment_modes=dict(payment),
        months=months,
        footer_local=footer,
        **fixed,
    )
