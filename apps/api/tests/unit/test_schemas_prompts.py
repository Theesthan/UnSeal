"""Draft output schemas and the versioned prompt files the harness (and the language eval) use."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from unseal.evals.lang_eval import invented_legal_values
from unseal.llm import prompts
from unseal.llm.client import strict_schema
from unseal.llm.glossary import glossary_block
from unseal.llm.prompts import load_prompt
from unseal.llm.schemas import STEP_SCHEMAS, AppealFacts, Compose, Intake, Rewrite

STEPS = ["rewrite", "intake", "compose", "appeal_facts"]


def test_every_step_has_a_schema() -> None:
    assert {
        "rewrite": Rewrite,
        "intake": Intake,
        "compose": Compose,
        "appeal_facts": AppealFacts,
    } == STEP_SCHEMAS


@pytest.mark.parametrize("step", STEPS)
def test_schemas_are_strict_and_name_their_user_facing_fields(step: str) -> None:
    model = STEP_SCHEMAS[step]
    schema = strict_schema(model)
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(model.model_fields)
    assert model.USER_FACING
    assert set(model.USER_FACING) <= set(model.model_fields)


def test_user_facing_text_joins_fields_and_skips_empty_ones() -> None:
    compose = Compose(subject="Subject", questions=["One", "Two"])
    assert compose.user_text() == "Subject\nOne\nTwo"
    refused = Rewrite(
        rewritten="",
        records_requested=[],
        reason="Reason",
        personal_information=True,
        suggestion=None,
    )
    assert refused.user_text() == "Reason"


@pytest.mark.parametrize("step", STEPS)
def test_prompts_are_v2_and_render_language_and_glossary(step: str) -> None:
    prompt = load_prompt(step)
    assert prompt.name == step
    assert prompt.version == 2
    assert "{language}" in prompt.template and "{glossary}" in prompt.template
    rendered = prompt.render(language="Tamil", glossary=glossary_block("ta"))
    assert "Tamil" in rendered
    assert "சான்றளிக்கப்பட்ட நகல்" in rendered
    assert "{" not in rendered
    assert "version:" not in rendered  # front matter is stripped


@pytest.mark.parametrize("step", STEPS)
@pytest.mark.parametrize("language", ["ta", "hi"])
def test_prompts_carry_no_legal_values(step: str, language: str) -> None:
    # Golden rule 1: section numbers, fees and deadlines come from code, never from a prompt.
    prompt = load_prompt(step)
    assert invented_legal_values(prompt.template, "") == []
    rendered = prompt.render(language="x", glossary=glossary_block(language))
    assert invented_legal_values(rendered, "") == []


def test_unknown_prompt_fails() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("nope")


def test_prompt_without_front_matter_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bare.md").write_text("No version here.", "utf-8")
    monkeypatch.setattr(prompts, "_DIR", tmp_path)
    with pytest.raises(ValueError):
        prompts.load_prompt("bare")


def test_rewrite_must_name_records_unless_it_refuses() -> None:
    with pytest.raises(ValidationError):  # the live v2 TA-1 answer: valid JSON, says nothing
        Rewrite(
            rewritten="",
            records_requested=[],
            reason="",
            personal_information=False,
            suggestion=None,
        )
    with pytest.raises(ValidationError):  # a reason alone is not a rewrite
        Rewrite(
            rewritten="",
            records_requested=[],
            reason="Asked for records instead of reasons",
            personal_information=False,
            suggestion=None,
        )
    with pytest.raises(ValidationError):  # a refusal must not request the person's data
        Rewrite(
            rewritten="Copy of the neighbour's tax return",
            records_requested=["tax return"],
            reason="Personal information",
            personal_information=True,
            suggestion=None,
        )
    Rewrite(
        rewritten="",
        records_requested=[],
        reason="Personal information of another person",
        personal_information=True,
        suggestion="Ask for aggregate figures",
    )


def test_compose_and_appeal_facts_need_content() -> None:
    with pytest.raises(ValidationError):
        Compose(subject="  ", questions=["A question"])
    with pytest.raises(ValidationError):
        Compose(subject="Subject", questions=[])
    with pytest.raises(ValidationError):
        Compose(subject="Subject", questions=["A question", " "])
    with pytest.raises(ValidationError):
        AppealFacts(facts_paragraph="")
