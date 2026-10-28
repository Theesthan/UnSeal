"""Fixed strings of the second appeal (FR-12) in English, Hindi and Tamil, per format.

The format's own wording lives in cic_labels.py (CIC rule 8 Appendix) and tnsic_labels.py (the
TNSIC form); this module adds what both share: the ground sentences, the delay paragraph and the
labels the application already has (months, footer, date, place, address).

No section number lives in any of these strings. They keep slots that the renderer fills from
rules/data/rti_act.json: {request} (the request section), {transfer}, {deemed_refusal},
{first_appeal}, {faa_decision} and {second_appeal}. Dates, names and blanks are slots too
({date}, {name}, ...).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Literal

from unseal.pdf.appeal_labels import appeal_labels_for
from unseal.pdf.cic_labels import CIC_ENCLOSURES, CIC_SIGN, CIC_TEXT
from unseal.pdf.labels import ACT, OFFICER, Language, glossary_term, labels_for
from unseal.pdf.tnsic_labels import TNSIC_ENCLOSURES, TNSIC_SIGN, TNSIC_TEXT

Format = Literal["cic_rule_8", "tnsic_form"]
PUBLIC_AUTHORITY = "public authority"  # glossary concept

# The two grounds the first appeal does not have. The other four reuse the first appeal's
# sentences (appeal_labels.py), so both letters say the same thing.
# Native review needed: the Hindi and Tamil sentences below.
_NEW_GROUNDS = {
    "en": {
        "no_decision": "The First Appellate Authority did not decide the first appeal within the "
        "time allowed by Section {faa_decision} of the Act.",
        "incorrect": "The information provided is incorrect or misleading.",
    },
    "hi": {
        "no_decision": "प्रथम अपील प्राधिकारी ने अधिनियम की धारा {faa_decision} के अंतर्गत अनुमत "
        "समय के भीतर प्रथम अपील का विनिश्चय नहीं किया।",
        "incorrect": "दी गई सूचना गलत या भ्रामक है।",
    },
    "ta": {
        "no_decision": "சட்டத்தின் பிரிவு {faa_decision}-இன் கீழ் அனுமதிக்கப்பட்ட காலத்திற்குள் "
        "முதல் மேல்முறையீட்டு அலுவலர் முதல் மேல்முறையீட்டை முடிவு செய்யவில்லை.",
        "incorrect": "வழங்கப்பட்ட தகவல் தவறானது அல்லது தவறாக வழிநடத்துவது.",
    },
}
# Native review needed: the Hindi and Tamil delay paragraphs (they follow the first appeal's).
_DELAY = {
    "en": "This second appeal is filed after the time limit. I request that the delay be "
    "condoned, as I was prevented by sufficient cause from filing it in time.",
    "hi": "यह द्वितीय अपील निर्धारित समय-सीमा के बाद प्रस्तुत की जा रही है। अनुरोध है कि विलंब को "
    "क्षमा किया जाए, क्योंकि पर्याप्त कारण से समय पर अपील प्रस्तुत करना संभव नहीं हो सका।",
    "ta": "இந்த இரண்டாம் மேல்முறையீடு உரிய காலக்கெடு கடந்த பின் தாக்கல் செய்யப்படுகிறது. போதுமான "
    "காரணத்தால் உரிய காலத்தில் தாக்கல் செய்ய இயலவில்லை; எனவே தாமதத்தை மன்னித்து ஏற்குமாறு "
    "கேட்டுக்கொள்கிறேன்.",
}


class _Keep(dict[str, str]):
    """For str.format_map: a slot with no value stays a slot, to be filled later."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def fill(template: str, values: Mapping[str, str]) -> str:
    """Fill the slots `values` names and keep every other slot as it is."""
    return template.format_map(_Keep(values))


@dataclass(frozen=True)
class SignLabels:
    """What the shared signature block (templates/_parts.html.j2) reads."""

    closing: str  # blank in both formats: a verification ends in a signature, not a closing
    date: str
    place: str
    signature: str
    address: str
    signer: str


@dataclass(frozen=True)
class SecondAppealLabels:
    text: Mapping[str, str]  # the format's labels and sentences, slots kept
    grounds: Mapping[str, str]  # SecondGround code -> sentence
    enclosures: Mapping[str, str]  # Enclosure code -> line of the list of copies
    filing_modes: Mapping[str, str]
    months: tuple[str, ...]
    footer_local: str | None
    sign: SignLabels


def _terms(language: Language) -> dict[str, str]:
    public_authority = (
        "public authority" if language == "en" else glossary_term(PUBLIC_AUTHORITY, language)
    )
    return {
        "act": glossary_term(ACT, language),
        "officer": glossary_term(OFFICER, language),
        "public_authority": public_authority,
    }


def _grounds(language: Language) -> dict[str, str]:
    first = appeal_labels_for(language).grounds
    return {
        "no_reply": first["no_reply"].replace("{section}", "{deemed_refusal}"),
        "no_decision": _NEW_GROUNDS[language]["no_decision"],
        "refused": first["refused"],
        "incomplete": first["incomplete"],
        "incorrect": _NEW_GROUNDS[language]["incorrect"],
        "fee_demanded": first["fee_demanded"],
    }


@cache
def second_appeal_labels(fmt: Format, language: Language) -> SecondAppealLabels:
    tables = {
        "cic_rule_8": (CIC_TEXT, CIC_ENCLOSURES, CIC_SIGN),
        "tnsic_form": (TNSIC_TEXT, TNSIC_ENCLOSURES, TNSIC_SIGN),
    }
    text_table, enclosure_table, sign_table = tables[fmt]
    terms = _terms(language)
    base = labels_for(language)
    appeal = appeal_labels_for(language)
    shared = {
        "delay": _DELAY[language],
        "filed_on": appeal.filed_on,
        "filing_mode": appeal.filing_mode,
        "received_on": appeal.received_on,
        "estimated": appeal.estimated,
        "reply_due_on": appeal.reply_due_on,
    }
    text = {key: fill(value, terms) for key, value in {**shared, **text_table[language]}.items()}
    sign = sign_table[language]
    return SecondAppealLabels(
        text=MappingProxyType(text),
        grounds=MappingProxyType(_grounds(language)),
        enclosures=MappingProxyType(
            {code: fill(line, terms) for code, line in enclosure_table[language].items()}
        ),
        filing_modes=MappingProxyType(dict(appeal.filing_modes)),
        months=base.months,
        footer_local=base.footer_local,
        sign=SignLabels(
            closing="",
            date=sign.get("date", base.date),
            place=sign.get("place", base.place),
            signature=sign.get("signature", base.signature),
            address=base.address,
            signer=sign["signer"],
        ),
    )
