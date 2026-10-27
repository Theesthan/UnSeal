"""Harness steps: one place renders the prompt, picks the schema and calls the model."""

from typing import Any

import pytest
from pydantic import BaseModel

from unseal.harness.steps import appeal_facts, compose, intake, rewrite, run_step
from unseal.llm.client import StructuredResult
from unseal.llm.glossary import glossary_block, load_glossary
from unseal.llm.prompts import load_prompt
from unseal.llm.schemas import AppealFacts, Compose, Intake, Rewrite

pytestmark = pytest.mark.anyio

REWRITE = Rewrite(
    rewritten="Certified copy of the evaluated answer script <REG_NO>",
    records_requested=["answer script"],
    reason="Records instead of reasons",
    personal_information=False,
    suggestion=None,
)
INTAKE = Intake(
    jurisdiction_hint="central",
    authority="CBSE",
    time_period="2026",
    records_wanted=["answer book"],
    delivery_mode="post",
    bpl="unknown",
    follow_up_questions=[],
    ready_to_draft=True,
)
COMPOSE = Compose(
    subject="Copy of the answer book", questions=["Certified copy of the answer book"]
)
APPEAL = AppealFacts(facts_paragraph="Filed on 2026-08-03; no reply by 2026-10-20.")


class FakeLLM:
    def __init__(self, value: BaseModel) -> None:
        self.value = value
        self.calls: list[dict[str, Any]] = []

    async def structured_call(self, output: type[Any], **kwargs: Any) -> StructuredResult[Any]:
        self.calls.append({"output": output, **kwargs})
        return StructuredResult(self.value, "req-1", 0, False)


async def test_run_step_renders_the_prompt_with_language_and_glossary() -> None:
    llm = FakeLLM(REWRITE)
    result = await run_step(llm, "rewrite", language="ta", input="ஏன்?")
    call = llm.calls[0]
    assert call["output"] is Rewrite
    assert call["input"] == "ஏன்?"
    expected = load_prompt("rewrite").render(language="Tamil", glossary=glossary_block("ta"))
    assert call["instructions"] == expected
    assert call["reasoning_effort"] is None
    assert result.value == REWRITE and result.request_id == "req-1"


async def test_intake_runs_without_reasoning() -> None:
    llm = FakeLLM(INTAKE)
    assert await intake(llm, "My CBSE marks", language="en") == INTAKE
    assert llm.calls[0]["reasoning_effort"] == "none"
    assert "English" in llm.calls[0]["instructions"]


async def test_typed_wrappers_return_their_models() -> None:
    assert await rewrite(FakeLLM(REWRITE), "Why?", language="hi") == REWRITE
    assert await compose(FakeLLM(COMPOSE), "records", language="hi") == COMPOSE
    assert await appeal_facts(FakeLLM(APPEAL), "facts", language="ta") == APPEAL


async def test_a_wrapper_rejects_a_mismatched_model() -> None:
    with pytest.raises(TypeError):
        await rewrite(FakeLLM(COMPOSE), "Why?", language="en")


def test_english_glossary_lists_the_concepts_themselves() -> None:
    english = glossary_block("en")
    assert "- certified copy: certified copy" in english
    assert len(english.splitlines()) == len(load_glossary())
