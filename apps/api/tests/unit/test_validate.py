"""FR-3 validator: code checks before export. Only missing mandatory fields block."""

from unseal.harness.validate import Draft, validate
from unseal.rules.engine import load_rules

CENTRAL = load_rules("central")
WORD_LIMIT = CENTRAL.local.word_limit.words if CENTRAL.local.word_limit else 0


def draft(**changes: object) -> Draft:
    base: dict[str, object] = {
        "jurisdiction": "central",
        "questions": ("Certified copy of the evaluated answer book",),
        "personal_information": False,
        "pio_address": "Public Information Officer, Example Board, New Delhi",
        "applicant_address": "12 Example Street, Chennai",
    }
    return Draft.model_validate({**base, **changes})


def codes(d: Draft) -> dict[str, str]:
    return {flag.code: flag.severity for flag in validate(d)}


def test_a_complete_draft_has_no_flags() -> None:
    assert validate(draft()) == ()


def test_missing_addresses_block_export() -> None:
    assert codes(draft(pio_address="  ")) == {"missing_pio_address": "block"}
    assert codes(draft(applicant_address="")) == {"missing_applicant_address": "block"}
    assert codes(draft(questions=())) == {"no_questions": "block"}


def test_over_the_word_limit_only_warns() -> None:
    long_question = " ".join(["record"] * (WORD_LIMIT + 1))
    assert codes(draft(questions=(long_question,))) == {"over_word_limit": "warn"}
    exactly = " ".join(["record"] * WORD_LIMIT)
    assert codes(draft(questions=(exactly,))) == {}


def test_tamil_nadu_has_no_word_limit_rule() -> None:
    long_question = " ".join(["பதிவு"] * (WORD_LIMIT + 50))
    assert codes(draft(jurisdiction="tamil_nadu", questions=(long_question,))) == {}


def test_personal_information_warns_with_its_legal_basis() -> None:
    (flag,) = validate(draft(personal_information=True))
    assert (flag.code, flag.severity) == ("personal_information", "warn")
    assert flag.basis == CENTRAL.act.personal_information.basis
    assert flag.under_challenge is CENTRAL.act.personal_information.under_challenge


def test_a_leftover_why_question_warns_in_every_language() -> None:
    for question in ("Why was my mark low?", "மதிப்பெண் ஏன் குறைவு?", "अंक क्यों कम हैं?"):
        found = validate(draft(questions=(question,)))
        assert [(f.code, f.severity, f.question) for f in found] == [("opinion_ask", "warn", 0)]
