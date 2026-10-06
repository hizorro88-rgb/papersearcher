"""새 수집 결과를 기존 레코드와 병합하고 변경 이력을 남긴다."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import HistoryEvent, Item

STATUS_KO = {
    "NOT_YET_RECRUITING": "모집 예정", "RECRUITING": "모집 중", "ENROLLING_BY_INVITATION": "초대 모집",
    "ACTIVE_NOT_RECRUITING": "진행 중(모집 종료)", "COMPLETED": "완료", "SUSPENDED": "일시 중단",
    "TERMINATED": "조기 종료", "WITHDRAWN": "철회", "UNKNOWN": "상태 미확인",
}


@dataclass
class MergeResult:
    new: list[Item] = field(default_factory=list)
    updated: list[Item] = field(default_factory=list)   # 의미 있는 변경 (history 이벤트 발생)
    unchanged: int = 0


def merge_one(old: Item, new: Item, today: str) -> tuple[Item, bool]:
    """old를 기준으로 new의 소스 필드를 반영. 사람이 쓴 요약·검수 상태는 보존."""
    changed = False
    events: list[HistoryEvent] = []

    if new.abstract and new.abstract != old.abstract:
        old.abstract = new.abstract
        changed = True
    if new.title and new.title != old.title:
        old.title = new.title
        changed = True
    if new.published_at and not old.published_at:
        old.published_at = new.published_at
        changed = True
    for k in ("doi", "pmid", "pmcid"):
        if getattr(new.links, k) and not getattr(old.links, k):
            setattr(old.links, k, getattr(new.links, k))
            changed = True
    if set(new.links.nct) - set(old.links.nct):
        old.links.nct = sorted(set(old.links.nct) | set(new.links.nct))
        changed = True
    if new.pub_types and new.pub_types != old.pub_types:
        old.pub_types = new.pub_types
        changed = True
    if old.type == "preprint" and new.type == "paper":
        old.type = "paper"
        events.append(HistoryEvent(date=today, event="preprint_published", detail="프리프린트가 정식 출판됨"))

    if new.trial:
        if not old.trial:
            old.trial = new.trial
            changed = True
        else:
            ot, nt = old.trial, new.trial
            if nt.status and nt.status != ot.status:
                events.append(HistoryEvent(
                    date=today, event="trial_status_changed",
                    detail=f"{STATUS_KO.get(ot.status, ot.status)} → {STATUS_KO.get(nt.status, nt.status)}"))
            if nt.has_results and not ot.has_results:
                events.append(HistoryEvent(date=today, event="results_posted", detail="ClinicalTrials.gov에 결과 게시"))
            if nt.phase and nt.phase != ot.phase:
                events.append(HistoryEvent(date=today, event="phase_changed", detail=f"{ot.phase} → {nt.phase}"))
            if len(nt.locations_kr) and not len(ot.locations_kr):
                events.append(HistoryEvent(date=today, event="kr_site_added", detail="국내 실시기관 추가"))
            # 선정기준이 바뀌면 한국어 조건 요약을 다시 만든다
            if nt.eligibility_text and nt.eligibility_text != ot.eligibility_text:
                nt.eligibility_ko = None
                old.summary_source = "pending"
                events.append(HistoryEvent(date=today, event="eligibility_changed", detail="참여 조건 변경"))
            else:
                nt.eligibility_ko = ot.eligibility_ko
            if nt.model_dump() != ot.model_dump():
                changed = True
            old.trial = nt

    if events:
        old.history.extend(events)
        changed = True
    if changed:
        old.last_updated = today
    return old, bool(events)


def merge(existing: dict[str, Item], incoming: list[Item], today: str) -> MergeResult:
    res = MergeResult()
    seen: set[str] = set()
    for it in incoming:
        if it.id in seen:
            continue
        seen.add(it.id)
        if it.id in existing:
            merged, significant = merge_one(existing[it.id], it, today)
            existing[it.id] = merged
            if significant:
                res.updated.append(merged)
            else:
                res.unchanged += 1
        else:
            it.history.append(HistoryEvent(date=today, event="created"))
            existing[it.id] = it
            res.new.append(it)
    return res


def apply_overrides(items: dict[str, Item], overrides: dict[str, dict]) -> None:
    """data/overrides/*.json 의 값은 항상 우선한다."""
    for iid, ov in overrides.items():
        it = items.get(iid)
        if not it:
            continue
        for k in ("categories", "tags", "evidence", "title_ko", "summary_ko", "entities"):
            if k in ov:
                setattr(it, k, ov[k])
                if k == "summary_ko":
                    it.summary_source = "manual"
        if "review" in ov:
            it.review = it.review.model_copy(update=ov["review"])
