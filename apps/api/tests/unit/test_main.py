"""The ASGI entry point wires the real BharatCode client and the PDF renderer."""

import importlib

import pytest

from unseal.llm.client import LLMClient
from unseal.pdf.render import render_application_pdf


def test_entry_point_builds_the_app_with_real_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    monkeypatch.setenv("BHARATCODE_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./unused-test.db")
    import unseal.main as main

    app = importlib.reload(main).app
    assert isinstance(app.state.llm, LLMClient)
    assert app.state.renderer is render_application_pdf
