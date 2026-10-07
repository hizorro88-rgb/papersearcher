"""data/ → docs/_generated/*.md, feed.xml, data/index.json.

생성물은 멱등이어야 한다 (같은 데이터 → 같은 파일). 사람이 쓰는 docs/ 영역은 건드리지 않는다.
"""
from __future__ import annotations

import html
import json
import shutil
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from . import config
from .merge import STATUS_KO
from .models import Item

SITE_URL = "https://hizorro88-rgb.github.io/papersearcher"

EVIDENCE_NAME = {
    "guideline": "가이드라인", "meta": "메타분석", "phase3": "3상", "phase2": "2상", "phase1": "1상",
    "rct": "무작위", "observational": "관찰연구", "review": "종설", "case": "증례",
    "preclinical": "전임상", "press": "보도자료", "other": "기타",
}
TYPE_NAME = {"paper": "논문", "preprint": "프리프린트", "trial": "임상시험", "regulatory": "규제",
             "press": "보도자료", "news": "뉴스", "guideline": "가이드라인"}
PHASE_KO = {"EARLY_PHASE1": "초기 1상", "PHASE1": "1상", "PHASE2": "2상", "PHASE3": "3상", "PHASE4": "4상", "NA": "해당 없음"}
HISTORY_KO = {"created": "수집", "trial_status_changed": "상태 변경", "results_posted": "결과 게시",
              "preprint_published": "정식 출판", "phase_changed": "단계 변경", "kr_site_added": "국내 기관 추가",
              "eligibility_changed": "참여 조건 변경"}


def cat_name(key: str) -> str:
    return config.taxonomy()["categories"].get(key, {}).get("name", key)


def phase_ko(p: str | None) -> str:
    if not p:
        return "-"
    return "/".join(PHASE_KO.get(x, x) for x in p.split("/"))


def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def short(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def rel(path: str, depth: int) -> str:
    """_generated/ 아래 depth 단계에서 docs 루트 기준 경로로 가는 상대 링크."""
    return "../" * depth + path


def item_anchor(it: Item) -> str:
    return it.safe_id.replace("_", "-").lower()


def trial_page_rel(it: Item, depth: int) -> str:
    return rel(f"_generated/trials/{it.trial.nct_id}.md", depth)


def render_item(it: Item, depth: int, *, show_history: bool = False) -> str:
    """다이제스트·카테고리 페이지용 항목 블록."""
    lines = []
    title = md_escape(it.display_title)
    lines.append(f'<a id="{item_anchor(it)}"></a>')
    lines.append(f"#### [{title}]({it.source.url})")
    if it.title_ko:
        lines.append(f"<small>{html.escape(it.title)}</small>")
        lines.append("")
    type_name = TYPE_NAME.get(it.type, it.type)
    meta = [f"`{type_name}`", f"`{EVIDENCE_NAME.get(it.evidence, it.evidence)}`"]
    meta += [f"`{cat_name(c)}`" for c in it.categories if cat_name(c) != type_name]
    meta += [f"`{t}`" for t in it.tags if t == "신경내분비종양"]
    src = it.source.name + (f" · {it.source.journal}" if it.source.journal else "")
    date_s = it.published_at or "날짜 미상"
    lines.append(f"{' '.join(meta)} · {date_s} · {md_escape(src)} · 중요도 {it.importance:.2f}")
    lines.append("")
    if it.trial:
        t = it.trial
        kr = f"국내 {len(t.locations_kr)}곳" if t.locations_kr else "국내 기관 없음"
        lines.append(f"**{t.nct_id}** · {phase_ko(t.phase)} · {STATUS_KO.get(t.status, t.status)} · {kr} · "
                     f"[참여 조건·기관 보기]({trial_page_rel(it, depth)})")
        lines.append("")
    if it.summary_ko:
        lines.append(it.summary_ko)
        lines.append("")
    elif it.summary_source == "pending":
        lines.append("_한국어 요약이 아직 생성되지 않았습니다. 다음 수집(매일 06:00)에서 처리됩니다._")
        lines.append("")
    if it.key_points_ko:
        for k in it.key_points_ko:
            lines.append(f"- {k}")
        lines.append("")
    if show_history:
        ev = [h for h in it.history if h.event != "created"]
        if ev:
            lines.append("변경 이력: " + " / ".join(f"{h.date} {HISTORY_KO.get(h.event, h.event)}" + (f"({h.detail})" if h.detail else "") for h in ev[-3:]))
            lines.append("")
    tag = {"llm": "AI 한국어 요약 · 원문 확인 필요",
           "excerpt": "⏳ 한국어 요약 재시도 예정 (영어 초록 발췌 임시 표시)",
           "manual": "검수된 요약",
           "pending": "⏳ 한국어 요약 대기 중 (다음 수집에서 처리)"}[it.summary_source]
    links = [f"[원문]({it.source.url})"]
    if it.links.doi:
        links.append(f"[DOI](https://doi.org/{it.links.doi})")
    if it.links.pmcid:
        links.append(f"[무료 전문](https://pmc.ncbi.nlm.nih.gov/articles/{it.links.pmcid}/)")
    for n in it.links.nct:
        if not it.trial:
            links.append(f"[{n}](https://clinicaltrials.gov/study/{n})")
    issue = (f"https://github.com/hizorro88-rgb/papersearcher/issues/new?template=correction.yml"
             f"&title={html.escape(it.id)}")
    lines.append(f"<small>{' · '.join(links)} · {tag} · [수정 제안]({issue})</small>")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def header(title: str, desc: str = "", *, comments: bool = True) -> str:
    fm = ["---", f"title: {json.dumps(title, ensure_ascii=False)}"]
    if desc:
        fm.append(f"description: {json.dumps(desc, ensure_ascii=False)}")
    fm.append(f"comments: {'true' if comments else 'false'}")
    fm.append("search:\n  boost: 0.4")   # 자동 생성 페이지는 가이드보다 검색 순위를 낮춘다
    fm.append("---")
    return "\n".join(fm) + "\n\n"


def disclaimer(depth: int) -> str:
    return (f'!!! warning "안내"\n    이 페이지는 자동 수집·AI 요약된 정보입니다. 의료 조언이 아니며, 치료 결정은 반드시 담당 의료진과 상의하세요. '
            f'응급 상황은 [응급 가이드]({rel("guides/emergency/index.md", depth)}) 또는 119.\n\n')


# ---------------------------------------------------------------- 페이지들

def render_daily(items_by_day: dict[str, list[Item]], out: Path) -> list[str]:
    days = sorted(items_by_day, reverse=True)
    for d in days:
        its = items_by_day[d]
        y, m, dd = d[:4], d[5:7], d[8:10]
        p = out / "daily" / y / m / f"{dd}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        thr = float(config.sources().get("importance_threshold", 0.6))
        new = [i for i in its if any(h.event == "created" and h.date == d for h in i.history)]
        upd = [i for i in its if i not in new]
        top = sorted([i for i in new if i.importance >= thr], key=lambda i: -i.importance)
        rest = sorted([i for i in new if i.importance < thr], key=lambda i: -i.importance)
        s = header(f"{d} 수집", f"{d}에 수집·갱신된 췌장암 관련 소식 {len(its)}건")
        s += f"# {d} 일일 다이제스트\n\n"
        s += disclaimer(4)
        s += f"신규 {len(new)}건 · 갱신 {len(upd)}건 · [날짜별 목록](../../index.md)\n\n"
        if top:
            s += "## 주요 소식\n\n" + "".join(render_item(i, 4) for i in top)
        if upd:
            s += "## 기존 정보 업데이트\n\n" + "".join(render_item(i, 4, show_history=True) for i in sorted(upd, key=lambda i: -i.importance))
        if rest:
            s += "## 전체 목록\n\n"
            by_cat: dict[str, list[Item]] = defaultdict(list)
            for i in rest:
                by_cat[i.categories[0] if i.categories else "treatment"].append(i)
            for c in config.taxonomy()["categories"]:
                if by_cat.get(c):
                    s += f"### {cat_name(c)}\n\n" + "".join(render_item(i, 4) for i in by_cat[c])
        p.write_text(s, encoding="utf-8")
    # 날짜 목록
    idx = header("날짜별 보기", "수집일 기준 다이제스트 목록", comments=False) + "# 날짜별 보기\n\n"
    by_month: dict[str, list[str]] = defaultdict(list)
    for d in days:
        by_month[d[:7]].append(d)
    for mth in sorted(by_month, reverse=True):
        idx += f"## {mth}\n\n"
        for d in by_month[mth]:
            n = len(items_by_day[d])
            idx += f"- [{d}]({d[:4]}/{d[5:7]}/{d[8:10]}.md) — {n}건\n"
        idx += "\n"
    (out / "daily" / "index.md").write_text(idx, encoding="utf-8")
    return days


def render_categories(items: list[Item], out: Path, today: date) -> None:
    cats = config.taxonomy()["categories"]
    cutoff = (today - timedelta(days=30)).isoformat()
    (out / "categories").mkdir(parents=True, exist_ok=True)
    for key, meta in cats.items():
        its = [i for i in items if key in i.categories]
        its.sort(key=lambda i: (i.last_updated, i.importance), reverse=True)
        recent = [i for i in its if i.last_updated >= cutoff]
        by_month: dict[str, list[Item]] = defaultdict(list)
        for i in its:
            by_month[i.last_updated[:7]].append(i)
        s = header(meta["name"], meta.get("description", ""))
        s += f"# {meta['name']}\n\n{meta.get('description', '')}\n\n"
        s += disclaimer(2)
        s += f"전체 {len(its)}건 · 최근 30일 {len(recent)}건\n\n"
        if by_month:
            s += "월별 보기: " + " · ".join(f"[{m}]({key}/{m}.md)" for m in sorted(by_month, reverse=True)) + "\n\n"
        s += "## 최근 30일\n\n" + ("".join(render_item(i, 2) for i in recent[:150]) if recent else "최근 30일 항목이 없습니다.\n")
        (out / "categories" / f"{key}.md").write_text(s, encoding="utf-8")
        for m, lst in by_month.items():
            p = out / "categories" / key / f"{m}.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            ms = header(f"{meta['name']} {m}", comments=False) + f"# {meta['name']} — {m}\n\n{disclaimer(3)}"
            ms += "".join(render_item(i, 3) for i in sorted(lst, key=lambda i: -i.importance))
            p.write_text(ms, encoding="utf-8")


def render_trial_page(it: Item) -> str:
    t = it.trial
    s = header(f"{t.nct_id} {short(it.display_title, 60)}", f"{phase_ko(t.phase)} · {STATUS_KO.get(t.status, t.status)}")
    s += f"# {md_escape(it.display_title)}\n\n"
    if it.title_ko:
        s += f"<small>{html.escape(it.title)}</small>\n\n"
    s += disclaimer(2)
    kr = ", ".join(f"{l.facility or ''}({l.city or ''})".strip() for l in t.locations_kr) or "없음"
    rows = [
        ("등록번호", f"[{t.nct_id}](https://clinicaltrials.gov/study/{t.nct_id})"),
        ("상태", STATUS_KO.get(t.status, t.status or "-")),
        ("단계", phase_ko(t.phase)),
        ("시험 약물/중재", ", ".join(t.interventions) or "-"),
        ("대상 질환", ", ".join(t.conditions[:6]) or "-"),
        ("스폰서", t.sponsor or "-"),
        ("연령·성별", f"{t.min_age or '-'} ~ {t.max_age or '제한 없음'} · {t.sex or '-'}"),
        ("목표 인원", str(t.enrollment or "-")),
        ("시작 / 1차 완료 예정", f"{t.start_date or '-'} / {t.primary_completion_date or '-'}"),
        ("국내 실시기관", kr),
        ("실시 국가", f"{len(t.location_countries)}개국, 기관 {t.n_locations}곳" + (f" ({', '.join(t.location_countries[:8])}{'…' if len(t.location_countries) > 8 else ''})" if t.location_countries else "")),
        ("결과 게시", "예" if t.has_results else "아니오"),
        ("최근 갱신", t.last_update_posted or "-"),
    ]
    s += "| 항목 | 내용 |\n|---|---|\n" + "".join(f"| {k} | {md_escape(v)} |\n" for k, v in rows) + "\n"
    if t.contacts:
        s += "## 문의처 (등록된 중앙 연락처)\n\n"
        for c in t.contacts:
            s += f"- {c.name or ''} {c.phone or ''} {c.email or ''}\n".replace("  ", " ")
        s += "\n국내 기관 참여 문의는 해당 병원 임상시험센터 또는 담당 주치의를 통해 하세요. [참여 방법 안내](../../guides/trials/how-to-apply.md)\n\n"
    if it.summary_ko:
        s += "## 시험 개요\n\n" + it.summary_ko + "\n\n"
        for k in it.key_points_ko:
            s += f"- {k}\n"
        s += "\n"
    if t.eligibility_ko:
        s += "## 참여 조건 (AI 정리, 원문 확인 필요)\n\n" + t.eligibility_ko + "\n\n"
    if t.eligibility_text:
        s += '??? note "선정/제외 기준 원문 (영어)"\n\n'
        s += "".join(f"    {line}\n" for line in t.eligibility_text.splitlines()) + "\n"
    if len(it.history) > 1:
        s += "## 변경 이력\n\n" + "".join(
            f"- {h.date} · {HISTORY_KO.get(h.event, h.event)}{' · ' + h.detail if h.detail else ''}\n" for h in it.history) + "\n"
    s += f"<small>출처: [ClinicalTrials.gov]({it.source.url}) · 수집 {it.first_seen} · 갱신 {it.last_updated}</small>\n"
    return s


def render_trials(items: list[Item], out: Path) -> None:
    trials = [i for i in items if i.trial and i.review.status != "hidden"]
    tdir = out / "trials"
    tdir.mkdir(parents=True, exist_ok=True)
    for it in trials:
        (tdir / f"{it.trial.nct_id}.md").write_text(render_trial_page(it), encoding="utf-8")

    def row(it: Item) -> str:
        t = it.trial
        drug = ", ".join(t.interventions)[:60]
        kr = f"{len(t.locations_kr)}곳" if t.locations_kr else "-"
        return (f"| [{md_escape(short(it.display_title, 70))}]({t.nct_id}.md) | {phase_ko(t.phase)} | "
                f"{STATUS_KO.get(t.status, t.status)} | {md_escape(drug)} | {kr} | {t.last_update_posted or '-'} |\n")

    head = "| 시험명 | 단계 | 상태 | 시험 약물 | 국내 기관 | 갱신 |\n|---|---|---|---|---|---|\n"
    recruiting = {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"}
    kr = sorted([i for i in trials if i.trial.locations_kr and i.trial.status in recruiting], key=lambda i: -i.importance)
    world = sorted([i for i in trials if not i.trial.locations_kr and i.trial.status in recruiting], key=lambda i: -i.importance)
    other = sorted([i for i in trials if i.trial.status not in recruiting], key=lambda i: (i.trial.last_update_posted or ""), reverse=True)
    s = header("임상시험", "췌장암 임상시험 목록: 참여 조건, 국내 실시기관, 신청 방법")
    s += "# 임상시험\n\n"
    s += disclaimer(2)
    s += (f"임상시험 참여를 고려한다면 먼저 [참여 방법 안내]({rel('guides/trials/how-to-apply.md', 2)})를 읽어 주세요. "
          "각 시험 페이지에는 AI가 정리한 참여 조건과 원문, 국내 실시기관, 문의처가 있습니다.\n\n")
    s += f"총 {len(trials)}건 · 국내 모집 중 {len(kr)}건 · 해외 모집 중 {len(world)}건\n\n"
    s += f"## 국내에서 모집 중 ({len(kr)})\n\n" + (head + "".join(row(i) for i in kr) if kr else "현재 등록된 국내 모집 시험이 없습니다.\n") + "\n"
    s += f"## 해외에서 모집 중 ({len(world)})\n\n" + (head + "".join(row(i) for i in world[:300]) if world else "없음\n") + "\n"
    s += f"## 모집 종료·진행 중·완료 ({len(other)})\n\n" + (head + "".join(row(i) for i in other[:300]) if other else "없음\n") + "\n"
    (tdir / "index.md").write_text(s, encoding="utf-8")


def render_topics(items: list[Item], out: Path) -> None:
    ents = {e["id"]: e for e in config.entities()}
    tdir = out / "topics"
    tdir.mkdir(parents=True, exist_ok=True)
    idx = header("주제별 보기", "약물·요법·수술법별 모아보기", comments=False) + "# 주제별 보기\n\n| 주제 | 종류 | 항목 수 | 최근 갱신 |\n|---|---|---|---|\n"
    for eid, e in ents.items():
        its = sorted([i for i in items if eid in i.entities], key=lambda i: (i.published_at or "", i.importance), reverse=True)
        kind = {"drug": "약물", "regimen": "요법", "procedure": "시술·수술", "trial": "시험"}.get(e.get("kind"), e.get("kind", ""))
        s = header(e["names"][0], f"{kind} · {e.get('target', '')}")
        s += f"# {e['names'][0]}\n\n"
        s += disclaimer(2)
        s += f"- 종류: {kind}\n- 별칭: {', '.join(e['names'])}\n"
        if e.get("target"):
            s += f"- 표적/기전: {e['target']}\n"
        if e.get("developer"):
            s += f"- 개발사: {e['developer']}\n"
        trials = [i for i in its if i.trial]
        if trials:
            s += f"\n## 관련 임상시험 ({len(trials)})\n\n| 시험 | 단계 | 상태 | 국내 |\n|---|---|---|---|\n"
            for i in trials:
                s += f"| [{md_escape(short(i.display_title, 70))}](../trials/{i.trial.nct_id}.md) | {phase_ko(i.trial.phase)} | {STATUS_KO.get(i.trial.status, i.trial.status)} | {len(i.trial.locations_kr) or '-'} |\n"
        papers = [i for i in its if not i.trial]
        s += f"\n## 타임라인 ({len(papers)})\n\n" + ("".join(render_item(i, 2) for i in papers[:100]) if papers else "아직 수집된 항목이 없습니다.\n")
        (tdir / f"{eid}.md").write_text(s, encoding="utf-8")
        last = its[0].last_updated if its else "-"
        idx += f"| [{e['names'][0]}]({eid}.md) | {kind} | {len(its)} | {last} |\n"
    (tdir / "index.md").write_text(idx, encoding="utf-8")


def render_latest(items: list[Item], days: list[str], out: Path, today: date) -> None:
    """index.md가 snippet으로 포함하는 '오늘의 주요 소식'."""
    thr = float(config.sources().get("importance_threshold", 0.6))
    recent_cut = (today - timedelta(days=7)).isoformat()
    recent = [i for i in items if i.last_updated >= recent_cut and i.review.status != "hidden"]
    # 논문·소식 3건 + 임상시험 2건 (홈은 짧게, 전체는 날짜별 페이지로)
    papers = sorted([i for i in recent if not i.trial], key=lambda i: -i.importance)[:3]
    trials = sorted([i for i in recent if i.trial], key=lambda i: -i.importance)[:2]
    top = sorted(papers + trials, key=lambda i: -i.importance)
    recruiting = {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"}
    kr_n = sum(1 for i in items if i.trial and i.trial.locations_kr and i.trial.status in recruiting)
    s = ""
    if days:
        s += (f"최근 수집일: [{days[0]}](_generated/daily/{days[0][:4]}/{days[0][5:7]}/{days[0][8:10]}.md) · 전체 {len(items)}건 · "
              f"최근 7일 {len(recent)}건 · **국내 모집 중 임상시험 [{kr_n}건](_generated/trials/index.md)**\n\n")
    if top:
        s += "".join(render_item(i, 0) for i in top)
    else:
        s += "아직 수집된 항목이 없습니다. 첫 수집이 끝나면 여기에 표시됩니다.\n"
    (out / "latest.inc").write_text(s, encoding="utf-8")


def render_status(state: dict, items: list[Item], out: Path) -> None:
    s = header("수집 현황", "소스별 상태와 실행 기록", comments=False) + "# 수집 현황\n\n"
    s += "## 소스 상태\n\n| 소스 | 마지막 실행 | 결과 | 건수 |\n|---|---|---|---|\n"
    for k, v in (state.get("sources") or {}).items():
        s += f"| {k} | {v.get('at', '-')} | {'정상' if v.get('ok') else '실패: ' + md_escape(str(v.get('error')))} | {v.get('count', 0)} |\n"
    s += "\n## 최근 실행\n\n| 날짜 | 신규 | 갱신 | 누적 | LLM | 성공/실패 | 토큰(입력/출력) |\n|---|---|---|---|---|---|---|\n"
    for r in reversed((state.get("runs") or [])[-30:]):
        llm = r.get("llm") or {}
        s += (f"| {r['date']} | {r['new']} | {r['updated']} | {r['total']} | {llm.get('model') or '-'} | "
              f"{llm.get('succeeded', '-')}/{llm.get('failed', '-')} | {llm.get('input_tokens', '-')}/{llm.get('output_tokens', '-')} |\n")
    src = defaultdict(int)
    for i in items:
        src[i.summary_source] += 1
    s += f"\n요약 상태: AI {src['llm']} · 발췌 {src['excerpt']} · 수동 {src['manual']} · 대기 {src['pending']}\n"
    (out / "status.md").write_text(s, encoding="utf-8")


def render_feed(items: list[Item], out: Path, today: date) -> None:
    recent = sorted([i for i in items if i.review.status != "hidden"], key=lambda i: (i.last_updated, i.importance), reverse=True)[:50]
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
             "<title>췌장암 정보 위키</title>", f"<link>{SITE_URL}/</link>",
             "<description>췌장암 신약·임상·수술·치료 소식 자동 수집</description>"]
    for i in recent:
        d = i.last_updated
        link = f"{SITE_URL}/_generated/daily/{d[:4]}/{d[5:7]}/{d[8:10]}/#{item_anchor(i)}"
        desc = (i.summary_ko or "") + f" (출처: {i.source.url})"
        parts.append(f"<item><title>{escape(i.display_title)}</title><link>{escape(link)}</link>"
                     f"<guid isPermaLink=\"false\">{escape(i.id)}:{d}</guid><pubDate>{d}</pubDate>"
                     f"<description>{escape(desc)}</description></item>")
    parts.append("</channel></rss>")
    (out / "feed.xml").write_text("\n".join(parts), encoding="utf-8")


def render_index_json(items: list[Item]) -> None:
    rows = [{
        "id": i.id, "t": i.display_title, "d": i.published_at, "u": i.last_updated, "c": i.categories,
        "e": i.evidence, "imp": i.importance, "src": i.source.name, "url": i.source.url,
        "nct": i.trial.nct_id if i.trial else None, "kr": bool(i.trial and i.trial.locations_kr),
    } for i in items if i.review.status != "hidden"]
    rows.sort(key=lambda r: (r["u"] or "", r["imp"]), reverse=True)
    with open(config.DATA_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))


def render_all(items_map: dict[str, Item], state: dict, today: date) -> None:
    out = config.GENERATED_DIR
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    items = [i for i in items_map.values() if i.review.status != "hidden"]
    by_day: dict[str, list[Item]] = defaultdict(list)
    for i in items:
        for h in i.history:
            by_day[h.date].append(i) if i not in by_day[h.date] else None
    days = render_daily(by_day, out)
    render_categories(items, out, today)
    render_trials(items, out)
    render_topics(items, out)
    render_latest(items, days, out, today)
    render_status(state, items, out)
    render_feed(items, out, today)
    render_index_json(items)
