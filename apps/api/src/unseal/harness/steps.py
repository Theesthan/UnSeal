"""Harness language steps (CLAUDE.md "Harness pipeline").

Each step is a versioned prompt (`src/unseal/prompts/<step>.md`) plus a Pydantic output schema
(`llm/schemas.py`). This module is the one place that renders a prompt (language name and
glossary) and calls the model, so the app and the language eval send exactly the same request.
"""

from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

from unseal.llm.client import ReasoningEffort, StructuredResult
from unseal.llm.glossary import Language, glossary_block
from unseal.llm.prompts import load_prompt
from unseal.llm.schemas import STEP_SCHEMAS, AppealFacts, Compose, Intake, Rewrite, StepOutput
from unseal.privacy.redact import redact

Step = Literal["rewrite", "intake", "compose", "appeal_facts"]

LANGUAGE_NAMES: dict[Language, str] = {"en": "English", "ta": "Tamil", "hi": "Hindi"}
MAX_OUTPUT_TOKENS = 4096  # Indic scripts cost more tokens per word than English

T = TypeVar("T", bound=BaseModel)


class StructuredLLM(Protocol):
    async def structured_call(
        self,
        output: type[T],
        *,
        instructions: str,
        input: str,
        max_output_tokens: int,
        reasoning_effort: ReasoningEffort | None,
    ) -> StructuredResult[T]: ...


async def run_step(
    llm: StructuredLLM, step: Step, *, language: Language, input: str
) -> StructuredResult[StepOutput]:
    """One model call for `step`, with the step's prompt, schema and settings. Phone numbers,
    emails and ID numbers in `input` are masked first: they never reach the model."""
    prompt = load_prompt(step)
    instructions = prompt.render(
        language=LANGUAGE_NAMES[language], glossary=glossary_block(language)
    )
    return await llm.structured_call(
        STEP_SCHEMAS[step],
        instructions=instructions,
        input=redact(input),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        reasoning_effort="none" if step == "intake" else None,  # short extraction
    )


async def _typed[M: BaseModel](
    llm: StructuredLLM, step: Step, output: type[M], *, language: Language, input: str
) -> M:
    value = (await run_step(llm, step, language=language, input=input)).value
    if not isinstance(value, output):
        raise TypeError(f"{step} returned {type(value).__name__}, expected {output.__name__}")
    return value


async def rewrite(llm: StructuredLLM, question: str, *, language: Language) -> Rewrite:
    return await _typed(llm, "rewrite", Rewrite, language=language, input=question)


async def intake(llm: StructuredLLM, message: str, *, language: Language) -> Intake:
    return await _typed(llm, "intake", Intake, language=language, input=message)


async def compose(llm: StructuredLLM, records: str, *, language: Language) -> Compose:
    return await _typed(llm, "compose", Compose, language=language, input=records)


async def appeal_facts(llm: StructuredLLM, facts: str, *, language: Language) -> AppealFacts:
    return await _typed(llm, "appeal_facts", AppealFacts, language=language, input=facts)
