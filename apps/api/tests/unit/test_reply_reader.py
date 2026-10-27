"""Reply reader (FR-11): upload to page images, the model call, and the code-side checks."""

import io
from datetime import date
from typing import Any

import pypdfium2 as pdfium
import pytest
from PIL import Image
from pydantic import ValidationError
from unseal.services.reply_reader import (
    MAX_PAGES,
    MAX_SIDE,
    TooManyPages,
    UnreadableUpload,
    findings,
    page_images,
)

from unseal.harness.steps import read_reply
from unseal.llm.client import StructuredResult
from unseal.llm.schemas import ReplyItem, ReplyRead

pytestmark = pytest.mark.anyio

FILED = date(2026, 8, 3)
TODAY = date(2026, 10, 20)


def png(width: int = 3000, height: int = 1500) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_with_gps() -> bytes:
    exif = Image.Exif()
    exif[0x8825] = {2: (13.0, 5.0, 0.0)}  # GPSInfo: a latitude
    exif[0x010F] = "PhoneMaker"  # Make
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def pdf(pages: int) -> bytes:
    document = pdfium.PdfDocument.new()
    for _ in range(pages):
        document.new_page(595, 842)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def reading(**changes: Any) -> ReplyRead:
    base: dict[str, Any] = {
        "letter_date": "2026-09-01",
        "items": [
            {"number": 1, "status": "given", "section_cited": None},
            {"number": 2, "status": "refused", "section_cited": "8(1)(j)"},
            {"number": 3, "status": "partial", "section_cited": None},
        ],
        "fee_demanded": False,
        "transferred_to": None,
    }
    return ReplyRead.model_validate({**base, **changes})


def test_a_photo_is_downscaled_and_reencoded() -> None:
    [page] = page_images(png())
    image = Image.open(io.BytesIO(page))
    assert image.format == "JPEG" and max(image.size) == MAX_SIDE


def test_photo_metadata_never_reaches_the_model() -> None:
    [page] = page_images(jpeg_with_gps())
    image = Image.open(io.BytesIO(page))
    assert not image.getexif() and "exif" not in image.info


def test_a_pdf_becomes_one_image_per_page() -> None:
    pages = page_images(pdf(2))
    assert len(pages) == 2
    assert all(Image.open(io.BytesIO(p)).format == "JPEG" for p in pages)


def test_too_many_pages_is_refused() -> None:
    with pytest.raises(TooManyPages):
        page_images(pdf(MAX_PAGES + 1))


@pytest.mark.parametrize("data", [b"", b"hello", b"%PDF-1.7 broken", b"\x89PNG\r\n\x1a\nbroken"])
def test_anything_else_is_unreadable(data: bytes) -> None:
    with pytest.raises(UnreadableUpload):
        page_images(data)


def test_a_huge_image_is_refused_before_decoding() -> None:
    buffer = io.BytesIO()
    Image.new("1", (12000, 12000)).save(buffer, format="PNG")  # 144 megapixels, tiny file
    with pytest.raises(UnreadableUpload):
        page_images(buffer.getvalue())


class FakeLLM:
    def __init__(self, value: ReplyRead) -> None:
        self.value = value
        self.calls: list[dict[str, Any]] = []

    async def structured_call(self, output: type[Any], **kwargs: Any) -> StructuredResult[Any]:
        self.calls.append({"output": output, **kwargs})
        return StructuredResult(self.value, "req-1", 0, False)


async def test_the_model_gets_every_page_as_an_image_with_the_prompt() -> None:
    llm = FakeLLM(reading())
    pages = page_images(pdf(2))
    result = await read_reply(llm, pages, language="ta")
    call = llm.calls[0]
    [message] = call["input"]
    images = [part for part in message["content"] if part["type"] == "input_image"]
    assert result == reading() and call["output"] is ReplyRead
    assert len(images) == 2 and images[0]["image_url"].startswith("data:image/jpeg;base64,")
    assert "Tamil" in call["instructions"] and "8(1)(j)" not in call["instructions"]


def test_a_bad_letter_date_or_repeated_item_fails_validation() -> None:
    with pytest.raises(ValidationError):
        reading(letter_date="1 September 2026")
    with pytest.raises(ValidationError):
        reading(items=[{"number": 1, "status": "given", "section_cited": None}] * 2)
    with pytest.raises(ValidationError):
        ReplyItem(number=0, status="given", section_cited=None)


def test_findings_suggest_grounds_from_the_statuses() -> None:
    found = findings(reading(fee_demanded=True), filed_on=FILED, today=TODAY)
    assert found.letter_date == date(2026, 9, 1)
    assert found.suggested_grounds == ["refused", "incomplete", "fee_demanded"]


def test_a_fully_answered_reply_suggests_no_ground() -> None:
    items = [{"number": 1, "status": "given", "section_cited": None}]
    assert findings(reading(items=items), filed_on=FILED, today=TODAY).suggested_grounds == []


@pytest.mark.parametrize("letter_date", ["2026-08-02", "2026-10-21", None])
def test_an_impossible_letter_date_is_dropped_for_the_user_to_enter(
    letter_date: str | None,
) -> None:
    found = findings(reading(letter_date=letter_date), filed_on=FILED, today=TODAY)
    assert found.letter_date is None
