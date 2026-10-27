"""The second appeal (FR-12, S. 19(3)): shared behaviour and the CIC rule 8 Appendix format.

The TNSIC form is covered in test_pdf_second_appeal_tnsic.py; real PDFs in
tests/pdf/test_pdf_second_appeal_render.py.
"""

import re
from importlib.resources import files
from typing import Literal, get_args

import pytest
from test_pdf_second_appeal_support import (
    CASES,
    EM_DASH,
    FAKE_BASES,
    FAKE_SECTIONS,
    FOOTER_EN,
    FOOTER_LOCAL,
    REAL_SECTIONS,
    SOURCES,
    case,
    parse,
    rules_with,
    visible,
)

from unseal.pdf.models import SecondGround
from unseal.pdf.second_appeal import enclosures_for, render_second_appeal_html
from unseal.pdf.second_appeal_labels import second_appeal_labels
from unseal.rules.deadlines import (
    appeal_lateness,
    compute_deadlines,
    faa_decision_deadlines,
    second_appeal_deadline,
)
from unseal.rules.engine import Enclosure, load_rules

CIC = ["cic-en", "cic-hi", "cic-ta"]
# The Appendix "FORMAT OF APPEAL" of the RTI Rules 2012, as published (capitals normalised):
# https://cic.gov.in/sites/default/files/RTIRules2012_Eng.pdf and RTIRules2012_Hindi.pdf
ITEMS = {
    "en": [
        "Name and address of the appellant",
        "Name and address of the Central Public Information Officer to whom the application "
        "was addressed",
        "Name and address of the Central Public Information Officer who gave reply to the "
        "application",
        "Name and address of the First Appellate Authority who decided the first appeal",
        "Particulars of the application",
        "Particulars of the order(s) including number, if any, against which the appeal is "
        "preferred",
        "Brief facts leading to the appeal",
        "Prayer or relief sought",
        "Grounds for the prayer or relief",
        "Any other information relevant to the appeal",
        "Verification/authentication by the appellant",
    ],
    "hi": [
        "अपीलार्थी का नाम और पता",
        "केंद्रीय लोक सूचना अधिकारी का नाम और पता, जिसे आवेदन संबोधित किया गया था",
        "केंद्रीय लोक सूचना अधिकारी का नाम और पता, जिसने आवेदन का उत्तर दिया था",
        "प्रथम अपील प्राधिकारी का नाम और पता, जिसने प्रथम अपील का विनिश्चय किया था",
        "आवेदन की विशिष्टियां",
        "ऐसे आदेश (आदेशों) की, संख्यांक सहित, यदि कोई हो, जिसके (जिनके) विरुद्ध अपील की गई है, विशिष्टियां",
        "अपील के संक्षिप्त तथ्य, जिनके कारण अपील की गई है",
        "प्रार्थना या ईप्सित अनुतोष",
        "प्रार्थना या अनुतोष के आधार",
        "अपील से सुसंगत कोई अन्य सूचना",
        "अपीलार्थी द्वारा सत्यापन/अधिप्रमाणन",
    ],
}
EN_FACTS = (
    "The application under Section 6(1) was filed on 4 May 2026 and received by the public "
    "authority on 11 May 2026 (estimated). The reply was due by 10 June 2026, but no reply was "
    "received. The first appeal under Section 19(1) was filed on 1 July 2026. The First Appellate "
    "Authority passed no order on the first appeal."
)
EN_GROUNDS = {
    "no_reply": "No information was provided within the time limit, so the request is deemed to "
    "have been refused under Section 7(2) of the Act.",
    "no_decision": "The First Appellate Authority did not decide the first appeal within the time "
    "allowed by Section 19(6) of the Act.",
    "refused": "The request was refused without a valid reason.",
    "incomplete": "The information provided is incomplete, or is not the information that was "
    "asked for.",
    "incorrect": "The information provided is incorrect or misleading.",
    "fee_demanded": "A fee was demanded that, in my view, is not payable.",
}
EN_PRAYER = (
    "I request the Commission to direct the Central Public Information Officer to provide the "
    "information sought in my application."
)
EN_DELAY = (
    "This second appeal is filed after the time limit. I request that the delay be condoned, as I "
    "was prevented by sufficient cause from filing it in time."
)
EN_DECLARATION = (
    "I, Test Appellant, the appellant, declare that the particulars given in this appeal are true "
    "and correct to the best of my knowledge and belief, and that the documents enclosed are true "
    "copies."
)


def items(html: str) -> list[str]:
    """The HTML of each of the 11 Appendix items, in order."""
    body = html.split('<ol class="items">', 1)[1].split("</ol>\n</section>", 1)[0]
    return body.split('<li class="item">')[1:]


def item_text(html: str, number: int) -> str:
    return visible(items(html)[number - 1])


# --- the format comes from the rules ---------------------------------------------------------


@pytest.mark.parametrize("name", [*CIC, "tnsic-en", "tnsic-ta"])
def test_html_lang_is_the_document_language(name: str) -> None:
    doc = case(name)
    assert f'<html lang="{doc.language}"' in render_second_appeal_html(doc)


def test_the_format_follows_the_rules_not_the_jurisdiction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("unseal.pdf.second_appeal.load_rules", rules_with(fmt="tnsic_form"))
    assert '<main class="tnsic">' in render_second_appeal_html(case("cic-en"))
    monkeypatch.setattr("unseal.pdf.second_appeal.load_rules", rules_with(fmt="cic_rule_8"))
    assert '<main class="cic">' in render_second_appeal_html(case("tnsic-en"))


@pytest.mark.parametrize(
    ("name", "printed"), [("cic-en", FAKE_SECTIONS), ("tnsic-en", FAKE_SECTIONS[:4])]
)
def test_every_section_number_follows_the_rules(
    monkeypatch: pytest.MonkeyPatch, name: str, printed: tuple[str, ...]
) -> None:
    # The TNSIC form ticks boxes instead of printing the ground sentences, so it never cites the
    # deemed refusal or the FAA decision sections.
    monkeypatch.setattr("unseal.pdf.second_appeal.load_rules", rules_with(**FAKE_BASES))
    doc = case(
        name,
        transferred_to="Test Office",
        reply_received_on=None,
        faa_decision_received_on=None,
        grounds=["no_reply", "no_decision"],
    )
    text = visible(render_second_appeal_html(doc))
    for section in REAL_SECTIONS:
        assert section not in text, section
    for section in printed:
        assert section in text, section


def test_a_rule_basis_without_a_section_stops_the_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "unseal.pdf.second_appeal.load_rules", rules_with(second_appeal="RTI Act 2005")
    )
    with pytest.raises(ValueError, match="section"):
        render_second_appeal_html(case("cic-en"))


def test_no_section_or_fee_literal_in_the_sources() -> None:
    package = files("unseal.pdf")
    section = re.compile(r"\d+\s*\(\s*\d+\s*\)|\bSection\s+\d|\bs\.\s*\d|धारा\s*\d|பிரிவு\s*\d")
    fee = re.compile(r"(Rs\.?|₹|रु\.?|ரூ\.?)\s*\d")
    for name in SOURCES:
        source = package.joinpath(name).read_text("utf-8")
        assert not section.search(source), name
        assert not fee.search(source), name
        assert EM_DASH not in source, name


# --- the CIC Appendix ------------------------------------------------------------------------


def test_english_title_and_addressee() -> None:
    html = render_second_appeal_html(case("cic-en"))
    title = "Second appeal under Section 19(3) of the Right to Information Act, 2005"
    assert f"<h1>{title}</h1>" in html and f"<title>{title}</title>" in html
    assert "Before the Central Information Commission" in visible(html)


@pytest.mark.parametrize("language", ["en", "hi"])
def test_the_eleven_items_use_the_official_appendix_wording(language: Literal["en", "hi"]) -> None:
    html = render_second_appeal_html(case(f"cic-{language}"))
    headings = [visible(h) for h in re.findall(r'<h2 class="item-label">(.*?)</h2>', html, re.S)]
    assert headings == ITEMS[language]


def test_the_tamil_appendix_has_eleven_items() -> None:
    html = render_second_appeal_html(case("cic-ta"))
    assert len(items(html)) == 11
    assert all(re.search(r"[஀-௿]", visible(item)) for item in items(html))


def test_item_1_names_the_appellant_with_the_phone_when_known() -> None:
    assert item_text(render_second_appeal_html(case("cic-en")), 1).endswith(
        "Test Appellant 12 Example Street Chennai Phone: 00000 00000"
    )
    no_phone = item_text(render_second_appeal_html(case("cic-en", appellant_phone=None)), 1)
    assert "Phone" not in no_phone


def test_items_2_to_4_name_the_officers_and_the_appellate_authority() -> None:
    html = render_second_appeal_html(case("cic-en"))
    office = "Central Public Information Officer, Regional Office, Example Central Agency"
    assert item_text(html, 2).endswith(f"{office} 2 Example Road Chennai")
    assert item_text(html, 3).endswith("No reply was received.")
    first = "First Appellate Authority, Regional Office, Example Central Agency"
    assert item_text(html, 4).endswith(f"{first} Regional Director 2 Example Road Chennai")
    replied = render_second_appeal_html(
        case("cic-en", reply_received_on="2026-06-05", grounds=["refused"])
    )
    assert item_text(replied, 3).endswith(f"{office} 2 Example Road Chennai")


def test_item_5_gives_the_particulars_of_the_application() -> None:
    rows = parse(items(render_second_appeal_html(case("cic-en")))[4]).rows
    assert rows == [
        ("Application filed on", "4 May 2026"),
        ("Mode of filing", "By post"),
        ("Received by the public authority on", "11 May 2026 (estimated)"),
        ("Reply was due by", "10 June 2026"),
    ]
    moved = parse(
        items(render_second_appeal_html(case("cic-en", transferred_to="<Test> Office")))[4]
    )
    assert moved.rows[-1] == ("Transferred under Section 6(3) to", "<Test> Office")


def test_item_6_gives_the_orders_appealed_against() -> None:
    rows = parse(items(render_second_appeal_html(case("cic-en")))[5]).rows
    assert rows == [
        ("Reply of the Central Public Information Officer", "No reply was received"),
        ("First appeal filed on", "1 July 2026"),
        (
            "Order of the First Appellate Authority",
            "No order was passed by the First Appellate Authority",
        ),
    ]
    doc = case(
        "cic-en",
        reply_received_on="2026-06-05",
        faa_decision_received_on="2026-08-03",
        grounds=["incomplete"],
    )
    decided = render_second_appeal_html(doc)
    rows = parse(items(decided)[5]).rows
    assert rows[0] == ("Reply of the Central Public Information Officer", "Received on 5 June 2026")
    assert rows[2] == ("Order of the First Appellate Authority", "Received on 3 August 2026")
    assert (
        rows[3][0] == "Number of the order, if any" and '<span class="blank">' in items(decided)[5]
    )


def test_item_7_tells_the_facts_in_order_then_the_appellants_own_words() -> None:
    text = item_text(render_second_appeal_html(case("cic-en")), 7)
    assert text.startswith(f"Brief facts leading to the appeal {EN_FACTS}")
    assert text.endswith(CASES["cic-en"]["details"])  # type: ignore[arg-type]
    blank = item_text(render_second_appeal_html(case("cic-en", details=" ")), 7)
    assert blank.endswith("passed no order on the first appeal.")


def test_item_7_says_so_when_the_application_was_transferred_and_answered() -> None:
    doc = case(
        "cic-en", transferred_to="Test Office", reply_received_on="2026-06-05", grounds=["refused"]
    )
    text = item_text(render_second_appeal_html(doc), 7)
    assert "It was transferred under Section 6(3) of the Act to Test Office." in text
    assert "The reply was due by 10 June 2026 and was received on 5 June 2026." in text


def test_items_8_and_9_give_the_prayer_and_the_grounds_in_order() -> None:
    html = render_second_appeal_html(case("cic-en"))
    assert item_text(html, 8).endswith(EN_PRAYER)
    assert parse(items(html)[8]).items == [EN_GROUNDS["no_reply"], EN_GROUNDS["no_decision"]]
    grounds: list[SecondGround] = ["fee_demanded", "incorrect", "refused", "incomplete"]
    doc = case(
        "cic-en",
        reply_received_on="2026-06-05",
        faa_decision_received_on="2026-08-03",
        grounds=grounds,
    )
    assert parse(items(render_second_appeal_html(doc))[8]).items == [EN_GROUNDS[g] for g in grounds]


def test_item_10_carries_the_delay_paragraph_only_when_late() -> None:
    assert item_text(render_second_appeal_html(case("cic-en", delay_reason="Not used")), 10) == (
        "Any other information relevant to the appeal None."
    )
    late = item_text(
        render_second_appeal_html(case("cic-en", late=True, delay_reason="I <was> ill.")), 10
    )
    assert late.endswith(f"{EN_DELAY} I <was> ill.")
    no_reason = item_text(render_second_appeal_html(case("cic-en", late=True)), 10)
    assert no_reason.endswith(EN_DELAY)


def test_item_11_is_the_declaration_and_the_signature_block() -> None:
    html = render_second_appeal_html(case("cic-en"))
    last = items(html)[10]
    assert EN_DECLARATION in visible(last)
    assert '<span class="signature-line" aria-hidden="true"></span>' in last
    assert '<time datetime="2026-10-27">27 October 2026</time>' in last
    assert "Chennai" in visible(last.split('<section class="closing">')[1])
    assert "Place" not in visible(render_second_appeal_html(case("cic-en", place="")))


# --- enclosures ------------------------------------------------------------------------------


def test_enclosures_drop_the_copies_this_case_cannot_have() -> None:
    every: tuple[Enclosure, ...] = get_args(Enclosure)
    assert enclosures_for(case("cic-hi"), every) == [
        "application",
        "pio_reply",
        "first_appeal",
        "faa_order",
        "relied_documents",
        "index",
    ]
    assert enclosures_for(case("cic-en"), every) == [
        "application",
        "first_appeal",
        "relied_documents",
        "index",
    ]
    assert enclosures_for(case("cic-ta"), every) == [
        "application",
        "pio_reply",
        "transfer_letter",
        "first_appeal",
        "relied_documents",
        "index",
    ]


def test_the_enclosure_list_follows_the_rules_order_and_labels() -> None:
    html = render_second_appeal_html(case("cic-en"))
    annex = parse(html.split('<section class="enclosures">', 1)[1]).items
    assert annex == [
        "A copy of the application submitted to the Central Public Information Officer",
        "A copy of the appeal made to the First Appellate Authority",
        "Copies of other documents relied upon and referred to in this appeal",
        "An index of the documents referred to in this appeal",
    ]
    assert "Documents enclosed" in visible(html)


def test_a_transfer_letter_is_listed_only_when_the_rules_ask_for_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = render_second_appeal_html(case("cic-ta"))
    assert len(parse(html.split('<section class="enclosures">', 1)[1]).items) == 5
    fake = rules_with(enclosures=("application", "transfer_letter"))
    monkeypatch.setattr("unseal.pdf.second_appeal.load_rules", fake)
    html = render_second_appeal_html(case("cic-ta"))
    assert len(parse(html.split('<section class="enclosures">', 1)[1]).items) == 2
    html = render_second_appeal_html(case("cic-ta", transferred_to=None))
    assert len(parse(html.split('<section class="enclosures">', 1)[1]).items) == 1


# --- labels ----------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["cic_rule_8", "tnsic_form"])
def test_every_language_has_every_label(fmt: Literal["cic_rule_8", "tnsic_form"]) -> None:
    english = second_appeal_labels(fmt, "en")
    for language in ("en", "hi", "ta"):
        labels = second_appeal_labels(fmt, language)  # type: ignore[arg-type]
        assert set(labels.text) == set(english.text), language
        assert set(labels.grounds) == set(get_args(SecondGround)), language
        assert set(labels.enclosures) == set(get_args(Enclosure)), language
        # Only the reason-box prefixes may be empty: the Tamil form has one, the others none.
        blank = [k for k, v in labels.text.items() if not v.strip() and not k.endswith("_from")]
        assert not blank, (language, blank)


# --- shared behaviour ------------------------------------------------------------------------


@pytest.mark.parametrize("name", [*CIC, "tnsic-en", "tnsic-ta"])
def test_footer_no_fee_line_and_no_official_look(name: str) -> None:
    doc = case(name)
    html = render_second_appeal_html(doc)
    text = visible(html)
    assert text.count(FOOTER_EN) == 1
    if doc.language != "en":
        assert FOOTER_LOCAL[doc.language] in text
    for tag in ("<img", "<svg", "<canvas", "<object", "<embed", "<picture", "<link"):
        assert tag not in html.lower(), tag
    assert "background-image" not in html and "http" not in html
    assert not re.search(r"\bseal\b|emblem|ashoka|satyamev|government of india", html, re.I)
    assert not re.search(r"(Rs\.?|₹)\s?\d", text)
    assert EM_DASH not in html


@pytest.mark.parametrize("name", [*CIC, "tnsic-en", "tnsic-ta"])
def test_metadata_carries_no_personal_data_and_rendering_is_deterministic(name: str) -> None:
    doc = case(name)
    html = render_second_appeal_html(doc)
    head = html.split("</head>")[0]
    for value in (doc.appellant_name, doc.appellant_address, doc.details, doc.authority_name):
        assert not value.strip() or value not in head
    assert html == render_second_appeal_html(doc)


def test_user_text_is_escaped_and_marked_with_its_language() -> None:
    doc = case(
        "cic-en",
        authority_name="R&D <Office>",
        appellant_phone="<b>1</b>",
        details="பதில் <வரவில்லை>",
        late=True,
        delay_reason="<script>x</script>",
    )
    html = render_second_appeal_html(doc)
    assert "<script" not in html and "<b>" not in html
    assert "R&amp;D &lt;Office&gt;" in html and "&lt;script&gt;x&lt;/script&gt;" in html
    assert '<span lang="ta">பதில் &lt;வரவில்லை&gt;</span>' in html


# --- the golden cases ------------------------------------------------------------------------


def test_golden_cases_use_fictional_appellants_only() -> None:
    markers = {"en": "Test", "hi": "परीक्षण", "ta": "சோதனை"}
    for name, data in CASES.items():
        assert str(data["appellant_name"]).startswith(markers[str(data["language"])]), name
        blob = str(data)
        assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", blob), name
        assert not re.search(r"\d{10,}|\d{4}\s\d{4}\s\d{4}|[1-9]\d{4}\s?\d{5}", blob), name
        assert data["prepared_on"] == "2026-10-27"


@pytest.mark.parametrize("name", list(CASES))
def test_golden_dates_agree_with_the_rules_engine(name: str) -> None:
    doc = case(name)
    rules = load_rules(doc.jurisdiction)
    computed = compute_deadlines(
        filed_on=doc.filed_on,
        received_on=None if doc.received_estimated else doc.received_on,
        via_apio=False,
        third_party=False,
        life_liberty=False,
        rules=rules,
    )
    assert computed.received_on == doc.received_on
    assert computed.pio_reply.due_on == doc.reply_due_on
    faa = faa_decision_deadlines(rules=rules, appeal_filed_on=doc.appeal_filed_on)
    window = second_appeal_deadline(
        faa, rules=rules, decision_received_on=doc.faa_decision_received_on
    )
    assert appeal_lateness(window, doc.prepared_on, rules=rules).late == doc.late
