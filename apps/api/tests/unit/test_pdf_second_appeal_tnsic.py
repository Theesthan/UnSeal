"""The second appeal on the Tamil Nadu Information Commission form (FR-12, S. 19(3)).

The form: https://tnsic.gov.in/pdf/guidelines/appeal_format/sa_eng.pdf (English) and
https://tnsic.gov.in/pdf/guidelines/appeal_format/sa_tam.pdf (Tamil). Fields UnSeal does not hold
are printed blank to fill by hand; Yes/No answers and tick boxes come from the case.
"""

import re

import pytest
from test_pdf_second_appeal_support import case, options, parse, visible

from unseal.pdf.models import SecondGround
from unseal.pdf.second_appeal import TNSIC_REASON_BY_GROUND, render_second_appeal_html
from unseal.pdf.second_appeal_labels import second_appeal_labels

REASONS = ["not_furnished", "not_satisfactory", "partial", "improper"]
EN_REASONS_19_3 = [
    "Reply not furnished by the PIO/First Appellate Authority",
    "Reply not satisfactory",
    "Partial reply",
    "Improper reply",
]
EN_DECLARATION = (
    "I, Test Appellant, S/o or D/o or W/o , the appellant herein, do hereby declare that the "
    "details and particulars furnished above are true and correct to the best of my knowledge "
    "and belief and I have not suppressed any material fact. I have not preferred any appeal "
    "previously to the Commission on the same issues raised in this appeal."
)
# Rows of the official Tamil form, read from its text layer (sa_tam.pdf), with the section
# numbers as the real rules give them.
TA_OFFICIAL = [
    "மேல்முறையீட்டாளர் விவரங்கள்",
    "தந்தை/ கணவர்/ காப்பாளர் பெயர்",
    "அலைபேசி எண்",
    "அஞ்சல் குறியீடு எண்",
    "பிரிவு 6(1)-ன் கீழ் பொதுத் தகவல் அலுவலருக்கு அளித்த மனு நாள்",
    "பிரிவு 6(1)-ன் கீழ் அளித்த மனுவானது சட்டப்பிரிவு 6(3)-ன் கீழ் பிற பொதுத் தகவல் அலுவலருக்கு மாற்றப்பட்டுள்ளது",
    "பிரிவு 19(1)-ன் கீழ் முதல் மேல் முறையீட்டு அலுவலருக்கு அளித்த மனு நாள்",
    "பிரிவு 19(3)-ன் கீழ் இரண்டாம் மேல் முறையீடு செய்வதற்கான காரணம்",
    "காணொளி காட்சி விசாரணை",
    "நேரடி விசாரணை",
    "நான் இதற்கு முன்னர் இதே பொருள் குறித்து ஆணையத்திடம் எந்த மேல்முறையீடும் செய்யவில்லை என்றும் உறுதியளிக்கிறேன்.",
    "மேல்முறையீட்டாளரின் கையொப்பம்",
]


def part(html: str, name: str) -> str:
    return html.split(f'<section class="part" id="{name}">', 1)[1].split("</section>", 1)[0]


def rows(html: str, name: str) -> list[list[str]]:
    return parse(part(html, name)).cells


def row(html: str, name: str, number: int) -> str:
    """The HTML of numbered row `number` in part `name`."""
    return part(html, name).split("<tr>")[number]


# --- structure -------------------------------------------------------------------------------


def test_header_title_and_parts_follow_the_form() -> None:
    html = render_second_appeal_html(case("tnsic-en"))
    assert '<main class="tnsic">' in html
    assert "Before the Tamil Nadu Information Commission" in visible(html)
    title = (
        "Second appeal under Section 19(3) of the Right to Information Act, 2005, with necessary "
        "copies enclosed"
    )
    assert f"<h1>{title}</h1>" in html
    headings = [visible(h) for h in re.findall(r"<h2>(.*?)</h2>", html, re.S)]
    assert headings == [
        "Details of Appellant",
        "I. Details of petition under section 6(1) of the Right to Information Act, 2005",
        "II. Details of first appeal under section 19(1) of the Right to Information Act, 2005",
        "III. Details of second appeal under section 19(3) of the Right to Information Act, 2005",
        "IV. Details of hearing mode",
        "Verification",
        "Copies enclosed",
    ]


def test_the_appellant_details_leave_what_unseal_does_not_hold_blank() -> None:
    html = render_second_appeal_html(case("tnsic-en"))
    assert rows(html, "appellant") == [
        ["Name*", "Test Appellant"],
        ["Father/Husband/Guardian Name*", ""],
        ["Mobile Number*", "00000 00000"],
        ["Email", ""],
        ["Gender", ""],
        ["Date of Birth & Age", ""],
        ["Country", ""],
        ["State", ""],
        ["District", ""],
        ["Address*", "12 Example Street Chennai"],
        ["Pin Code", ""],
    ]
    assert part(html, "appellant").count('<span class="blank"></span>') == 8
    no_phone = render_second_appeal_html(case("tnsic-en", appellant_phone=None))
    assert rows(no_phone, "appellant")[2] == ["Mobile Number*", ""]
    assert part(no_phone, "appellant").count('<span class="blank"></span>') == 9


def test_part_1_without_a_transfer() -> None:
    html = render_second_appeal_html(case("tnsic-en"))
    cells = rows(html, "part-1")
    assert [c[:2] for c in cells] == [
        ["1", "Date of petition to the PIO under section 6(1)*"],
        ["2", "Details of PIO*"],
        ["3", "Copy of petition under section 6(1) to be enclosed*"],
        ["4", "Reply received from the PIO to the petition under section 6(1)"],
        ["5", "If yes, copy of the reply to be enclosed"],
        [
            "6",
            "Whether the petition under section 6(1) has been transferred to any other PIO "
            "under section 6(3)",
        ],
        ["7", "If yes, copy of the letter to be enclosed"],
        ["8", "Details of any other/new PIO to whom the petition was transferred*"],
        ["9", "Reply received from the new PIO to whom the petition was transferred"],
        ["10", "If yes, copy of the reply to be enclosed"],
    ]
    values = [c[2] for c in cells]
    assert values[0] == "15 June 2026"
    assert values[1] == (
        "Public Information Officer, Example Municipal Corporation Civic Centre, 1 Example Road "
        "Chennai"
    )
    assert values[2] == "Enclosed" and values[4] == "Enclosed"
    assert values[3].endswith("(received on 15 July 2026)")
    assert options(row(html, "part-1", 4)) == [("Yes", True), ("No", False)]
    assert options(row(html, "part-1", 6)) == [("Yes", False), ("No", True)]
    assert values[6:] == ["Not applicable"] * 4


def test_part_1_with_a_transfer_and_no_reply() -> None:
    html = render_second_appeal_html(
        case(
            "tnsic-en",
            transferred_to="Zone <3> Office",
            reply_received_on=None,
            grounds=["no_reply"],
        )
    )
    values = [c[2] for c in rows(html, "part-1")]
    assert options(row(html, "part-1", 4)) == [("Yes", False), ("No", True)]
    assert values[4] == "Not applicable"
    assert options(row(html, "part-1", 6)) == [("Yes", True), ("No", False)]
    assert values[6] == "Enclosed" and values[7] == "Zone <3> Office"
    # Which PIO answered is not on record: the appellant fills rows 9 and 10 by hand.
    assert options(row(html, "part-1", 9)) == [("Yes", False), ("No", False)]
    assert '<span class="blank"></span>' in row(html, "part-1", 10)


def test_part_2_ticks_no_reply_only_when_there_was_none() -> None:
    html = render_second_appeal_html(case("tnsic-en"))
    values = [c[2] for c in rows(html, "part-2")]
    assert values[0] == "1 August 2026"
    assert values[1].startswith("First Appellate Authority, Example Municipal Corporation Deputy")
    assert values[2] == "Enclosed" and values[5] == "Enclosed"
    assert [ticked for _, ticked in options(row(html, "part-2", 4))] == [False] * 4
    assert options(row(html, "part-2", 5)) == [("Yes", True), ("No", False)]
    assert values[4].endswith("(received on 28 August 2026)")
    silent = render_second_appeal_html(case("tnsic-ta"))
    assert [ticked for _, ticked in options(row(silent, "part-2", 4))] == [
        True,
        False,
        False,
        False,
    ]
    assert options(row(silent, "part-2", 5))[1][1] is True
    assert [c[2] for c in rows(silent, "part-2")][5] == "பொருந்தாது"


@pytest.mark.parametrize("ground", list(TNSIC_REASON_BY_GROUND))
def test_part_3_ticks_the_reason_each_ground_maps_to(ground: SecondGround) -> None:
    doc = case("tnsic-en", reply_received_on=None, faa_decision_received_on=None, grounds=[ground])
    found = options(row(render_second_appeal_html(doc), "part-3", 1))
    assert [label for label, _ in found] == EN_REASONS_19_3
    expected = REASONS.index(TNSIC_REASON_BY_GROUND[ground])
    assert [ticked for _, ticked in found] == [i == expected for i in range(4)]


def test_the_ground_to_reason_mapping() -> None:
    assert TNSIC_REASON_BY_GROUND == {
        "no_reply": "not_furnished",
        "no_decision": "not_furnished",
        "refused": "not_satisfactory",
        "fee_demanded": "not_satisfactory",
        "incomplete": "partial",
        "incorrect": "improper",
    }
    html = render_second_appeal_html(case("tnsic-en"))  # refused and fee_demanded: one box
    assert [t for _, t in options(row(html, "part-3", 1))] == [False, True, False, False]


def test_part_3_grievance_and_complaint_question() -> None:
    doc = case("tnsic-en", details="Refused <without> reason.")
    html = render_second_appeal_html(doc)
    assert "Refused &lt;without&gt; reason." in row(html, "part-3", 2)
    complaint = row(html, "part-3", 3)
    assert "complaint petition" in visible(complaint)
    assert "18" not in visible(complaint)  # no rule carries that section: worded without it
    assert options(complaint) == [("Yes", False), ("No", False)]
    blank = render_second_appeal_html(case("tnsic-en", details=""))
    assert '<span class="blank wide"></span>' in row(blank, "part-3", 2)


def test_a_late_appeal_adds_the_delay_paragraph_to_the_grievance() -> None:
    html = render_second_appeal_html(case("tnsic-en", late=True, delay_reason="I was <ill>."))
    grievance = visible(row(html, "part-3", 2))
    assert "This second appeal is filed after the time limit." in grievance
    assert grievance.endswith("I was <ill>.")
    assert "time limit" not in visible(render_second_appeal_html(case("tnsic-en")))


@pytest.mark.parametrize(
    ("mode", "ticks"),
    [("virtual", [True, False]), ("direct", [False, True]), (None, [False, False])],
)
def test_part_4_hearing_mode(mode: str | None, ticks: list[bool]) -> None:
    html = render_second_appeal_html(case("tnsic-en", hearing_mode=mode))
    assert options(part(html, "part-4")) == [("Virtual", ticks[0]), ("Direct", ticks[1])]


def test_verification_and_signature() -> None:
    html = render_second_appeal_html(case("tnsic-en"))
    verification = part(html, "verification")
    assert EN_DECLARATION in visible(verification)
    assert '<span class="blank"></span>' in verification.split("S/o or D/o or W/o")[1][:40]
    assert '<span class="signature-line" aria-hidden="true"></span>' in html
    assert "*Signature of the Appellant" in visible(html)


def test_copies_enclosed_follow_the_case() -> None:
    def annex(html: str) -> list[str]:
        return parse(html.split('<section class="enclosures">', 1)[1]).items

    assert annex(render_second_appeal_html(case("tnsic-en"))) == [
        "Copy of the petition under section 6(1)",
        "Copy of the reply from the PIO",
        "Copy of the appeal petition under section 19(1)",
        "Copy of the reply from the First Appellate Authority",
    ]
    assert (
        len(annex(render_second_appeal_html(case("tnsic-ta")))) == 3
    )  # petition, transfer, appeal


# --- Tamil and Hindi -------------------------------------------------------------------------


def test_the_tamil_form_uses_the_official_wording() -> None:
    text = visible(render_second_appeal_html(case("tnsic-ta", hearing_mode="direct")))
    for wording in TA_OFFICIAL:
        assert wording in text, wording


def test_no_english_label_leaks_into_a_tamil_or_hindi_form() -> None:
    english = second_appeal_labels("tnsic_form", "en").text
    for name, changes in (("tnsic-ta", {}), ("tnsic-ta", {"language": "hi"})):
        text = visible(render_second_appeal_html(case(name, **changes)))
        for key in ("guardian", "mobile", "hearing", "verification", "virtual", "enclosed"):
            assert english[key].rstrip("*") not in text, (changes, key)
