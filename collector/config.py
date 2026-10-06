"""설정 파일 로딩."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("PAPERSEARCHER_ROOT", Path(__file__).resolve().parent.parent))
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
GENERATED_DIR = DOCS_DIR / "_generated"


def _load(name: str) -> Any:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def sources() -> dict:
    return _load("sources.yaml")


@lru_cache
def taxonomy() -> dict:
    return _load("taxonomy.yaml")


@lru_cache
def entities() -> list[dict]:
    return _load("entities.yaml") or []
