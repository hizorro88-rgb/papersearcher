"""data/ 디렉터리 읽기·쓰기. Git이 데이터베이스다."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import config
from .models import Item


def item_path(item: Item) -> Path:
    d = item.first_seen or date.today().isoformat()
    return config.DATA_DIR / "items" / d[:4] / d[5:7] / f"{item.safe_id}.json"


def load_all() -> dict[str, Item]:
    items: dict[str, Item] = {}
    base = config.DATA_DIR / "items"
    if not base.exists():
        return items
    for p in sorted(base.rglob("*.json")):
        with open(p, encoding="utf-8") as f:
            it = Item.model_validate(json.load(f))
        items[it.id] = it
    return items


def save(item: Item) -> Path:
    p = item_path(item)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(item.model_dump(mode="json"), f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    return p


def load_overrides() -> dict[str, dict]:
    base = config.DATA_DIR / "overrides"
    out = {}
    if base.exists():
        for p in base.glob("*.json"):
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if "id" in d:
                out[d["id"]] = d
    return out


def load_state() -> dict:
    p = config.DATA_DIR / "state.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"sources": {}, "runs": []}


def save_state(state: dict) -> None:
    p = config.DATA_DIR / "state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    state["runs"] = state.get("runs", [])[-60:]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
