"""LLM client against a fake BharatCode: an httpx2 MockTransport behind the real openai SDK, so the
tests see the exact HTTP request the SDK sends and replay canned responses."""

import json
import logging
from typing import Any

import httpx2
import openai
import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from unseal.config import Settings
from unseal.llm.client import (
    MAX_OUTPUT_TOKENS_CAP,
    LLMClient,
    ModelBusy,
    ModelIncomplete,
    ModelOutputInvalid,
    build_client,
    strict_schema,
)

pytestmark = pytest.mark.anyio

BASE_URL = "https://bharatcode.test/api/model/v1"
VALID = json.dumps(
    {"rewritten": "Certified copy of the answer script", "records": ["answer script"], "note": None}
)


class Rewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rewritten: str
    records: list[str]
    note: str | None = None


class FakeBharatCode:
    """Replays queued responses (or raises queued transport errors) and records every request."""

    def __init__(self, *responses: httpx2.Response | Exception) -> None:
        self.queue = list(responses)
        self.requests: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]


def reply(
    text: str = VALID, status: str = "completed", reason: str | None = None
) -> httpx2.Response:
    body = {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": status,
        "model": "qwen-3.8-27b",
        "incomplete_details": {"reason": reason} if reason else None,
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    return httpx2.Response(200, json=body, headers={"x-request-id": "req-ok"})


def truncated(text: str = '{"rewritten": "Cert') -> httpx2.Response:
    return reply(text=text, status="incomplete", reason="max_output_tokens")


def failing(status: int, request_id: str = "req-err") -> httpx2.Response:
    return httpx2.Response(
        status,
        json={"error": {"message": "SECRET-BODY upstream detail"}},
        headers={"x-request-id": request_id},
    )


def make(fake: FakeBharatCode, sleeps: list[float] | None = None) -> LLMClient:
    async def fake_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    settings = Settings(_env_file=None, bharatcode_api_key="test-key", bharatcode_base_url=BASE_URL)
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(fake.handler))
    return build_client(settings, http_client=http_client, sleep=fake_sleep)


async def test_request_is_stateless_and_strict() -> None:
    fake = FakeBharatCode(reply())
    result = await make(fake).structured(Rewrite, instructions="Rewrite.", input="Why?")

    assert result == Rewrite(
        rewritten="Certified copy of the answer script", records=["answer script"]
    )
    (request,) = fake.requests
    assert str(request.url) == f"{BASE_URL}/responses"
    assert request.headers["authorization"] == "Bearer test-key"
    body = fake.bodies[0]
    assert body["store"] is False
    assert "previous_response_id" not in body
    assert body["model"] == "qwen-3.8-27b"
    assert body["instructions"] == "Rewrite."
    assert body["input"] == "Why?"
    assert body["text"] == {
        "format": {
            "type": "json_schema",
            "name": "Rewrite",
            "schema": strict_schema(Rewrite),
            "strict": True,
        }
    }
    assert "reasoning" not in body


async def test_reasoning_effort_is_sent_only_when_asked() -> None:
    fake = FakeBharatCode(reply())
    await make(fake).structured(Rewrite, instructions="x", input="y", reasoning_effort="none")
    assert fake.bodies[0]["reasoning"] == {"effort": "none"}


async def test_invalid_output_retries_once_then_succeeds() -> None:
    fake = FakeBharatCode(reply(text="not json"), reply())
    result = await make(fake).structured(Rewrite, instructions="x", input="y")
    assert result.records == ["answer script"]
    assert len(fake.requests) == 2


async def test_invalid_output_twice_raises_for_the_caller_to_ask_the_user() -> None:
    fake = FakeBharatCode(reply(text="not json"), reply(text='{"rewritten": 1}'))
    with pytest.raises(ModelOutputInvalid) as exc:
        await make(fake).structured(Rewrite, instructions="x", input="y")
    assert len(fake.requests) == 2
    assert exc.value.request_id == "req-ok"


async def test_truncation_retries_once_with_a_higher_budget() -> None:
    fake = FakeBharatCode(truncated(), reply())
    result = await make(fake).structured(
        Rewrite, instructions="x", input="y", max_output_tokens=1000
    )
    assert result.rewritten.startswith("Certified")
    assert [b["max_output_tokens"] for b in fake.bodies] == [1000, 2000]


async def test_truncation_twice_raises_and_keeps_the_partial_text() -> None:
    fake = FakeBharatCode(truncated('{"rewritten": "A'), truncated('{"rewritten": "AB'))
    with pytest.raises(ModelIncomplete) as exc:
        await make(fake).structured(Rewrite, instructions="x", input="y", max_output_tokens=1000)
    assert exc.value.reason == "max_output_tokens"
    assert exc.value.partial_text == '{"rewritten": "AB'
    budgets = [b["max_output_tokens"] for b in fake.bodies]
    assert budgets == [1000, 2000]  # never the same budget twice


async def test_truncation_at_the_cap_is_not_retried() -> None:
    fake = FakeBharatCode(truncated())
    with pytest.raises(ModelIncomplete):
        await make(fake).structured(
            Rewrite, instructions="x", input="y", max_output_tokens=MAX_OUTPUT_TOKENS_CAP
        )
    assert len(fake.requests) == 1


async def test_raised_budget_never_exceeds_the_cap() -> None:
    fake = FakeBharatCode(truncated(), reply())
    start = MAX_OUTPUT_TOKENS_CAP - 1000
    await make(fake).structured(Rewrite, instructions="x", input="y", max_output_tokens=start)
    assert [b["max_output_tokens"] for b in fake.bodies] == [start, MAX_OUTPUT_TOKENS_CAP]


async def test_budget_above_the_cap_is_rejected_before_any_call() -> None:
    fake = FakeBharatCode()
    with pytest.raises(ValueError):
        await make(fake).structured(
            Rewrite, instructions="x", input="y", max_output_tokens=MAX_OUTPUT_TOKENS_CAP + 1
        )
    assert fake.requests == []


async def test_incomplete_for_another_reason_is_not_retried() -> None:
    fake = FakeBharatCode(reply(text="", status="incomplete", reason="content_filter"))
    with pytest.raises(ModelIncomplete) as exc:
        await make(fake).structured(Rewrite, instructions="x", input="y")
    assert exc.value.reason == "content_filter"
    assert len(fake.requests) == 1


async def test_503_backs_off_then_succeeds() -> None:
    sleeps: list[float] = []
    fake = FakeBharatCode(failing(503), failing(503), reply())
    await make(fake, sleeps).structured(Rewrite, instructions="x", input="y")
    assert sleeps == [2, 4]
    assert len(fake.requests) == 3


async def test_503_after_2_4_8_seconds_is_busy() -> None:
    sleeps: list[float] = []
    fake = FakeBharatCode(*(failing(503, "req-busy") for _ in range(4)))
    with pytest.raises(ModelBusy) as exc:
        await make(fake, sleeps).structured(Rewrite, instructions="x", input="y")
    assert sleeps == [2, 4, 8]
    assert len(fake.requests) == 4
    assert exc.value.request_id == "req-busy"


@pytest.mark.parametrize(
    "error", [httpx2.ConnectError("unreachable"), httpx2.ReadTimeout("too slow")]
)
async def test_unreachable_or_timeout_is_busy_without_retry(error: Exception) -> None:
    sleeps: list[float] = []
    fake = FakeBharatCode(error)
    with pytest.raises(ModelBusy):
        await make(fake, sleeps).structured(Rewrite, instructions="x", input="y")
    assert len(fake.requests) == 1  # a retried timeout would leave the user waiting for minutes
    assert sleeps == []


async def test_other_http_errors_are_not_retried() -> None:
    fake = FakeBharatCode(failing(400, "req-bad"))
    with pytest.raises(openai.BadRequestError):
        await make(fake).structured(Rewrite, instructions="x", input="y")
    assert len(fake.requests) == 1


async def test_logs_carry_request_ids_never_bodies(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    busy = FakeBharatCode(*(failing(503, "req-busy") for _ in range(4)))
    with pytest.raises(ModelBusy):
        await make(busy).structured(Rewrite, instructions="x", input="y")
    leaky = FakeBharatCode(reply(text="LEAKY-OUTPUT"), reply(text="LEAKY-OUTPUT"))
    with pytest.raises(ModelOutputInvalid):
        await make(leaky).structured(Rewrite, instructions="x", input="y")
    bad = FakeBharatCode(failing(400, "req-bad"))
    with pytest.raises(openai.BadRequestError):
        await make(bad).structured(Rewrite, instructions="x", input="y")

    assert "req-busy" in caplog.text
    assert "req-ok" in caplog.text
    assert "req-bad" in caplog.text
    assert "SECRET-BODY" not in caplog.text
    assert "LEAKY-OUTPUT" not in caplog.text


class Inner(BaseModel):
    label: str
    default: str | None = None  # a field literally named "default" must survive


class Outer(BaseModel):
    items: list[Inner]
    count: int = 0


def test_strict_schema_closes_every_object_and_requires_every_field() -> None:
    schema = strict_schema(Outer)
    objects = [schema, *schema["$defs"].values()]
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])
    inner = schema["$defs"]["Inner"]["properties"]
    assert "default" in inner  # the field survives...
    assert "default" not in inner["default"]  # ...but no node keeps a `default` keyword
    assert {"type": "null"} in inner["default"]["anyOf"]  # optional stays nullable
    assert "default" not in schema["properties"]["count"]


def test_settings_read_the_key_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHARATCODE_API_KEY", "env-test-key")
    settings = Settings(_env_file=None)
    assert settings.bharatcode_api_key.get_secret_value() == "env-test-key"
    assert settings.bharatcode_model == "qwen-3.8-27b"
    assert "env-test-key" not in repr(settings)


def test_settings_require_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BHARATCODE_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
