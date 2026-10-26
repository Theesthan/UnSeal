"""Opt-in: one real BharatCode call (`uv run pytest -m live tests/live`).

Needs BHARATCODE_API_KEY in the repo-root .env. Confirms base URL, model name and strict structured
output before the Tamil and Hindi eval spends its timebox."""

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from unseal.config import Settings
from unseal.llm.client import build_client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


class RecordsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rewritten: str
    records: list[str]


async def test_smoke_structured_rewrite() -> None:
    try:
        settings = Settings()
    except ValidationError:
        pytest.skip("BHARATCODE_API_KEY is not set")
    result = await build_client(settings).structured(
        RecordsRequest,
        instructions=(
            "Rewrite the citizen's question as a request for specific records a public authority "
            "holds (certified copies, file notings, dates). Never ask for reasons or opinions."
        ),
        input="Why was my semester mathematics mark so low?",
        max_output_tokens=1024,
        reasoning_effort="none",
    )
    assert result.rewritten.strip()
    assert result.records
