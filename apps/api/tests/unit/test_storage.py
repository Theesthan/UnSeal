"""Local document storage: server-made keys only, never a path outside the folder."""

from pathlib import Path

import pytest

from unseal.services.storage import path_for, remove_files, save


def test_save_writes_under_a_uuid_key_and_remove_deletes(tmp_path: Path) -> None:
    key = save(tmp_path / "store", b"%PDF-1.7 test")
    assert key.endswith(".pdf") and len(key) == len("00000000-0000-0000-0000-000000000000.pdf")
    assert path_for(tmp_path / "store", key).read_bytes() == b"%PDF-1.7 test"
    remove_files(tmp_path / "store", [key, key])  # removing twice is fine
    assert not path_for(tmp_path / "store", key).exists()


@pytest.mark.parametrize("key", ["../secret.pdf", "a/b.pdf", "..\\x.pdf", "name.pdf", ""])
def test_keys_that_are_not_server_made_are_refused(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError):
        path_for(tmp_path, key)
