"""Versioned prompt files, one per harness step: src/unseal/prompts/<step>.md.

Each file starts with front matter `---\\nversion: N\\n---`. Changing a prompt means bumping N and
passing the live golden eval before merge (CLAUDE.md). `{language}` is the only placeholder.
"""

import re
from dataclasses import dataclass
from importlib.resources import files

_DIR = files("unseal") / "prompts"
_FRONT_MATTER = re.compile(r"\A---\s*\nversion:\s*(\d+)\s*\n---\s*\n")
_NAME = re.compile(r"[a-z_]+")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    template: str

    def render(self, *, language: str) -> str:
        return self.template.replace("{language}", language)


def load_prompt(name: str) -> Prompt:
    path = _DIR / f"{name}.md"
    if not _NAME.fullmatch(name) or not path.is_file():
        raise FileNotFoundError(f"no prompt named {name!r}")
    text = path.read_text("utf-8").replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise ValueError(f"prompt {name!r} has no 'version: N' front matter")
    return Prompt(name=name, version=int(match.group(1)), template=text[match.end() :].strip())
