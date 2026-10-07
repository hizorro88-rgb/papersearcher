"""수집 결과를 Slack Incoming Webhook으로 보낸다.

SLACK_WEBHOOK_URL 환경변수가 없으면 아무것도 하지 않는다.
사용법:
  python -m collector.notify                 # 마지막 실행 결과 + 오늘의 새 소식
  python -m collector.notify --failure URL   # 워크플로 실패 알림
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date

import httpx

from . import store
from .merge import STATUS_KO
from .models import Item
from .render import EVIDENCE_NAME, SITE_URL, cat_name, item_anchor, short

log = logging.getLogger(__name__)
MAX_ITEMS = 10


def daily_url(d: str) -> str:
    return f"{SITE_URL}/_generated/daily/{d[:4]}/{d[5:7]}/{d[8:10]}/"


def item_line(it: Item) -> str:
    title = short(it.display_title, 90).replace("<", "〈").replace(">", "〉").replace("&", "＆")
    badge = EVIDENCE_NAME.get(it.evidence, it.evidence)
    cats = "·".join(cat_name(c) for c in it.categories[:2])
    extra = ""
    if it.trial:
        kr = f" 🇰🇷국내 {len(it.trial.locations_kr)}곳" if it.trial.locations_kr else ""
        extra = f" ({STATUS_KO.get(it.trial.status, it.trial.status)}{kr})"
    ko = "" if it.summary_source == "llm" else " _(요약 대기)_"
    return f"• <{it.source.url}|{title}> — {badge} · {cats}{extra}{ko}"


def build_message(items: dict[str, Item], state: dict, today: date) -> dict:
    d = today.isoformat()
    run = (state.get("runs") or [{}])[-1]
    llm = run.get("llm") or {}
    new = [i for i in items.values() if i.review.status != "hidden"
           and any(h.event == "created" and h.date == d for h in i.history)]
    updated = [i for i in items.values() if i.review.status != "hidden"
               and any(h.event != "created" and h.date == d for h in i.history)]
    new.sort(key=lambda i: -i.importance)
    updated.sort(key=lambda i: -i.importance)
    failed_sources = [k for k, v in (state.get("sources") or {}).items() if not v.get("ok")]

    head = (f"*췌장암 정보 위키 · {d} 수집 완료*\n"
            f"신규 {len(new)}건 · 갱신 {len(updated)}건 · 누적 {run.get('total', len(items))}건"
            f" · 한국어 요약 {llm.get('succeeded', 0)}건 성공/{llm.get('failed', 0)}건 실패"
            + (f" ({llm.get('model')})" if llm.get("model") else ""))
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": head}}]
    if failed_sources:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": f"⚠️ 소스 실패: {', '.join(failed_sources)} (<{SITE_URL}/_generated/status/|수집 현황>)"}})
    if new:
        lines = [item_line(i) for i in new[:MAX_ITEMS]]
        more = f"\n…외 {len(new) - MAX_ITEMS}건" if len(new) > MAX_ITEMS else ""
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*새로운 소식*\n" + "\n".join(lines) + more}})
    if updated:
        lines = []
        for i in updated[:5]:
            ev = [h for h in i.history if h.event != "created" and h.date == d][-1]
            lines.append(item_line(i) + f" — {ev.detail or ev.event}")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*기존 정보 업데이트*\n" + "\n".join(lines)}})
    if not new and not updated:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "오늘은 새 소식이 없습니다."}})
    pending = sum(1 for i in items.values() if i.summary_source in ("pending", "excerpt"))
    foot = f"<{daily_url(d)}|오늘의 다이제스트> · <{SITE_URL}/_generated/trials/|임상시험> · <{SITE_URL}/_generated/status/|수집 현황>"
    if pending:
        foot += f" · 요약 대기 {pending}건"
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": foot}]})
    return {"text": head.replace("*", ""), "blocks": blocks}


def build_failure(run_url: str, today: date) -> dict:
    text = f"❌ 췌장암 정보 위키 · {today.isoformat()} 수집 실패\n<{run_url}|Actions 실행 로그 보기>"
    return {"text": text, "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]}


def post(payload: dict) -> bool:
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        log.info("SLACK_WEBHOOK_URL 없음: 알림 생략")
        return False
    r = httpx.post(url, json=payload, timeout=30)
    if r.status_code != 200:
        log.error("Slack 전송 실패 %s: %s", r.status_code, r.text[:200])
        return False
    return True


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date")
    p.add_argument("--failure", metavar="RUN_URL", help="실패 알림을 보낸다")
    p.add_argument("--dry-run", action="store_true", help="보내지 않고 JSON 출력")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    today = date.fromisoformat(a.date) if a.date else date.today()
    payload = build_failure(a.failure, today) if a.failure else build_message(store.load_all(), store.load_state(), today)
    if a.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0
    return 0 if post(payload) or not os.environ.get("SLACK_WEBHOOK_URL") else 1


if __name__ == "__main__":
    sys.exit(main())
