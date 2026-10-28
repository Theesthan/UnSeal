"""Real second appeal PDFs with WeasyPrint (Pango and HarfBuzz shape Tamil and Devanagari).

Like test_pdf_render.py these skip where WeasyPrint's system libraries are missing and run in the
Docker image (docker run --rm unseal-api uv run pytest -q tests/pdf). They write the goldens,
second-appeal-<case>.pdf and a PNG of page 1, to tests/golden/pdf/ for visual review. pdfium
extracts Hindi and Tamil with wrong letters (see test_pdf_render.py), so Indic wording is checked
on WeasyPrint's layout tree and the text layer is used for Latin text and digits.
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

from unseal.pdf.models import SecondAppealDocument
from unseal.pdf.second_appeal import render_second_appeal_html, render_second_appeal_pdf

try:
    weasyprint = importlib.import_module("weasyprint")
except (ImportError, OSError) as exc:  # OSError: Pango or HarfBuzz missing
    pytest.skip(
        f"WeasyPrint system libraries unavailable ({type(exc).__name__}); run in Docker",
        allow_module_level=True,
    )

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "pdf"
CASES = json.loads((GOLDEN / "second-appeal-cases.json").read_text("utf-8"))
NAMES = list(CASES)
FOOTER_EN = "Prepared with UnSeal. Not legal advice."
FOOTER_LOCAL = {
    "hi": "UnSeal द्वारा तैयार किया गया। यह कानूनी सलाह नहीं है।",
    "ta": "UnSeal மூலம் தயாரிக்கப்பட்டது. இது சட்ட ஆலோசனை அல்ல.",
}
SCRIPT_FONT = {"en": None, "hi": "Noto-Sans-Devanagari", "ta": "Noto-Sans-Tamil"}
SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
# The Gazette's Hindi Appendix items (RTIRules2012_Hindi.pdf) and rows of the TNSIC Tamil form.
HI_ITEMS = ["अपीलार्थी का नाम और पता", "आवेदन की विशिष्टियां", "अपीलार्थी द्वारा सत्यापन/अधिप्रमाणन"]
TA_FORM = ["மேல்முறையீட்டாளர் விவரங்கள்", "அலைபேசி எண்", "விசாரணை முறை", "மேல்முறையீட்டாளரின் கையொப்பம்"]


def case(name: str, **changes: object) -> SecondAppealDocument:
    return SecondAppealDocument.model_validate({**CASES[name], **changes})


def page_texts(pdf_bytes: bytes) -> list[str]:
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        return [
            unicodedata.normalize("NFC", " ".join(page.get_textpage().get_text_bounded().split()))
            for page in pdf
        ]
    finally:
        pdf.close()


def embedded_fonts(pdf_bytes: bytes) -> dict[str, bool]:
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


def layout_page_texts(doc: SecondAppealDocument) -> list[str]:
    """Text WeasyPrint laid out on each page, footer included (not public API)."""

    def collect(box: Any) -> list[str]:
        own = [box.text] if hasattr(box, "text") else []
        return own + [t for child in getattr(box, "children", []) for t in collect(child)]

    rendered = weasyprint.HTML(string=render_second_appeal_html(doc)).render()
    return [
        unicodedata.normalize("NFC", " ".join(" ".join(collect(page._page_box)).split()))
        for page in rendered.pages
    ]


def details_of(lines: int) -> str:
    return "\n".join(f"Line {n} of the appellant's account of what happened." for n in range(lines))


@pytest.fixture(scope="module")
def pdfs() -> dict[str, bytes]:
    return {name: render_second_appeal_pdf(case(name)) for name in NAMES}


# A filled TNSIC form (11 appellant rows, parts I to IV, verification) and a Tamil CIC appeal
# run to three or four pages at a legible size; the cap only catches a runaway layout.
MAX_PAGES = 4


@pytest.mark.parametrize("name", NAMES)
def test_renders_a_pdf_of_at_most_four_pages(pdfs: dict[str, bytes], name: str) -> None:
    assert pdfs[name].startswith(b"%PDF-")
    assert 1 <= len(page_texts(pdfs[name])) <= MAX_PAGES


@pytest.mark.parametrize("name", NAMES)
def test_only_the_embedded_noto_fonts_are_used(pdfs: dict[str, bytes], name: str) -> None:
    fonts = embedded_fonts(pdfs[name])
    script = SCRIPT_FONT[CASES[name]["language"]]
    allowed = {"Noto-Sans", "Noto-Sans-Bold"} | ({script, f"{script}-Bold"} if script else set())
    assert set(fonts) <= allowed, fonts  # no system fallback font
    assert (script or "Noto-Sans") in fonts
    assert all(fonts.values()), fonts


def test_the_text_layer_carries_the_english_cic_appeal(pdfs: dict[str, bytes]) -> None:
    text = " ".join(page_texts(pdfs["cic-en"]))
    for needle in (
        "Before the Central Information Commission",
        "Second appeal under Section 19(3) of the Right to Information Act, 2005",
        "Name and address of the appellant",
        "Phone: 00000 00000",
        "11 May 2026 (estimated)",
        "No order was passed by the First Appellate Authority",
        "under Section 7(2) of the Act",
        "allowed by Section 19(6) of the Act",
        "Verification/authentication by the appellant",
        "Documents enclosed",
        FOOTER_EN,
    ):
        assert needle in text, needle
    assert "11." in text.split()
    assert not re.search(r"(Rs|₹)\s?\d", text)


def test_the_text_layer_carries_the_english_tnsic_form(pdfs: dict[str, bytes]) -> None:
    text = " ".join(page_texts(pdfs["tnsic-en"]))
    for needle in (
        "Before the Tamil Nadu Information Commission",
        "Father/Husband/Guardian Name*",
        "Mobile Number* 00000 00000",
        "Reply not furnished by the PIO/First Appellate Authority",
        "IV. Details of hearing mode",
        "Verification",
        "*Signature of the Appellant",
        "Copies enclosed",
        FOOTER_EN,
    ):
        assert needle in text, needle
    assert "X" in text.split()  # the ticks


@pytest.mark.parametrize(("name", "wording"), [("cic-hi", HI_ITEMS), ("tnsic-ta", TA_FORM)])
def test_the_laid_out_indic_forms_carry_the_official_wording(name: str, wording: list[str]) -> None:
    text = " ".join(layout_page_texts(case(name)))
    for needle in [*wording, FOOTER_LOCAL[CASES[name]["language"]]]:
        assert needle in text, needle


@pytest.mark.parametrize("name", NAMES)
def test_every_page_carries_the_footer(name: str) -> None:
    doc = case(name, details=details_of(50))
    texts = page_texts(render_second_appeal_pdf(doc))
    laid_out = layout_page_texts(doc)
    assert len(texts) >= 2 and len(laid_out) == len(texts)
    for number, (text, laid) in enumerate(zip(texts, laid_out, strict=True), start=1):
        assert FOOTER_EN in text, f"page {number}"
        if doc.language != "en":
            assert FOOTER_LOCAL[doc.language] in laid, f"page {number}"


@pytest.mark.parametrize(
    ("name", "heading", "before"),
    [
        ("cic-en", "Verification/authentication by the appellant", "Any other information"),
        ("tnsic-en", "Verification", "IV. Details of hearing mode"),
    ],
)
@pytest.mark.parametrize("lines", range(0, 40, 3))
def test_the_verification_is_never_alone_at_the_top_of_a_page(
    name: str, heading: str, before: str, lines: int
) -> None:
    # Wherever the page break falls, the verification shares its page with the part before it,
    # and the signature block stays with the verification.
    doc = case(name, details=details_of(lines), late=True, delay_reason="I was unwell.")
    pages = page_texts(render_second_appeal_pdf(doc))
    (page,) = [p for p in pages if f"{heading} " in p or p.endswith(heading)]
    assert before in page
    assert page.index(before) < page.index(heading)
    for needle in ("Signature", "Appellant", "27 October 2026"):
        assert needle in page[page.index(heading) :], needle


def test_a_long_unbroken_word_wraps_inside_the_page() -> None:
    word = "W" * 220
    for name in ("cic-en", "tnsic-en"):
        doc = case(name, authority_name=word, faa_address=f"{word}\nChennai", details=word)
        pdf = pdfium.PdfDocument(render_second_appeal_pdf(doc))
        try:
            for page in pdf:
                width, _ = page.get_size()
                right_margin = 20 / 25.4 * 72  # the shared 20 mm page margin, in points
                for text_object in page.get_objects(filter=[FPDF_PAGEOBJ_TEXT]):
                    _, _, right, _ = text_object.get_bounds()
                    assert right <= width - right_margin + 1, (name, right)
        finally:
            pdf.close()


@pytest.mark.parametrize("name", NAMES)
def test_pdf_metadata_is_generic_and_rendering_is_deterministic(
    pdfs: dict[str, bytes], name: str
) -> None:
    pdf = pdfium.PdfDocument(pdfs[name])
    try:
        metadata = pdf.get_metadata_dict(skip_empty=True)
    finally:
        pdf.close()
    assert metadata.get("Title")
    data = CASES[name]
    for value in metadata.values():
        for field in ("appellant_name", "appellant_address", "details", "authority_name"):
            assert not data[field].strip() or data[field] not in value, field
    assert render_second_appeal_pdf(case(name)) == pdfs[name]


@pytest.mark.parametrize("name", NAMES)
def test_writes_the_golden_pdf_and_a_page_one_preview(pdfs: dict[str, bytes], name: str) -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / f"second-appeal-{name}.pdf").write_bytes(pdfs[name])
    pdf = pdfium.PdfDocument(pdfs[name])
    try:
        image = pdf[0].render(scale=2).to_pil()  # 2x of 72 dpi: 1190 x 1684 px for A4
        image.save(GOLDEN / f"second-appeal-{name}-page1.png")
    finally:
        pdf.close()
    assert (GOLDEN / f"second-appeal-{name}-page1.png").stat().st_size > 10_000
