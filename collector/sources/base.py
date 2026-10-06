"""소스 어댑터 공통 인터페이스."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import httpx

from ..models import Item

log = logging.getLogger(__name__)

USER_AGENT = "papersearcher/0.1 (+https://github.com/hizorro88-rgb/papersearcher)"


@dataclass
class SourceResult:
    name: str
    items: list[Item] = field(default_factory=list)
    error: str | None = None


class SourceAdapter:
    name: str = "base"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.client = httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}, follow_redirects=True)

    def fetch(self, since: date, today: date, *, bootstrap: bool = False) -> list[Item]:
        raise NotImplementedError

    def run(self, since: date, today: date, *, bootstrap: bool = False) -> SourceResult:
        try:
            items = self.fetch(since, today, bootstrap=bootstrap)
            log.info("%s: %d건", self.name, len(items))
            return SourceResult(self.name, items)
        except Exception as e:  # 한 소스의 실패가 전체를 멈추지 않게 한다
            log.exception("%s 수집 실패", self.name)
            return SourceResult(self.name, [], error=f"{type(e).__name__}: {e}")
