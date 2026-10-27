"""Bot strings: every key in English, Hindi and Tamil, the same placeholders in each, glossary
terms filled in, and the writing rules (no em dash)."""

from datetime import date
from string import Formatter

from unseal.bot.texts import TEXTS, format_date, t

LANGUAGES = {"en", "hi", "ta"}
EM_DASH = chr(0x2014)  # the writing rules ban it


def fields(template: str) -> frozenset[str]:
    return frozenset(name for _, name, _, _ in Formatter().parse(template) if name)


def test_every_text_exists_in_all_three_languages() -> None:
    assert len(TEXTS) > 50
    for key, by_language in TEXTS.items():
        assert set(by_language) == LANGUAGES, key
        assert all(text.strip() for text in by_language.values()), key


def test_placeholders_are_the_same_in_every_language() -> None:
    for key, by_language in TEXTS.items():
        assert len({fields(text) for text in by_language.values()}) == 1, key


def test_no_em_dash_anywhere() -> None:
    assert not [key for key, texts in TEXTS.items() if any(EM_DASH in v for v in texts.values())]


def test_glossary_terms_are_filled_in() -> None:
    assert "பொதுத் தகவல் அலுவலர்" in t("authority_address", "ta")
    assert "लोक सूचना अधिकारी" in t("authority_address", "hi")
    assert "Public Information Officer" in t("authority_address", "en")
    assert "சட்டம், 2005" in t("privacy", "ta") and "अधिनियम, 2005" in t("privacy", "hi")
    assert "{" not in t("privacy", "ta")


def test_privacy_notice_offers_deletion_in_every_language() -> None:
    assert all("/delete" in t("privacy", language) for language in LANGUAGES)


def test_unknown_language_falls_back_to_english() -> None:
    assert t("busy", "xx") == t("busy", "en")


def test_dates_use_the_month_names_of_the_language() -> None:
    day = date(2027, 1, 2)
    assert format_date(day, "en") == "2 January 2027"
    assert format_date(day, "hi") == "2 जनवरी 2027"
    assert format_date(day, "ta") == "2 ஜனவரி 2027"
