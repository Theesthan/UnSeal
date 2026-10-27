"""Real PDF rendering with WeasyPrint (Pango and HarfBuzz shape Tamil and Devanagari).

These tests need WeasyPrint's system libraries. They skip where those are missing (a Windows
machine without Pango) and run in the Docker image built from apps/api/Dockerfile:

    docker run --rm unseal-api uv run pytest -q tests/pdf

The tests also write the golden outputs (PDF and a PNG of page 1 per language) to
tests/golden/pdf/ for visual review.

Text extraction caveat: pdfium (pypdfium2, and Chrome's viewer) stops reading a ToUnicode map at
the first empty entry, which WeasyPrint writes for glyphs that carry no text of their own. Hindi
and Tamil text therefore extracts with wrong letters even though the page looks right. Latin text,
digits and the numbering extract fine, so the text-layer checks below use those; the Hindi and
Tamil wording is checked on the HTML (tests/unit) and on the layout tree, and by eye on the PNGs.
"""

import importlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
import pytest
from pypdfium2.raw import FPDF_PAGEOBJ_TEXT

from unseal.pdf.models import ApplicationDocument
from unseal.pdf.render import render_application_html, render_application_pdf

try:
    weasyprint = importlib.import_module("weasyprint")
except (ImportError, OSError) as exc:  # OSError: Pango or HarfBuzz missing
    pytest.skip(
        f"WeasyPrint system libraries unavailable ({type(exc).__name__}); run in Docker",
        allow_module_level=True,
    )

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "pdf"
CASES = json.loads((GOLDEN / "cases.json").read_text("utf-8"))
LANGUAGES = ["en", "hi", "ta"]

FOOTER_EN = "Prepared with UnSeal. Not legal advice."
FOOTER_LOCAL = {
    "hi": "UnSeal द्वारा तैयार किया गया। यह कानूनी सलाह नहीं है।",
    "ta": "UnSeal மூலம் தயாரிக்கப்பட்டது. இது சட்ட ஆலோசனை அல்ல.",
}
SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


def case(language: str, **changes: object) -> ApplicationDocument:
    return ApplicationDocument.model_validate({**CASES[language], **changes})


def page_texts(pdf_bytes: bytes) -> list[str]:
    """NFC-normalised text of each page as pdfium extracts it, whitespace collapsed."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        return [
            unicodedata.normalize("NFC", " ".join(page.get_textpage().get_text_bounded().split()))
            for page in pdf
        ]
    finally:
        pdf.close()


def embedded_fonts(pdf_bytes: bytes) -> dict[str, bool]:
    """Every font the pages draw with: name (subset prefix removed) -> is the font file embedded."""
    found: dict[str, bool] = {}
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        for page in pdf:
            for text_object in page.get_objects(filter=[FPDF_PAGEOBJ_TEXT]):
                font = text_object.get_font()
                found[SUBSET_PREFIX.sub("", font.get_base_name())] = font.is_embedded
    finally:
        pdf.close()
    return found


def layout_page_texts(doc: ApplicationDocument) -> list[str]:
    """Text WeasyPrint laid out on each page, margin boxes (the footer) included.

    Uses WeasyPrint's box tree, which is not public API; the version is pinned in uv.lock.
    """

    def collect(box: Any) -> list[str]:
        own = [box.text] if hasattr(box, "text") else []
        return own + [t for child in getattr(box, "children", []) for t in collect(child)]

    rendered = weasyprint.HTML(string=render_application_html(doc)).render()
    return [
        unicodedata.normalize("NFC", " ".join(" ".join(collect(page._page_box)).split()))
        for page in rendered.pages
    ]


@pytest.fixture(scope="module")
def pdfs() -> dict[str, bytes]:
    return {language: render_application_pdf(case(language)) for language in LANGUAGES}


@pytest.mark.parametrize("language", LANGUAGES)
def test_renders_a_one_page_pdf(pdfs: dict[str, bytes], language: str) -> None:
    assert pdfs[language].startswith(b"%PDF-")
    assert len(page_texts(pdfs[language])) == 1


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", {"Noto-Sans", "Noto-Sans-Bold"}),
        ("hi", {"Noto-Sans-Devanagari", "Noto-Sans-Devanagari-Bold", "Noto-Sans"}),
        ("ta", {"Noto-Sans-Tamil", "Noto-Sans-Tamil-Bold", "Noto-Sans"}),
    ],
)
def test_the_noto_fonts_are_embedded(
    pdfs: dict[str, bytes], language: str, expected: set[str]
) -> None:
    fonts = embedded_fonts(pdfs[language])
    assert set(fonts) == expected, fonts  # these fonts and no other, so no system fallback
    assert all(fonts.values()), fonts  # every one carries its font file


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_text_layer_carries_the_english_footer(pdfs: dict[str, bytes], language: str) -> None:
    (text,) = page_texts(pdfs[language])
    assert FOOTER_EN in text


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_the_laid_out_page_carries_the_footer_in_the_document_language(language: str) -> None:
    (text,) = layout_page_texts(case(language))
    assert FOOTER_EN in text
    assert FOOTER_LOCAL[language] in text


def test_the_text_layer_carries_the_whole_english_letter(pdfs: dict[str, bytes]) -> None:
    (text,) = page_texts(pdfs["en"])
    data = CASES["en"]
    for needle in (data["applicant_name"], data["authority_name"], data["subject"], "Rs 10"):
        assert needle in text
    assert [token for token in text.split() if re.fullmatch(r"\d\.", token)] == ["1.", "2.", "3."]


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_the_text_layer_carries_the_numbers_of_an_indic_letter(
    pdfs: dict[str, bytes], language: str
) -> None:
    (text,) = page_texts(pdfs[language])
    for token in ("2005", "2025-26", "₹10", "27", "2026", "1.", "2.", "3."):
        assert token in text.split() or token in text, token


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_page_of_a_long_letter_carries_the_footer(language: str) -> None:
    questions = [f"{CASES[language]['questions'][0]} ({n})" for n in range(1, 41)]
    doc = case(language, questions=questions)
    texts = page_texts(render_application_pdf(doc))
    laid_out = layout_page_texts(doc)
    assert len(texts) >= 3
    assert len(laid_out) == len(texts)
    for number, (text, laid) in enumerate(zip(texts, laid_out, strict=True), start=1):
        assert FOOTER_EN in text, f"page {number}"
        assert FOOTER_EN in laid, f"page {number}"
        if language != "en":
            assert FOOTER_LOCAL[language] in laid, f"page {number}"


@pytest.mark.parametrize("count", range(12, 32))
def test_the_signature_block_is_never_alone_on_a_page(count: int) -> None:
    # Wherever the page break falls, the fee, closing and signature stay on the last page together
    # with at least one question. The counts bracket the point where the break meets the tail.
    questions = [f"Question number {n} about the same work order." for n in range(1, count + 1)]
    last = page_texts(render_application_pdf(case("en", questions=questions)))[-1]
    for needle in ("Application fee", "Yours faithfully", "Signature", "Applicant"):
        assert needle in last, needle
    assert re.search(r"Question number \d+ about", last)


def test_a_long_unbroken_word_wraps_inside_the_page() -> None:
    word = "W" * 220
    doc = case("en", authority_name=word, pio_address=f"{word}\nChennai", subject=word)
    pdf = pdfium.PdfDocument(render_application_pdf(doc))
    try:
        for page in pdf:
            width, _ = page.get_size()
            right_margin = 20 / 25.4 * 72  # the template's 20 mm page margin, in points
            for text_object in page.get_objects(filter=[FPDF_PAGEOBJ_TEXT]):
                _, _, right, _ = text_object.get_bounds()
                assert right <= width - right_margin + 1, right
    finally:
        pdf.close()


@pytest.mark.parametrize("language", LANGUAGES)
def test_pdf_metadata_is_generic(pdfs: dict[str, bytes], language: str) -> None:
    pdf = pdfium.PdfDocument(pdfs[language])
    try:
        metadata = pdf.get_metadata_dict(skip_empty=True)
    finally:
        pdf.close()
    assert metadata.get("Title")
    data = CASES[language]
    for value in metadata.values():
        assert data["applicant_name"] not in value
        assert data["applicant_address"] not in value


@pytest.mark.parametrize("language", LANGUAGES)
def test_rendering_the_same_document_twice_gives_the_same_pdf(language: str) -> None:
    assert render_application_pdf(case(language)) == render_application_pdf(case(language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_writes_the_golden_pdf_and_a_page_one_preview(
    pdfs: dict[str, bytes], language: str
) -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / f"application-{language}.pdf").write_bytes(pdfs[language])
    pdf = pdfium.PdfDocument(pdfs[language])
    try:
        image = pdf[0].render(scale=2).to_pil()  # 2x of 72 dpi: 1190 x 1684 px for A4
        image.save(GOLDEN / f"application-{language}-page1.png")
    finally:
        pdf.close()
    assert (GOLDEN / f"application-{language}-page1.png").stat().st_size > 10_000
