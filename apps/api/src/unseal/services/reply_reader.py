"""Reply reader (FR-11): a photo or PDF of the PIO's reply to page images, and the code-side
reading of what the model extracted.

The upload holds personal data (CLAUDE.md): it is read only after the user opts in, re-encoded
so camera metadata (GPS, device) never reaches the model, and never stored. Only the extracted
fields go back to the user, who confirms the reply date before it touches the case.
"""

import io
import warnings
from dataclasses import dataclass
from datetime import date

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from unseal.db.models import Case, CaseStatus
from unseal.harness.steps import StructuredLLM, read_reply
from unseal.llm.schemas import ReplyRead
from unseal.pdf.models import Ground
from unseal.services.cases import WrongStatus, today_ist

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PAGES = 4  # a reply letter is one to three pages; more is likely the wrong file
MAX_SIDE = 2000  # pixels on the long side: legible, and keeps the model input small
MAX_PIXELS = 40_000_000  # refuse decompression bombs before decoding
JPEG_QUALITY = 85

_PDF_MAGIC = b"%PDF-"


# A reply can only exist once the application was filed; an appeal decision is not read here.
_READABLE = {
    CaseStatus.REPLY_DUE.value,
    CaseStatus.DEEMED_REFUSED.value,
    CaseStatus.REPLIED.value,
}


class UnreadableUpload(Exception):
    """Not a PDF or an image we can open."""


class TooManyPages(Exception):
    """More pages than a reply letter has."""


def _jpeg(image: Image.Image) -> bytes:
    """Downscale and re-encode. A fresh RGB image carries no EXIF, ICC or XMP from the upload."""
    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    clean = Image.new("RGB", image.size)
    clean.paste(image)
    buffer = io.BytesIO()
    clean.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _pdf_pages(data: bytes) -> list[bytes]:
    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        raise UnreadableUpload from error
    try:
        if len(document) > MAX_PAGES:
            raise TooManyPages
        pages = []
        for page in document:
            width, height = page.get_size()
            scale = MAX_SIDE / max(width, height)
            pages.append(_jpeg(page.render(scale=scale).to_pil()))
        return pages
    finally:
        document.close()


def page_images(data: bytes) -> list[bytes]:
    """One clean JPEG per page. CPU-bound: call it in a thread from async code."""
    if data.startswith(_PDF_MAGIC):
        return _pdf_pages(data)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)  # checked just below
            image = Image.open(io.BytesIO(data))
        with image:
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise UnreadableUpload
            image.load()
            return [_jpeg(image)]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise UnreadableUpload from error


@dataclass(frozen=True)
class Findings:
    letter_date: date | None  # None: not printed, unreadable or impossible; the user enters it
    reading: ReplyRead
    suggested_grounds: list[Ground]


def findings(reading: ReplyRead, *, filed_on: date, today: date) -> Findings:
    """Check the model's date against the case and map statuses to first-appeal grounds."""
    letter_date = date.fromisoformat(reading.letter_date) if reading.letter_date else None
    if letter_date is not None and not filed_on <= letter_date <= today:
        letter_date = None
    statuses = {item.status for item in reading.items}
    grounds: list[Ground] = []
    if "refused" in statuses:
        grounds.append("refused")
    if "partial" in statuses:
        grounds.append("incomplete")
    if reading.fee_demanded:
        grounds.append("fee_demanded")
    return Findings(letter_date=letter_date, reading=reading, suggested_grounds=grounds)


def ensure_readable(case: Case) -> None:
    if case.status not in _READABLE:
        raise WrongStatus


async def read_case_reply(llm: StructuredLLM, case: Case, data: bytes) -> Findings:
    """The whole FR-11 step for one upload. The caller has the user's consent."""
    ensure_readable(case)
    pages = await run_in_threadpool(page_images, data)
    reading = await read_reply(llm, pages, language=case.language)  # type: ignore[arg-type]
    return findings(reading, filed_on=case.filed_on, today=today_ist())  # type: ignore[arg-type]
