"""Real first appeal PDFs with WeasyPrint (Pango and HarfBuzz shape Tamil and Devanagari).

Like test_pdf_render.py these tests skip where WeasyPrint's system libraries are missing and run in
the Docker image built from apps/api/Dockerfile:

    docker run --rm unseal-api uv run pytest -q tests/pdf

They also write the golden outputs (appeal-<language>.pdf and a PNG of page 1) to tests/golden/pdf/
for visual review. pdfium extracts Hindi and Tamil with wrong letters (see test_pdf_render.py), so
the Indic wording is checked on WeasyPrint's layout tree and the text layer is used for Latin text,
digits and the numbering.
"""

import importlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

import pypdfium2 as pdfium
import pytest
from pypdfium2.raw import FPDF_PAGEOBJ_TEXT

from unseal.pdf.appeal import render_appeal_html, render_appeal_pdf
from unseal.pdf.appeal_labels import appeal_labels_for
from unseal.pdf.models import AppealDocument

try:
    weasyprint = importlib.import_module("weasyprint")
except (ImportError, OSError) as exc:  # OSError: Pango or HarfBuzz missing
    pytest.skip(
        f"WeasyPrint system libraries unavailable ({type(exc).__name__}); run in Docker",
        allow_module_level=True,
    )

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "pdf"
CASES = json.loads((GOLDEN / "appeal_cases.json").read_text("utf-8"))
LANGUAGES = ["en", "hi", "ta"]

FOOTER_EN = "Prepared with UnSeal. Not legal advice."
FOOTER_LOCAL = {
    "hi": "UnSeal द्वारा तैयार किया गया। यह कानूनी सलाह नहीं है।",
    "ta": "UnSeal மூலம் தயாரிக்கப்பட்டது. இது சட்ட ஆலோசனை அல்ல.",
}
SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


def case(language: str, **changes: object) -> AppealDocument:
    return AppealDocument.model_validate({**CASES[language], **changes})


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


def layout_page_texts(doc: AppealDocument) -> list[str]:
    """Text WeasyPrint laid out on each page, the footer included (not public API; see
    test_pdf_render.py)."""

    def collect(box: Any) -> list[str]:
        own = [box.text] if hasattr(box, "text") else []
        return own + [t for child in getattr(box, "children", []) for t in collect(child)]

    rendered = weasyprint.HTML(string=render_appeal_html(doc)).render()
    return [
        unicodedata.normalize("NFC", " ".join(" ".join(collect(page._page_box)).split()))
        for page in rendered.pages
    ]


def details_of(lines: int) -> str:
    return "\n".join(f"Line {n} of the appellant's account of what happened." for n in range(lines))


@pytest.fixture(scope="module")
def pdfs() -> dict[str, bytes]:
    return {language: render_appeal_pdf(case(language)) for language in LANGUAGES}


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
    assert all(fonts.values()), fonts


def test_the_text_layer_carries_the_whole_english_letter(pdfs: dict[str, bytes]) -> None:
    (text,) = page_texts(pdfs["en"])
    for needle in (
        "First appeal under Section 19(1) of the Right to Information Act, 2005",
        "First Appellate Authority",
        CASES["en"]["appellant_name"],
        CASES["en"]["authority_name"],
        "25 August 2026",
        "1 September 2026 (estimated)",
        "1 October 2026",
        "No reply was received",
        "under Section 7(2) of the Act",
        "Relief sought",
        "27 October 2026",
        FOOTER_EN,
    ):
        assert needle in text, needle
    assert [token for token in text.split() if re.fullmatch(r"\d\.", token)] == ["1."]
    assert not re.search(r"(Rs|₹)\s?\d", text)  # no fee line


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_the_laid_out_indic_letter_carries_its_wording(language: Literal["hi", "ta"]) -> None:
    doc = case(language)
    labels = appeal_labels_for(language)
    (text,) = layout_page_texts(doc)
    extra = [labels.delay, doc.delay_reason] if doc.late else []
    extra += [doc.details] if doc.details.strip() else []
    for needle in (
        labels.title.format(section="19(1)"),
        labels.authority,
        doc.appellant_name,
        labels.relief,
        FOOTER_EN,
        FOOTER_LOCAL[language],
        *[labels.grounds[code] for code in doc.grounds],
        *extra,
    ):
        assert needle in text, needle


def test_a_late_tamil_appeal_keeps_relief_delay_and_signature_together() -> None:
    # The longest golden variant: Tamil, with details, late, with a reason. It runs to two pages;
    # the unbreakable tail moves to the second page whole.
    reason = "பதில் கிடைத்த பிறகு நான் மருத்துவமனையில் சிகிச்சை பெற்றேன்."
    doc = case("ta", late=True, delay_reason=reason)
    labels = appeal_labels_for("ta")
    pages = layout_page_texts(doc)
    assert len(pages) == 2
    for needle in (labels.relief, labels.delay, reason, labels.closing, doc.appellant_name):
        assert needle in pages[-1], needle
    assert labels.relief not in pages[0]


@pytest.mark.parametrize("language", ["hi", "ta"])
def test_the_text_layer_carries_the_numbers_of_an_indic_letter(
    pdfs: dict[str, bytes], language: str
) -> None:
    (text,) = page_texts(pdfs[language])
    for token in ("19(1)", "2005", "27", "2026", "1.", FOOTER_EN):
        assert token in text, token


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_page_of_a_long_appeal_carries_the_footer(language: str) -> None:
    doc = case(language, details=details_of(60))
    texts = page_texts(render_appeal_pdf(doc))
    laid_out = layout_page_texts(doc)
    assert len(texts) >= 2
    assert len(laid_out) == len(texts)
    for number, (text, laid) in enumerate(zip(texts, laid_out, strict=True), start=1):
        assert FOOTER_EN in text, f"page {number}"
        if language != "en":
            assert FOOTER_LOCAL[language] in laid, f"page {number}"


@pytest.mark.parametrize("lines", range(4, 34, 2))
def test_the_signature_is_never_parted_from_the_relief(lines: int) -> None:
    # Wherever the page break falls, the relief, the delay paragraph, the closing and the
    # signature stay together on the last page. The counts bracket the break meeting the tail.
    doc = case("en", details=details_of(lines), late=True, delay_reason="I was unwell.")
    last = page_texts(render_appeal_pdf(doc))[-1]
    for needle in ("Relief sought", "Delay in filing", "I was unwell.", "Yours faithfully"):
        assert needle in last, needle
    assert "Signature" in last and "Appellant" in last


def test_a_long_unbroken_word_wraps_inside_the_page() -> None:
    word = "W" * 220
    doc = case("en", authority_name=word, faa_address=f"{word}\nChennai", details=word)
    pdf = pdfium.PdfDocument(render_appeal_pdf(doc))
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
    personal = ("appellant_name", "appellant_address", "details", "delay_reason", "authority_name")
    for value in metadata.values():
        for field in personal:
            assert not data[field].strip() or data[field] not in value, field


@pytest.mark.parametrize("language", LANGUAGES)
def test_rendering_the_same_document_twice_gives_the_same_pdf(language: str) -> None:
    assert render_appeal_pdf(case(language)) == render_appeal_pdf(case(language))


@pytest.mark.parametrize("language", LANGUAGES)
def test_writes_the_golden_pdf_and_a_page_one_preview(
    pdfs: dict[str, bytes], language: str
) -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / f"appeal-{language}.pdf").write_bytes(pdfs[language])
    pdf = pdfium.PdfDocument(pdfs[language])
    try:
        image = pdf[0].render(scale=2).to_pil()  # 2x of 72 dpi: 1190 x 1684 px for A4
        image.save(GOLDEN / f"appeal-{language}-page1.png")
    finally:
        pdf.close()
    assert (GOLDEN / f"appeal-{language}-page1.png").stat().st_size > 10_000
