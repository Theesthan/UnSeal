"""`python -m unseal.bot --polling`: the standalone local-development runner."""

from pathlib import Path
from typing import Any

import pytest
from telegram import Update
from telegram.ext import Application
from test_bot_fakes import bot_settings

from unseal.bot.__main__ import main


def test_it_needs_the_polling_flag(tmp_path: Path) -> None:
    assert main([], settings=bot_settings(tmp_path)) == 2


def test_it_refuses_to_run_without_a_token_or_chat_key(tmp_path: Path) -> None:
    assert main(["--polling"], settings=bot_settings(tmp_path, telegram_bot_token=None)) == 1
    assert main(["--polling"], settings=bot_settings(tmp_path, telegram_chat_hash_key=None)) == 1


def test_polling_runs_the_bot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[dict[str, Any]] = []

    def fake_run_polling(self: Application[Any, Any, Any, Any, Any, Any], **kwargs: Any) -> None:
        runs.append({"application": self, **kwargs})

    monkeypatch.setattr(Application, "run_polling", fake_run_polling)
    assert main(["--polling"], settings=bot_settings(tmp_path)) == 0
    [run] = runs
    assert run["allowed_updates"] == Update.ALL_TYPES
    assert run["application"].updater is not None  # polling needs the updater
    assert run["application"].bot_data["services"].settings.telegram_bot_token is not None
