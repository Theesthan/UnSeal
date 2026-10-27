"""Opt-in: can the BharatCode model read a reply letter from an image? (FR-11)

`uv run pytest -m live tests/live/test_reply_reader_live.py`. The letter is fictional and drawn
here, so no real reply or personal data is involved."""

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from pydantic import ValidationError

import unseal.pdf
from unseal.config import Settings
from unseal.harness.steps import read_reply
from unseal.llm.client import build_client
from unseal.services.reply_reader import page_images

pytestmark = [pytest.mark.live, pytest.mark.anyio]

LETTER = """EXAMPLE DEPARTMENT, GOVERNMENT OF EXAMPLE STATE
Office of the Public Information Officer

No. RTI/0000/2026                                   Date: 2026-09-01

To: The Applicant

Sub: Reply to your RTI application dated 2026-08-03

1. The attendance register for June 2026 is enclosed (4 pages).
2. The information sought is personal information of a third party and
   is exempt from disclosure under Section 8(1)(j) of the RTI Act, 2005.
3. Only the first page of the inspection report is available; it is enclosed.

Public Information Officer"""


def letter_png() -> bytes:
    fonts = Path(unseal.pdf.__file__).parent / "fonts"
    font = ImageFont.truetype(str(fonts / "NotoSans-Regular.ttf"), 30)
    image = Image.new("RGB", (1400, 1000), "white")
    ImageDraw.Draw(image).multiline_text((60, 60), LETTER, fill="black", font=font, spacing=12)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def test_the_model_reads_a_typed_reply_letter() -> None:
    try:
        settings = Settings()
    except ValidationError:
        pytest.skip("BHARATCODE_API_KEY is not set")
    reading = await read_reply(build_client(settings), page_images(letter_png()), language="en")
    by_number = {item.number: item for item in reading.items}
    assert reading.letter_date == "2026-09-01"
    assert by_number[1].status == "given"
    assert by_number[2].status == "refused" and by_number[2].section_cited is not None
    assert "8(1)(j)" in by_number[2].section_cited
    assert by_number[3].status == "partial"
    assert reading.fee_demanded is False and reading.transferred_to is None
