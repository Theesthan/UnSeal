"""The ONLY place that calls BharatCode (CLAUDE.md, "BharatCode API rules").

One structured call = one Responses request with store=False and a strict JSON schema built from
the output's Pydantic model. The API is stateless, so callers pass the full input every time.

Failure handling, in this order:
- 503: back off 2 s, 4 s, 8 s, then ModelBusy ("busy, try again").
- Unreachable or timed out: ModelBusy at once, no retry.
- Incomplete because of max_output_tokens: retry once with double the budget (capped at 32,000),
  never the same budget twice; then ModelIncomplete carrying the partial text.
- Output that fails its schema: retry once, then ModelOutputInvalid so the caller asks the user.
Logs carry the x-request-id only, never a request or response body.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx2
import openai
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseInputParam
from openai.types.shared import ReasoningEffort as ReasoningEffort  # re-exported for callers
from pydantic import BaseModel, ValidationError

from unseal.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_OUTPUT_TOKENS_CAP = 32_000  # BharatCode's cap, reasoning tokens included
BUSY_BACKOFF_SECONDS = (2, 4, 8)
REQUEST_TIMEOUT_SECONDS = 120


class LLMError(Exception):
    def __init__(self, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id


class ModelBusy(LLMError):
    """BharatCode stayed at 503 through every backoff: show "busy, try again"."""


class ModelOutputInvalid(LLMError):
    """Output failed its schema twice: fall back to asking the user."""


class ModelIncomplete(LLMError):
    """Output was cut off; `partial_text` is kept for display, never parsed or acted on."""

    def __init__(self, reason: str, partial_text: str, request_id: str | None = None) -> None:
        super().__init__(f"model output incomplete: {reason}", request_id)
        self.reason = reason
        self.partial_text = partial_text


@dataclass(frozen=True)
class StructuredResult[V: BaseModel]:
    """A validated answer plus how it was reached (for evals and metrics)."""

    value: V
    request_id: str | None
    schema_retries: int
    budget_raised: bool


_NAMED_MAPS = ("properties", "$defs")  # keys here are field or model names, not schema keywords


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON schema made strict-mode compatible: every object closed, every field
    required (optional fields stay nullable), defaults dropped. Output models must not use
    free-form dict fields, which strict mode cannot express."""
    result: dict[str, Any] = _strict(model.model_json_schema())
    return result


def _strict(node: Any) -> Any:
    if isinstance(node, list):
        return [_strict(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "default":
            continue
        if key in _NAMED_MAPS:
            out[key] = {name: _strict(sub) for name, sub in value.items()}
        else:
            out[key] = _strict(value)
    if out.get("type") == "object":
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}))
    return out


class LLMClient:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model: str,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._openai = openai_client
        self._model = model
        self._sleep = sleep

    async def structured_call(
        self,
        output: type[T],
        *,
        instructions: str,
        input: str | ResponseInputParam,
        max_output_tokens: int = 2048,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> StructuredResult[T]:
        if not 0 < max_output_tokens <= MAX_OUTPUT_TOKENS_CAP:
            raise ValueError(f"max_output_tokens must be 1..{MAX_OUTPUT_TOKENS_CAP}")
        request: dict[str, Any] = {
            "model": self._model,
            "instructions": instructions,
            "input": input,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": output.__name__,
                    "schema": strict_schema(output),
                    "strict": True,
                }
            },
        }
        if reasoning_effort is not None:
            request["reasoning"] = {"effort": reasoning_effort}

        budget = max_output_tokens
        raised_budget = retried_invalid = False
        while True:
            response = await self._create(request, budget)
            request_id = response._request_id
            if response.status == "incomplete":
                details = response.incomplete_details
                reason = (details.reason if details else None) or "unknown"
                log.warning("bharatcode incomplete reason=%s request_id=%s", reason, request_id)
                if (
                    reason == "max_output_tokens"
                    and not raised_budget
                    and budget < MAX_OUTPUT_TOKENS_CAP
                ):
                    budget = min(budget * 2, MAX_OUTPUT_TOKENS_CAP)
                    raised_budget = True
                    continue
                raise ModelIncomplete(reason, response.output_text, request_id)
            try:
                value = output.model_validate_json(response.output_text)
            except ValidationError as exc:
                log.warning(
                    "bharatcode output failed schema %s (%d errors) request_id=%s",
                    output.__name__,
                    exc.error_count(),
                    request_id,
                )
                if retried_invalid:
                    raise ModelOutputInvalid(
                        f"output failed {output.__name__} twice", request_id
                    ) from None
                retried_invalid = True
                continue
            return StructuredResult(value, request_id, int(retried_invalid), raised_budget)

    async def structured(
        self,
        output: type[T],
        *,
        instructions: str,
        input: str | ResponseInputParam,
        max_output_tokens: int = 2048,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> T:
        result = await self.structured_call(
            output,
            instructions=instructions,
            input=input,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
        )
        return result.value

    async def _create(self, request: dict[str, Any], budget: int) -> Response:
        delays = iter(BUSY_BACKOFF_SECONDS)
        while True:
            try:
                response: Response = await self._openai.responses.create(
                    **request, max_output_tokens=budget
                )
                return response
            except openai.APIConnectionError as exc:  # includes APITimeoutError
                # No retry: a second timeout would keep the user waiting for minutes.
                log.warning("bharatcode unreachable: %s", type(exc).__name__)
                raise ModelBusy("BharatCode is unreachable") from None
            except openai.APIStatusError as exc:
                if exc.status_code != 503:
                    log.warning(
                        "bharatcode error status=%s request_id=%s", exc.status_code, exc.request_id
                    )
                    raise
                delay = next(delays, None)
                if delay is None:
                    log.warning("bharatcode busy, giving up request_id=%s", exc.request_id)
                    raise ModelBusy("BharatCode is busy", exc.request_id) from None
                log.info("bharatcode 503, retrying in %ss request_id=%s", delay, exc.request_id)
                await self._sleep(delay)


def build_client(
    settings: Settings,
    *,
    http_client: httpx2.AsyncClient | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> LLMClient:
    openai_client = AsyncOpenAI(
        api_key=settings.bharatcode_api_key.get_secret_value(),
        base_url=settings.bharatcode_base_url,
        max_retries=0,  # we own retries: the SDK's own backoff would hide 503s from our policy
        timeout=REQUEST_TIMEOUT_SECONDS,
        http_client=http_client,
    )
    return LLMClient(openai_client, settings.bharatcode_model, sleep)
