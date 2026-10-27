"""Generated documents on local disk under STORAGE_DIR (FR-5, FR-8).

Keys are server-made (`<uuid4>.pdf`), never user input, and are checked again on every use, so
no stored key can point outside the folder.
"""

import re
import uuid
from collections.abc import Iterable
from pathlib import Path

_KEY = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.pdf")


def path_for(storage_dir: Path, key: str) -> Path:
    if not _KEY.fullmatch(key):
        raise ValueError("not a storage key")
    return storage_dir / key


def save(storage_dir: Path, data: bytes, suffix: str = ".pdf") -> str:
    key = f"{uuid.uuid4()}{suffix}"
    path = path_for(storage_dir, key)
    storage_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def remove_files(storage_dir: Path, keys: Iterable[str]) -> None:
    for key in keys:
        path_for(storage_dir, key).unlink(missing_ok=True)
