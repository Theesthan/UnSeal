"""The first appeal template (FR-10, S. 19(1)): pure Jinja2, runs anywhere.

Section numbers come from the rules engine, dates are written out in the document language, the
grounds are fixed sentences, and the appellant's own words are printed escaped. Real PDF rendering
is covered in tests/pdf/test_pdf_appeal_render.py.
"""

import json
import re
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from typing import Literal, get_args
from urllib.request import url2pathname

import pytest
from pydantic import ValidationError

from unseal.llm.glossary import load_glossary
from unseal.pdf.appeal import render_appeal_html, section_number
from unseal.pdf.appeal_labels import appeal_labels_for
from unseal.pdf.models import AppealDocument, FilingMode, Ground
from unseal.rules.deadlines import appeal_lateness, compute_deadlines, first_appeal_deadline
from unseal.rules.engine import Rules, load_rules

Language = Literal["en", "hi", "ta"]
LANGUAGES: list[Language] = ["en", "hi", "ta"]

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "golden" / "pdf" / "appeal_cases.json").read_text(
        "utf-8"
    )
)
FOOTER_EN = "Prepared with UnSeal. Not legal advice."
FOOTER_LOCAL = {
    "hi": "UnSeal द्वारा तैयार किया गया। यह कानूनी सलाह नहीं है।",
    "ta": "UnSeal மூலம் தயாரிக்கப்பட்டது. இது சட்ட ஆலோசனை அல்ல.",
}
LABELS = {
    "en": ["To", "Appellant", "Respondent", "Particulars of the application", "Grounds of appeal"]
    + ["Relief sought", "Application filed on", "Mode of filing", "Reply was due by", "Signature"]
    + ["Address", "Date", "Place"],
    "hi": ["सेवा में", "अपीलार्थी", "प्रत्यर्थी", "आवेदन का विवरण", "अपील के आधार", "माँगी गई राहत"]
    + ["आवेदन प्रस्तुत करने की तिथि", "उत्तर देने की अंतिम तिथि", "हस्ताक्षर", "पता", "दिनांक"],
    "ta": ["பெறுநர்", "மேல்முறையீட்டாளர்", "எதிர்மனுதாரர்", "விண்ணப்ப விவரங்கள்", "கோரும் நிவாரணம்"]
    + ["மேல்முறையீட்டுக்கான காரணங்கள்", "விண்ணப்பம் தாக்கல் செய்த நாள்", "கையொப்பம்", "முகவரி"],
}
EN_GROUNDS = {
    "no_reply": "No information was provided within the time limit, so the request is deemed to "
    "have been refused under Section 7(2) of the Act.",
    "incomplete": "The information provided is incomplete, or is not the information that was "
    "asked for.",
    "refused": "The request was refused without a valid reason.",
    "fee_demanded": "A fee was demanded that, in my view, is not payable.",
}
EN_RELIEF = (
    "I request that the Public Information Officer be directed to provide the information sought "
    "in my application."
)
EN_DELAY = (
    "This first appeal is filed after the time limit. I request that the delay be condoned, as I "
    "was prevented by sufficient cause from filing it in time."
)
EM_DASH = chr(0x2014)  # built from its code point so this file has none itself
SOURCES = ("appeal.py", "appeal_labels.py", "common.py", "templates/appeal.html.j2")


def case(language: Language, **changes: object) -> AppealDocument:
    return AppealDocument.model_validate({**CASES[language], **changes})


class _Page(HTMLParser):
    """Visible text (no CSS, no <title>), the text of each <li>, and each (dt, dd) pair."""

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.items: list[str] = []
        self.rows: list[tuple[str, str]] = []
        self._skip = 0
        self._open: dict[str, list[str]] = {}
        self._dt = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"style", "title"}:
            self._skip += 1
        elif tag in {"li", "dt", "dd"}:
            self._open[tag] = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "title"}:
            self._skip -= 1
            return
        if tag not in self._open:
            return
        text = " ".join("".join(self._open.pop(tag)).split())
        if tag == "li":
            self.items.append(text)
        elif tag == "dt":
            self._dt = text
        else:
            self.rows.append((self._dt, text))

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self.text.append(data)
        for parts in self._open.values():
            parts.append(data)


def parse(html: str) -> _Page:
    page = _Page()
    page.feed(html)
    return page


def visible(html: str) -> str:
    return " ".join(" ".join(parse(html).text).split())


def term(concept: str, language: Literal["hi", "ta"]) -> str:
    (entry,) = [e for e in load_glossary() if e.concept == concept]
    return entry.local(language).term


def rules_with(**bases: str) -> Callable[[str], Rules]:
    """A stand-in for load_rules whose act rules carry other `basis` texts."""

    def fake(jurisdiction: str) -> Rules:
        real = load_rules("central")
        act = real.act.model_copy(
            update={
                name: getattr(real.act, name).model_copy(update={"basis": basis})
                for name, basis in bases.items()
            }
        )
        return real.model_copy(update={"jurisdiction": jurisdiction, "act": act})

    return fake


# --- section numbers come from the rules -----------------------------------------------------


def test_section_number_is_read_from_the_rule_basis() -> None:
    assert section_number("RTI Act 2005, s. 19(1) and proviso") == "19(1)"
    assert section_number("RTI Act 2005, s. 7(2)") == "7(2)"
    assert section_number("RTI Act 2005, s. 8(1)(j), as substituted") == "8(1)(j)"


@pytest.mark.parametrize("basis", ["RTI Act 2005", "s. 19", "DPDP Act 2023, s. 44(3)", ""])
def test_a_basis_without_an_rti_act_section_raises(basis: str) -> None:
    with pytest.raises(ValueError, match="section"):
        section_number(basis)


def test_title_and_no_reply_ground_follow_the_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = rules_with(
        first_appeal="RTI Act 2005, s. 88(8) and proviso", deemed_refusal="RTI Act 2005, s. 99(9)"
    )
    monkeypatch.setattr("unseal.pdf.appeal.load_rules", fake)
    text = visible(render_appeal_html(case("en")))
    assert "First appeal under Section 88(8) of the Right to Information Act, 2005" in text
    assert "deemed to have been refused under Section 99(9) of the Act" in text
    assert "19(1)" not in text and "7(2)" not in text


def test_a_rule_basis_without_a_section_stops_the_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("unseal.pdf.appeal.load_rules", rules_with(first_appeal="RTI Act 2005"))
    with pytest.raises(ValueError, match="section"):
        render_appeal_html(case("en"))


def test_the_rules_are_read_for_the_documents_own_jurisdiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []

    def spy(jurisdiction: Literal["central", "tamil_nadu"]) -> Rules:
        asked.append(jurisdiction)
        return load_rules(jurisdiction)

    monkeypatch.setattr("unseal.pdf.appeal.load_rules", spy)
    render_appeal_html(case("ta"))
    assert asked == ["tamil_nadu"]


def test_no_section_or_fee_literal_in_the_sources() -> None:
    package = files("unseal.pdf")
    section = re.compile(r"\d+\s*\(\s*\d+\s*\)|\bSection\s+\d|\bs\.\s*\d|धारा\s*\d|பிரிவு\s*\d")
    fee = re.compile(r"(Rs\.?|₹|रु\.?|ரூ\.?)\s*\d")
    for name in SOURCES:
        source = package.joinpath(name).read_text("utf-8")
        assert not section.search(source), name
        assert not fee.search(source), name


# --- title, labels, glossary terms -----------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_html_lang_is_the_document_language(language: Language) -> None:
    assert re.search(rf'<html lang="{language}"', render_appeal_html(case(language)))


def test_english_title_names_the_section_and_the_act() -> None:
    html = render_appeal_html(case("en"))
    title = "First appeal under Section 19(1) of the Right to Information Act, 2005"
    assert f"<h1>{title}</h1>" in html
    assert f"<title>{title}</title>" in html


@pytest.mark.parametrize(
    ("language", "section"), [("hi", "की धारा 19(1) के अंतर्गत"), ("ta", "பிரிவு 19(1)-இன் கீழ்")]
)
def test_indic_title_uses_the_glossary_terms(language: Literal["hi", "ta"], section: str) -> None:
    (title,) = re.findall(r"<h1>(.*?)</h1>", render_appeal_html(case(language)))
    assert title.startswith(term("Right to Information Act, 2005", language))
    assert section in title
    assert title.endswith(term("first appeal", language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_fixed_labels_are_in_the_document_language(language: Language) -> None:
    text = visible(render_appeal_html(case(language)))
    for label in LABELS[language]:
        assert label in text, label
    if language != "en":  # no English label leaks into a Hindi or Tamil letter
        for label in LABELS["en"]:
            assert not re.search(rf"\b{label}\b", text), label


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_officer_authority_and_appeal_terms_come_from_the_glossary(
    language: Literal["hi", "ta"],
) -> None:
    text = visible(render_appeal_html(case(language, late=True)))
    for concept in ("Public Information Officer", "appellate authority", "public authority"):
        assert term(concept, language) in text, concept
    assert text.count(term("first appeal", language)) >= 2  # the title and the delay paragraph


def test_every_ground_and_filing_mode_has_a_label_in_every_language() -> None:
    for language in LANGUAGES:
        labels = appeal_labels_for(language)
        assert set(labels.grounds) == set(get_args(Ground)), language
        assert set(labels.filing_modes) == set(get_args(FilingMode)), language
        assert "{section}" in labels.title and "{section}" in labels.grounds["no_reply"]


# --- addressee and parties -------------------------------------------------------------------


def test_the_letter_goes_to_the_first_appellate_authority() -> None:
    doc = case("en")
    html = render_appeal_html(doc)
    to = html.split('<section class="to">')[1].split("</section>")[0]
    assert "First Appellate Authority," in to
    assert doc.authority_name in to
    assert "Deputy Commissioner (Works)\nCivic Centre, 1 Example Road\nChennai" in to


def test_appellant_and_respondent_are_named() -> None:
    rows = parse(render_appeal_html(case("en"))).rows
    assert ("Appellant", "Test Appellant 12 Example Street Chennai") in rows
    respondent = "Public Information Officer, Example Municipal Corporation Civic Centre, 1 "
    assert ("Respondent", respondent + "Example Road Chennai") in rows


# --- particulars -----------------------------------------------------------------------------


def test_english_particulars_without_a_reply() -> None:
    rows = parse(render_appeal_html(case("en"))).rows
    for row in [
        ("Application filed on", "25 August 2026"),
        ("Mode of filing", "By post"),
        ("Received by the public authority on", "1 September 2026 (estimated)"),
        ("Reply was due by", "1 October 2026"),
        ("Reply", "No reply was received"),
    ]:
        assert row in rows, row
    assert "Reply received on" not in [dt for dt, _ in rows]


def test_a_received_reply_is_dated_and_an_actual_receipt_is_not_estimated() -> None:
    doc = case("en", received_estimated=False, reply_received_on="2026-10-05", grounds=["refused"])
    html = render_appeal_html(doc)
    rows = parse(html).rows
    assert ("Reply received on", "5 October 2026") in rows
    assert ("Received by the public authority on", "1 September 2026") in rows
    assert "No reply was received" not in visible(html)
    assert "estimated" not in visible(html)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_date_is_written_out_and_machine_readable(language: Language) -> None:
    doc = case(language)
    labels = appeal_labels_for(language)
    html = render_appeal_html(doc)
    days = [doc.filed_on, doc.received_on, doc.reply_due_on, doc.prepared_on]
    days += [doc.reply_received_on] if doc.reply_received_on else []
    for day in days:
        text = f"{day.day} {labels.months[day.month - 1]} {day.year}"
        assert f'<time datetime="{day.isoformat()}">{text}</time>' in html, day


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("mode", get_args(FilingMode))
def test_the_filing_mode_is_translated_never_a_raw_code(language: Language, mode: str) -> None:
    html = render_appeal_html(case(language, filing_mode=mode))
    assert appeal_labels_for(language).filing_modes[mode] in visible(html)
    assert "rti_online" not in html and "in_person" not in html


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_the_estimated_note_is_in_the_document_language(language: Literal["hi", "ta"]) -> None:
    note = appeal_labels_for(language).estimated
    assert f"({note})" in visible(render_appeal_html(case(language, received_estimated=True)))
    assert note not in visible(render_appeal_html(case(language, received_estimated=False)))


# --- grounds, details, relief, delay ---------------------------------------------------------


def test_grounds_are_one_numbered_list_of_fixed_sentences_in_the_given_order() -> None:
    doc = case("en", reply_received_on="2026-10-05", grounds=["fee_demanded", "refused"])
    html = render_appeal_html(doc)
    assert html.count("<ol") == 1
    assert parse(html).items == [EN_GROUNDS["fee_demanded"], EN_GROUNDS["refused"]]


def test_no_reply_ground_cites_the_deemed_refusal_section() -> None:
    assert parse(render_appeal_html(case("en"))).items == [EN_GROUNDS["no_reply"]]


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_indic_grounds_follow_the_given_order(language: Literal["hi", "ta"]) -> None:
    grounds: list[Ground] = ["refused", "incomplete", "fee_demanded"]
    doc = case(language, grounds=grounds, reply_received_on="2026-10-05")
    sentences = appeal_labels_for(language).grounds
    assert parse(render_appeal_html(doc)).items == [sentences[g] for g in grounds]
    no_reply = parse(
        render_appeal_html(case(language, grounds=["no_reply"], reply_received_on=None))
    )
    assert no_reply.items == [sentences["no_reply"].format(section="7(2)")]


def test_details_are_printed_escaped_under_their_heading() -> None:
    html = render_appeal_html(case("en", details="Line one <b>&</b>\nLine two"))
    assert "<h2>Details</h2>" in html
    assert "Line one &lt;b&gt;&amp;&lt;/b&gt;\nLine two" in html
    assert "<b>" not in html


@pytest.mark.parametrize("blank", ["", "  \n "])
def test_blank_details_leave_out_the_heading(blank: str) -> None:
    assert "Details" not in visible(render_appeal_html(case("en", details=blank)))


def test_details_in_another_script_are_marked_with_their_language() -> None:
    html = render_appeal_html(case("en", details="பதில் வரவில்லை"))
    assert '<span lang="ta">பதில் வரவில்லை</span>' in html


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_relief_is_requested_in_every_letter(language: Language) -> None:
    assert appeal_labels_for(language).relief in visible(render_appeal_html(case(language)))


def test_english_relief_wording() -> None:
    assert EN_RELIEF in visible(render_appeal_html(case("en")))


def test_a_late_appeal_asks_for_condonation_and_gives_the_reason() -> None:
    text = visible(render_appeal_html(case("en", late=True, delay_reason="I was <ill>.")))
    assert "Delay in filing" in text
    assert f"{EN_DELAY} I was <ill>." in text


def test_a_late_appeal_without_a_reason_has_the_fixed_sentence_only() -> None:
    html = render_appeal_html(case("en", late=True, delay_reason="  "))
    assert EN_DELAY in visible(html)
    assert html.count('class="multiline delay-reason"') == 0


def test_an_appeal_in_time_has_no_delay_paragraph_even_with_a_reason() -> None:
    text = visible(render_appeal_html(case("en", late=False, delay_reason="Not needed")))
    assert "Delay in filing" not in text
    assert "condoned" not in text
    assert "Not needed" not in text


# --- closing, signature, footer --------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_signature_block_matches_the_application(language: Language) -> None:
    doc = case(language)
    html = render_appeal_html(doc)
    closing = html.split('<section class="closing">')[1]
    assert '<span class="signature-line" aria-hidden="true"></span>' in closing
    assert doc.appellant_name in closing
    assert '<time datetime="2026-10-27">' in closing
    assert appeal_labels_for(language).appellant in closing


def test_place_row_is_left_out_when_blank() -> None:
    assert "Place" in visible(render_appeal_html(case("en")))
    assert "Place" not in visible(render_appeal_html(case("en", place=" ")))


@pytest.mark.parametrize("language", LANGUAGES)
def test_footer_has_the_english_line_once(language: Language) -> None:
    assert visible(render_appeal_html(case(language))).count(FOOTER_EN) == 1


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_footer_is_also_in_the_document_language(language: Literal["hi", "ta"]) -> None:
    assert FOOTER_LOCAL[language] in visible(render_appeal_html(case(language)))


# --- user text, no official look, determinism ------------------------------------------------


def test_user_text_is_html_escaped() -> None:
    html = render_appeal_html(
        case(
            "en",
            authority_name="R&D <Office>",
            appellant_name='Test "Appellant" <x>',
            faa_address="<script>alert(1)</script>",
        )
    )
    assert "<script" not in html.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "R&amp;D &lt;Office&gt;" in html
    assert "<x>" not in html


def test_english_text_in_a_tamil_letter_is_marked_as_english() -> None:
    html = render_appeal_html(case("ta", authority_name="Greater Test Corporation"))
    assert '<span lang="en">Greater Test Corporation</span>' in html


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_fee_line_images_emblems_or_seals(language: Language) -> None:
    html = render_appeal_html(case(language))
    for tag in ("<img", "<svg", "<canvas", "<object", "<embed", "<picture", "<link"):
        assert tag not in html.lower(), tag
    assert "background-image" not in html
    assert not re.search(r"\bseal\b|emblem|ashoka|satyamev|government of india", html, re.I)
    assert not re.search(r"(Rs\.?|₹)\s?\d", visible(html))


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_is_self_contained_and_its_fonts_exist(language: Language) -> None:
    html = render_appeal_html(case(language))
    assert "http://" not in html and "https://" not in html
    urls = re.findall(r'url\("([^"]+)"\)', html)
    assert len(urls) == 6
    assert all(Path(url2pathname(u.removeprefix("file://"))).is_file() for u in urls), urls


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_em_dash_in_the_output(language: Language) -> None:
    assert EM_DASH not in render_appeal_html(case(language, late=True))


def test_no_em_dash_in_the_sources() -> None:
    package = files("unseal.pdf")
    for name in (*SOURCES, "templates/_style.html.j2", "templates/_parts.html.j2"):
        assert EM_DASH not in package.joinpath(name).read_text("utf-8"), name


@pytest.mark.parametrize("language", LANGUAGES)
def test_metadata_carries_no_personal_data(language: Language) -> None:
    doc = case(language)
    head = render_appeal_html(doc).split("</head>")[0]
    personal = (doc.appellant_name, doc.appellant_address, doc.details, doc.delay_reason)
    for value in (*personal, doc.authority_name):
        assert not value.strip() or value not in head, value


def test_rendering_is_deterministic() -> None:
    doc = case("ta")
    assert render_appeal_html(doc) == render_appeal_html(doc)


# --- the contract and the golden cases -------------------------------------------------------


def test_the_model_rejects_a_no_reply_ground_once_a_reply_came() -> None:
    with pytest.raises(ValidationError):
        case("en", reply_received_on="2026-10-05")


@pytest.mark.parametrize("grounds", [[], ["refused", "refused"], ["late"]])
def test_the_model_needs_distinct_known_grounds(grounds: list[str]) -> None:
    with pytest.raises(ValidationError):
        case("en", grounds=grounds, reply_received_on="2026-10-05")


def test_golden_cases_use_fictional_appellants_only() -> None:
    markers = {"en": "Test", "hi": "परीक्षण", "ta": "சோதனை"}
    for language, data in CASES.items():
        assert data["appellant_name"].startswith(markers[language]), language
        blob = json.dumps(data, ensure_ascii=False)
        assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", blob), "email"
        assert not re.search(r"\d{10,}|\d{4}\s\d{4}\s\d{4}", blob), "phone or ID-like number"
        assert data["prepared_on"] == date(2026, 10, 27).isoformat()


@pytest.mark.parametrize("language", LANGUAGES)
def test_golden_dates_agree_with_the_rules_engine(language: Language) -> None:
    doc = case(language)
    rules = load_rules(doc.jurisdiction)
    computed = compute_deadlines(
        filed_on=doc.filed_on,
        received_on=None if doc.received_estimated else doc.received_on,
        via_apio=False,
        third_party=False,
        life_liberty=False,
        rules=rules,
    )
    assert (computed.received_on, computed.received_estimated) == (
        doc.received_on,
        doc.received_estimated,
    )
    assert computed.pio_reply.due_on == doc.reply_due_on
    window = first_appeal_deadline(
        computed.pio_reply, rules=rules, reply_received_on=doc.reply_received_on
    )
    assert appeal_lateness(window, doc.prepared_on, rules=rules).late == doc.late
