"""규칙 기반 분류: 카테고리, 근거 수준, 엔티티, 관련도, 중요도."""
from __future__ import annotations

import re
from datetime import date
from functools import lru_cache

from . import config
from .models import Item


@lru_cache
def _compiled() -> dict:
    tax = config.taxonomy()
    cats = {k: [re.compile(p, re.I) for p in v["keywords"]] for k, v in tax["categories"].items()}
    evid = [(e["key"], e["weight"], set(e.get("pubtypes", [])),
             [re.compile(p, re.I) for p in e.get("patterns", [])]) for e in tax["evidence"]]
    core = [re.compile(t, re.I) for t in tax["core_terms"]]
    ents = []
    for e in config.entities():
        pat = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(n) for n in e["names"]) + r")(?![A-Za-z0-9])", re.I)
        ents.append((e["id"], pat))
    return {"cats": cats, "evid": evid, "core": core, "ents": ents, "tax": tax}


def categorize(item: Item) -> list[str]:
    c = _compiled()
    title, body = item.title or "", (item.abstract or "")
    if item.trial:
        body += " " + " ".join(item.trial.interventions) + " " + (item.trial.eligibility_text or "")[:1500]
    scores: dict[str, int] = {}
    for cat, pats in c["cats"].items():
        s = 0
        for p in pats:
            if p.search(title):
                s += 2
            if p.search(body):
                s += 1
        scores[cat] = s
    if item.type == "trial":
        scores["trial"] += 3
        if item.trial and any(t in (item.trial.model_dump_json()) for t in ("DRUG", "BIOLOGICAL")):
            scores["drug"] += 1
    chosen = [k for k, s in sorted(scores.items(), key=lambda kv: -kv[1]) if s >= 2]
    if item.type == "trial":  # 임상시험 레코드는 항상 '임상시험'이 첫 카테고리
        chosen = ["trial"] + [c for c in chosen if c != "trial"]
    # basic은 다른 임상 카테고리와 함께 있으면 제거 (기초연구는 전임상 전용)
    if "basic" in chosen and len(chosen) > 1 and item.evidence not in ("preclinical",):
        chosen.remove("basic")
    return chosen[:4] or ["treatment"]


def evidence_level(item: Item) -> str:
    c = _compiled()
    if item.trial:
        ph = (item.trial.phase or "").upper()
        if "PHASE3" in ph or "PHASE4" in ph:
            return "phase3"
        if "PHASE2" in ph:
            return "phase2"
        if "PHASE1" in ph or "EARLY_PHASE1" in ph:
            return "phase1"
        return "other"
    if item.type in ("press", "news", "regulatory"):
        return "press"
    text = f"{item.title}\n{(item.abstract or '')[:600]}"
    pubtypes = set(item.pub_types)
    for key, _w, pts, pats in c["evid"]:
        if pts & pubtypes:
            return key
    for key, _w, _pts, pats in c["evid"]:
        if any(p.search(text) for p in pats):
            return key
    return "other"


def evidence_from_pubtypes(item: Item) -> str | None:
    """PubMed 출판 유형이나 임상시험 단계처럼 확실한 근거에서 나온 수준만 돌려준다 (LLM이 덮어쓰지 않음)."""
    if item.trial:
        return evidence_level(item)
    pubtypes = set(item.pub_types)
    for key, _w, pts, _pats in _compiled()["evid"]:
        if pts & pubtypes:
            return key
    return None


def entities(item: Item) -> list[str]:
    c = _compiled()
    text = f"{item.title} {item.abstract or ''}"
    if item.trial:
        text += " " + " ".join(item.trial.interventions)
    return [eid for eid, pat in c["ents"] if pat.search(text)]


def relevance(item: Item) -> float:
    c = _compiled()
    t = sum(len(p.findall(item.title or "")) for p in c["core"])
    a = sum(len(p.findall(item.abstract or "")) for p in c["core"])
    if item.trial:
        t += sum(1 for cond in item.trial.conditions for p in c["core"] if p.search(cond))
    score = min(1.0, 0.5 * min(t, 2) + 0.1 * min(a, 5))
    # 신경내분비종양(pNET)은 췌장암(선암)과 다른 질환이므로 관련도를 낮추고 태그로 구분
    head = f"{item.title} {' '.join(item.trial.conditions) if item.trial else ''}"
    if re.search(r"neuroendocrine|pNET|NET\b|carcinoid", head, re.I) and not re.search(r"adenocarcinoma|PDAC|ductal", head, re.I):
        score *= 0.6
        if "신경내분비종양" not in item.tags:
            item.tags.append("신경내분비종양")
    return round(score, 2)


def importance(item: Item, today: date) -> float:
    c = _compiled()
    tax = c["tax"]
    w = {e["key"]: e["weight"] for e in tax["evidence"]}.get(item.evidence, 0.45)
    trust = tax["source_trust"].get(item.source.name, tax["source_trust"]["default"])
    if item.source.journal and item.source.journal in tax["journal_trust"]:
        trust = max(trust, tax["journal_trust"][item.source.journal])
    recency = 0.0
    # 임상시험은 등록일이 아니라 최근 갱신일 기준으로 최신성을 본다
    ref_date = (item.trial.last_update_posted if item.trial and item.trial.last_update_posted else item.published_at)
    if ref_date:
        try:
            if len(ref_date) == 7:  # YYYY-MM
                ref_date += "-01"
            days = (today - date.fromisoformat(ref_date[:10])).days
            recency = 1.0 if days <= 7 else 0.5 if days <= 30 else 0.0
        except ValueError:
            pass
    bonus = 0.0
    if item.trial:
        if item.trial.locations_kr:
            bonus += 0.05
        if item.trial.status == "RECRUITING":
            bonus += 0.03
        if any(h.event in ("results_posted", "trial_status_changed") for h in item.history[-3:]):
            bonus += 0.1
    score = 0.45 * w + 0.25 * trust + 0.20 * item.relevance + 0.10 * recency + bonus
    return round(min(1.0, score), 2)


def classify(item: Item, today: date) -> Item:
    item.evidence = evidence_level(item)
    item.categories = categorize(item)
    item.entities = entities(item)
    item.relevance = relevance(item)
    item.importance = importance(item, today)
    return item
