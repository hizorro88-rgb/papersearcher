import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    """config/ 는 실제 것을 쓰고 data/, docs/ 는 임시 디렉터리로 돌린다."""
    (tmp_path / "config").symlink_to(ROOT / "config")
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    from collector import config
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(config, "GENERATED_DIR", tmp_path / "docs" / "_generated")
    return tmp_path
