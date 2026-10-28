"""The application template (pure Jinja2, runs anywhere): labels, escaping, no official look.

Real PDF rendering needs WeasyPrint's system libraries and is covered in tests/pdf.
"""

import json
import re
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from typing import Literal
from urllib.request import url2pathname

import pytest
from pydantic import ValidationError

from unseal.llm.glossary import load_glossary
from unseal.pdf.labels import labels_for
from unseal.pdf.models import ApplicationDocument
from unseal.pdf.render import render_application_html
from unseal.rules.engine import Rules, load_rules

Language = Literal["en", "hi", "ta"]
LANGUAGES: list[Language] = ["en", "hi", "ta"]

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "golden" / "pdf" / "cases.json").read_text("utf-8")
)

FOOTER_EN = "Prepared with UnSeal. Not legal advice."
FOOTER_LOCAL = {
    "hi": "UnSeal द्वारा तैयार किया गया। यह कानूनी सलाह नहीं है।",
    "ta": "UnSeal மூலம் தயாரிக்கப்பட்டது. இது சட்ட ஆலோசனை அல்ல.",
}
LABELS = {
    "en": [
        "To",
        "Subject",
        "Applicant",
        "Address",
        "Date",
        "Place",
        "Application fee",
        "Signature",
    ],
    "hi": ["सेवा में", "विषय", "आवेदक", "पता", "दिनांक", "स्थान", "आवेदन शुल्क", "हस्ताक्षर"],
    "ta": [
        "பெறுநர்",
        "பொருள்",
        "விண்ணப்பதாரர்",
        "முகவரி",
        "நாள்",
        "இடம்",
        "விண்ணப்பக் கட்டணம்",
        "கையொப்பம்",
    ],
}
EM_DASH = chr(0x2014)  # built from its code point so this file has none itself
DATE_TEXT = {"en": "27 October 2026", "hi": "27 अक्टूबर 2026", "ta": "27 அக்டோபர் 2026"}


def case(language: Language, **changes: object) -> ApplicationDocument:
    return ApplicationDocument.model_validate({**CASES[language], **changes})


class _Page(HTMLParser):
    """Visible text (no CSS, no <title>) plus the text of each <li>."""

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.items: list[str] = []
        self._skip = 0
        self._item: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "title"}:
            self._skip += 1
        elif tag == "li":
            self._item = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "title"}:
            self._skip -= 1
        elif tag == "li" and self._item is not None:
            self.items.append(" ".join("".join(self._item).split()))
            self._item = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self.text.append(data)
        if self._item is not None:
            self._item.append(data)


def parse(html: str) -> _Page:
    page = _Page()
    page.feed(html)
    return page


def visible(html: str) -> str:
    return " ".join(" ".join(parse(html).text).split())


def rules_with(fee: int, *, bpl_certificate: bool = True) -> Callable[[str], Rules]:
    """A stand-in for load_rules whose fee and certificate rule differ from the real data."""

    def fake(jurisdiction: str) -> Rules:
        real = load_rules("central")
        local = real.local.model_copy(
            update={
                "application_fee": real.local.application_fee.model_copy(update={"rupees": fee}),
                "bpl_certificate_required": real.local.bpl_certificate_required.model_copy(
                    update={"applies": bpl_certificate}
                ),
            }
        )
        return real.model_copy(update={"jurisdiction": jurisdiction, "local": local})

    return fake


def glossary_term(concept: str, language: Literal["hi", "ta"]) -> str:
    (entry,) = [e for e in load_glossary() if e.concept == concept]
    return entry.local(language).term


# --- the model -------------------------------------------------------------------------------


def test_model_is_frozen_and_closed() -> None:
    doc = case("en")
    with pytest.raises(ValidationError):
        doc.subject = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ApplicationDocument.model_validate({**CASES["en"], "phone": "not a field"})


@pytest.mark.parametrize("language", ["fr", "", "EN"])
def test_model_rejects_languages_outside_en_hi_ta(language: str) -> None:
    with pytest.raises(ValidationError):
        ApplicationDocument.model_validate({**CASES["en"], "language": language})


def test_model_rejects_jurisdictions_other_than_central_and_tamil_nadu() -> None:
    with pytest.raises(ValidationError):
        ApplicationDocument.model_validate({**CASES["en"], "jurisdiction": "kerala"})


@pytest.mark.parametrize("field", ["pio_address", "applicant_address"])
@pytest.mark.parametrize("blank", ["", "   \n "])
def test_model_blocks_a_missing_address(field: str, blank: str) -> None:
    with pytest.raises(ValidationError):
        ApplicationDocument.model_validate({**CASES["en"], field: blank})


def test_model_needs_at_least_one_real_question() -> None:
    with pytest.raises(ValidationError):
        ApplicationDocument.model_validate({**CASES["en"], "questions": []})
    with pytest.raises(ValidationError):
        ApplicationDocument.model_validate({**CASES["en"], "questions": ["Fine", "  "]})


# --- language, labels, terms -----------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_html_lang_is_the_document_language(language: Language) -> None:
    html = render_application_html(case(language))
    assert re.search(rf'<html lang="{language}"', html)


@pytest.mark.parametrize("language", LANGUAGES)
def test_fixed_labels_are_in_the_document_language(language: Language) -> None:
    text = visible(render_application_html(case(language)))
    for label in LABELS[language]:
        assert label in text, label
    if language != "en":  # no English label leaks into a Hindi or Tamil letter
        for label in LABELS["en"]:
            assert not re.search(rf"\b{label}\b", text), label


def test_english_uses_the_act_and_officer_titles() -> None:
    text = visible(render_application_html(case("en")))
    assert "Right to Information Act, 2005" in text
    assert "Public Information Officer" in text


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_act_name_and_officer_title_come_from_the_glossary(language: Literal["hi", "ta"]) -> None:
    text = visible(render_application_html(case(language)))
    assert glossary_term("Right to Information Act, 2005", language) in text
    assert glossary_term("Public Information Officer", language) in text


@pytest.mark.parametrize("language", LANGUAGES)
def test_date_is_written_out_and_machine_readable(language: Language) -> None:
    html = render_application_html(case(language))
    assert DATE_TEXT[language] in visible(html)
    assert '<time datetime="2026-10-27">' in html


def test_place_row_is_left_out_when_blank() -> None:
    assert "Place" in visible(render_application_html(case("en")))
    assert "Place" not in visible(render_application_html(case("en", place="")))


# --- questions -------------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_questions_are_one_numbered_list_in_the_given_order(language: Language) -> None:
    doc = case(language)
    html = render_application_html(doc)
    assert html.count("<ol") == 1
    assert parse(html).items == doc.questions


def test_questions_keep_their_order_when_there_are_many() -> None:
    questions = [f"Question number {n}" for n in range(1, 31)]
    html = render_application_html(case("en", questions=questions))
    assert parse(html).items == questions


# --- fee and BPL: values come from the rules -------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_fee_is_the_rules_value(language: Language) -> None:
    rupees = load_rules("central").local.application_fee.rupees
    text = visible(render_application_html(case(language)))
    sign = "Rs" if language == "en" else "₹"
    assert re.search(rf"{sign}\s?{rupees}\b", text)


@pytest.mark.parametrize("jurisdiction", ["central", "tamil_nadu"])
def test_fee_follows_the_rules_not_a_literal(
    monkeypatch: pytest.MonkeyPatch, jurisdiction: str
) -> None:
    monkeypatch.setattr("unseal.pdf.render.load_rules", rules_with(37))
    text = visible(render_application_html(case("en", jurisdiction=jurisdiction)))
    assert "Rs 37" in text
    assert "Rs 10" not in text


def test_the_rules_are_read_for_the_documents_own_jurisdiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []
    fake = rules_with(37)

    def spy(jurisdiction: str) -> Rules:
        asked.append(jurisdiction)
        return fake(jurisdiction)

    monkeypatch.setattr("unseal.pdf.render.load_rules", spy)
    render_application_html(case("en", jurisdiction="tamil_nadu"))
    assert asked == ["tamil_nadu"]


def test_no_fee_literal_in_the_sources() -> None:
    package = files("unseal.pdf")
    sources = [
        package.joinpath("render.py"),
        package.joinpath("labels.py"),
        package.joinpath("templates", "application.html.j2"),
    ]
    for source in sources:
        assert not re.search(r"(Rs\.?|₹|रु\.?|ரூ\.?)\s*\d", source.read_text("utf-8")), source.name


def test_bpl_applicant_sees_nil_and_the_certificate_note() -> None:
    text = visible(render_application_html(case("en", bpl=True)))
    assert "Nil (BPL)" in text
    assert "A copy of my BPL certificate is enclosed." in text
    assert "Rs 10" not in text


def test_bpl_note_follows_the_certificate_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("unseal.pdf.render.load_rules", rules_with(10, bpl_certificate=False))
    text = visible(render_application_html(case("en", bpl=True)))
    assert "Nil (BPL)" in text
    assert "BPL certificate" not in text


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_bpl_text_uses_the_glossary_term(language: Literal["hi", "ta"]) -> None:
    text = visible(render_application_html(case(language, bpl=True)))
    assert glossary_term("below poverty line", language) in text
    assert "₹" not in text


def test_bpl_applicant_has_no_payment_mode() -> None:
    text = visible(render_application_html(case("en", bpl=True, payment_mode="demand_draft")))
    assert "Payment mode" not in text
    assert "Demand draft" not in text


def test_paying_applicant_sees_the_payment_mode() -> None:
    text = visible(render_application_html(case("en", payment_mode="demand_draft")))
    assert "Payment mode" in text
    assert "Demand draft" in text


def test_payment_mode_is_left_out_when_unknown_to_the_applicant() -> None:
    assert "Payment mode" not in visible(render_application_html(case("en", payment_mode=None)))


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("jurisdiction", ["central", "tamil_nadu"])
def test_every_payment_mode_in_the_rules_has_a_label(
    jurisdiction: Literal["central", "tamil_nadu"], language: Language
) -> None:
    labels = labels_for(language).payment_modes
    for mode in load_rules(jurisdiction).local.payment_modes.modes:
        assert labels.get(mode), (jurisdiction, language, mode)
        assert labels[mode] != mode


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("jurisdiction", ["central", "tamil_nadu"])
def test_a_rules_payment_mode_never_reaches_the_page_as_a_raw_code(
    jurisdiction: Literal["central", "tamil_nadu"], language: Language
) -> None:
    for mode in load_rules(jurisdiction).local.payment_modes.modes:
        doc = case(language, jurisdiction=jurisdiction, payment_mode=mode)
        html = render_application_html(doc)
        assert mode not in html, (jurisdiction, language, mode)
        assert labels_for(language).payment_modes[mode] in visible(html)


def test_an_unlisted_payment_mode_is_shown_as_written_and_escaped() -> None:
    html = render_application_html(case("en", payment_mode="<i>treasury</i> challan"))
    assert "&lt;i&gt;treasury&lt;/i&gt; challan" in html
    assert "<i>" not in html


# --- footer ----------------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_footer_has_the_english_line_in_every_language(language: Language) -> None:
    assert FOOTER_EN in visible(render_application_html(case(language)))


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_footer_is_also_in_the_document_language(language: Literal["hi", "ta"]) -> None:
    assert FOOTER_LOCAL[language] in visible(render_application_html(case(language)))


def test_english_footer_is_not_repeated() -> None:
    assert visible(render_application_html(case("en"))).count(FOOTER_EN) == 1


# --- user text -------------------------------------------------------------------------------


def test_user_text_is_html_escaped() -> None:
    html = render_application_html(
        case(
            "en",
            authority_name="R&D <Office>",
            subject="<b>Bold</b> & co",
            questions=["<script>alert(1)</script>", "Second"],
            applicant_name='Test "Applicant" <x>',
        )
    )
    assert "<script" not in html.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "R&amp;D &lt;Office&gt;" in html
    assert "&lt;b&gt;Bold&lt;/b&gt; &amp; co" in html
    assert "<x>" not in html
    assert parse(html).items[0] == "<script>alert(1)</script>"


def test_line_breaks_in_addresses_are_kept() -> None:
    html = render_application_html(case("en", pio_address="Line one\nLine two"))
    assert "Line one\nLine two" in html
    assert "pre-line" in html  # the CSS that turns the newline into a line break


def test_english_text_in_a_tamil_letter_is_marked_as_english() -> None:
    html = render_application_html(case("ta", authority_name="Greater Test Corporation"))
    assert '<span lang="en">Greater Test Corporation</span>' in html


def test_tamil_text_in_an_english_letter_is_marked_as_tamil() -> None:
    html = render_application_html(case("en", place="சென்னை"))
    assert '<span lang="ta">சென்னை</span>' in html


def test_text_in_the_document_language_is_not_wrapped() -> None:
    html = render_application_html(case("hi"))
    assert '<span lang="hi">' not in html
    assert '<span lang="en">' not in re.sub(r"<footer.*?</footer>", "", html, flags=re.S)


# --- no official look ------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_images_emblems_or_seals(language: Language) -> None:
    html = render_application_html(case(language))
    for tag in ("<img", "<svg", "<canvas", "<object", "<embed", "<picture", "<link"):
        assert tag not in html.lower(), tag
    assert "background-image" not in html
    # "UnSeal" is the product name; the word "seal" on its own is what must not appear.
    assert not re.search(r"\bseal\b|emblem|ashoka|satyamev|government of india", html, re.I)


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_is_self_contained(language: Language) -> None:
    html = render_application_html(case(language))
    assert "http://" not in html and "https://" not in html
    urls = re.findall(r'url\("([^"]+)"\)', html)
    assert urls
    assert all(u.startswith("file:///") and u.endswith(".ttf") for u in urls), urls


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_em_dash_in_the_output(language: Language) -> None:
    assert EM_DASH not in render_application_html(case(language))


def test_no_em_dash_in_the_sources() -> None:
    package = files("unseal.pdf")
    for name in ("render.py", "labels.py", "models.py", "templates/application.html.j2"):
        assert EM_DASH not in package.joinpath(name).read_text("utf-8"), name


@pytest.mark.parametrize("language", LANGUAGES)
def test_metadata_carries_no_personal_data(language: Language) -> None:
    doc = case(language)
    head = render_application_html(doc).split("</head>")[0]
    assert doc.applicant_name not in head
    assert doc.applicant_address not in head


def test_rendering_is_deterministic() -> None:
    doc = case("ta")
    assert render_application_html(doc) == render_application_html(doc)


# --- fonts and fictional data ----------------------------------------------------------------

FONT_FILES = [
    f"{family}-{weight}.ttf"
    for family in ("NotoSans", "NotoSansTamil", "NotoSansDevanagari")
    for weight in ("Regular", "Bold")
]


def test_the_noto_fonts_ship_with_their_licences() -> None:
    fonts = files("unseal.pdf") / "fonts"
    for name in FONT_FILES:
        assert fonts.joinpath(name).read_bytes()[:4] == b"\x00\x01\x00\x00", name  # TrueType
    for family in ("NotoSans", "NotoSansTamil", "NotoSansDevanagari"):
        licence = fonts.joinpath(f"OFL-{family}.txt").read_text("utf-8")
        assert "SIL Open Font License, Version 1.1" in licence, family


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_font_face_points_at_a_file_that_exists(language: Language) -> None:
    html = render_application_html(case(language))
    paths = [
        Path(url2pathname(u.removeprefix("file://"))) for u in re.findall(r'url\("([^"]+)"', html)
    ]
    assert sorted(p.name for p in paths) == sorted(FONT_FILES)
    assert all(p.is_file() for p in paths)
    for family in ("Noto Sans", "Noto Sans Tamil", "Noto Sans Devanagari"):
        assert f'font-family: "{family}"' in html


def test_golden_cases_use_fictional_applicants_only() -> None:
    markers = {"en": "Test", "hi": "परीक्षण", "ta": "சோதனை"}
    for language, data in CASES.items():
        assert data["applicant_name"].startswith(markers[language]), language
        blob = json.dumps(data, ensure_ascii=False)
        assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", blob), "email"
        assert not re.search(r"\d{10,}|\d{4}\s\d{4}\s\d{4}", blob), "phone or ID-like number"
        assert data["prepared_on"] == date(2026, 10, 27).isoformat()
