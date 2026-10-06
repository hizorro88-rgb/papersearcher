"""전체 파이프라인: fetch → merge → classify → enrich → save → render."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone

from . import config, render, store
from .classify import classify
from .enrich import Enricher
from .merge import apply_overrides, merge
from .sources.clinicaltrials import ClinicalTrialsSource
from .sources.europepmc import EuropePMCSource
from .sources.pubmed import PubMedSource

log = logging.getLogger("collector")


def build_sources(cfg: dict):
    table = {"pubmed": PubMedSource, "clinicaltrials": ClinicalTrialsSource, "europepmc": EuropePMCSource}
    out = []
    for key, cls in table.items():
        scfg = cfg.get(key) or {}
        if scfg.get("enabled", True):
            out.append((key, cls(scfg)))
    return out


def collect(today: date, *, since: date | None = None, no_llm: bool = False, dry_run: bool = False,
            max_llm: int | None = None) -> dict:
    cfg = config.sources()
    existing = store.load_all()
    bootstrap = len(existing) == 0
    state = store.load_state()
    log.info("기존 레코드 %d건, bootstrap=%s", len(existing), bootstrap)

    incoming = []
    source_status = {}
    for key, src in build_sources(cfg):
        s = since or (today - timedelta(days=int(cfg[key].get("lookback_days", 3))))
        res = src.run(s, today, bootstrap=bootstrap)
        source_status[key] = {"ok": res.error is None, "count": len(res.items), "error": res.error,
                              "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        incoming.extend(res.items)

    # 1차 분류 → 관련도 하한 미만은 버린다
    floor = float(cfg.get("relevance_floor", 0.25))
    kept = []
    for it in incoming:
        classify(it, today)
        if it.relevance >= floor:
            kept.append(it)
    log.info("수집 %d건 중 관련도 필터 통과 %d건", len(incoming), len(kept))

    mr = merge(existing, kept, today.isoformat())
    for it in mr.new + mr.updated:
        classify(it, today)
    log.info("신규 %d, 갱신 %d, 변화 없음 %d", len(mr.new), len(mr.updated), mr.unchanged)

    # LLM 요약: 신규 + 요약이 아직 없는 기존 항목 (중요도 순, 상한 적용)
    pending = [it for it in existing.values() if it.summary_source in ("pending", "excerpt")
               and it.review.status != "hidden"]
    pending.sort(key=lambda x: (-x.importance, x.published_at or ""))
    limit = max_llm if max_llm is not None else int(cfg.get("llm", {}).get("max_items_per_run", 120))
    todo = pending[:limit]
    llm_stats = None
    if todo and not no_llm:
        enricher = Enricher(cfg.get("llm", {}))
        llm_stats = enricher.enrich(todo)
        for it in todo:
            classify_after_llm(it, today)
    elif todo:
        from .enrich import apply_fallback
        for it in todo:
            if it.summary_source == "pending":
                apply_fallback(it)

    apply_overrides(existing, store.load_overrides())

    if not dry_run:
        for it in existing.values():
            store.save(it)
        state["sources"] = source_status
        state["runs"].append({
            "date": today.isoformat(), "new": len(mr.new), "updated": len(mr.updated),
            "total": len(existing), "llm": llm_stats.__dict__ if llm_stats else None,
        })
        store.save_state(state)
        render.render_all(existing, state, today)
    return {"new": len(mr.new), "updated": len(mr.updated), "total": len(existing),
            "sources": source_status, "llm": llm_stats.__dict__ if llm_stats else None}


def classify_after_llm(it, today):
    # LLM이 카테고리/근거를 바꿨을 수 있으므로 중요도만 다시 계산
    from .classify import importance
    it.importance = importance(it, today)


def main(argv=None):
    p = argparse.ArgumentParser(description="췌장암 정보 수집기")
    p.add_argument("--date", help="기준일 YYYY-MM-DD (기본: 오늘)")
    p.add_argument("--since", help="재수집 시작일 YYYY-MM-DD")
    p.add_argument("--no-llm", action="store_true", help="LLM 요약 건너뛰기")
    p.add_argument("--max-llm", type=int, help="이번 실행의 LLM 요약 상한")
    p.add_argument("--dry-run", action="store_true", help="저장·렌더 없이 수집만")
    p.add_argument("--render-only", action="store_true", help="수집 없이 페이지만 재생성")
    p.add_argument("--reclassify", action="store_true", help="수집 없이 기존 레코드 전체를 규칙으로 재분류하고 페이지 재생성")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    today = date.fromisoformat(a.date) if a.date else date.today()
    if a.render_only:
        render.render_all(store.load_all(), store.load_state(), today)
        return 0
    if a.reclassify:
        items = store.load_all()
        for it in items.values():
            classify(it, today)
        apply_overrides(items, store.load_overrides())
        for it in items.values():
            store.save(it)
        render.render_all(items, store.load_state(), today)
        return 0
    since = date.fromisoformat(a.since) if a.since else None
    result = collect(today, since=since, no_llm=a.no_llm, dry_run=a.dry_run, max_llm=a.max_llm)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
