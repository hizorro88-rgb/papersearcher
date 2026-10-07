import json
from datetime import date

from collector import render, store
from collector.classify import classify
from collector.enrich import apply_fallback, build_user_prompt, excerpt
from collector.merge import apply_overrides, merge
from collector.sources.clinicaltrials import parse_study
from collector.sources.pubmed import parse_efetch_xml

from .test_sources import CT_STUDY, PUBMED_XML

TODAY = date(2026, 10, 6)


def _items():
    paper = parse_efetch_xml(PUBMED_XML, TODAY)[0]
    trial = parse_study(CT_STUDY, TODAY)
    return classify(paper, TODAY), classify(trial, TODAY)


def test_classify_paper():
    paper, trial = _items()
    assert paper.evidence == "phase3"
    assert "drug" in paper.categories and "trial" in paper.categories
    assert "daraxonrasib" in paper.entities
    assert paper.relevance >= 0.5
    assert paper.importance >= 0.6
    assert trial.evidence == "phase3"
    assert trial.categories[0] == "trial"
    assert "daraxonrasib" in trial.entities


def test_merge_tracks_trial_status_change():
    _, trial = _items()
    existing = {}
    r = merge(existing, [trial], "2026-10-05")
    assert len(r.new) == 1 and existing[trial.id].history[0].event == "created"

    changed = parse_study(json.loads(json.dumps(CT_STUDY)), TODAY)
    changed.trial.status = "ACTIVE_NOT_RECRUITING"
    changed.trial.has_results = True
    existing[trial.id].trial.eligibility_ko = "선정 기준: ..."
    r2 = merge(existing, [changed], "2026-10-06")
    assert len(r2.updated) == 1
    events = [h.event for h in existing[trial.id].history]
    assert "trial_status_changed" in events and "results_posted" in events
    assert existing[trial.id].trial.eligibility_ko == "선정 기준: ..."  # 조건 원문이 같으면 한국어 정리 보존
    assert existing[trial.id].last_updated == "2026-10-06"

    r3 = merge(existing, [changed], "2026-10-07")
    assert r3.unchanged == 1 and not r3.updated


def test_overrides_and_fallback():
    paper, _ = _items()
    apply_fallback(paper)
    assert paper.summary_source == "excerpt" and paper.summary_ko.startswith("BACKGROUND")
    apply_overrides({paper.id: paper}, {paper.id: {"id": paper.id, "categories": ["surgery"], "review": {"status": "verified"}}})
    assert paper.categories == ["surgery"] and paper.review.status == "verified"
    assert excerpt("One. Two. Three.") == "One. Two."
    assert "선정/제외 기준 원문" in build_user_prompt(_items()[1])


def test_store_and_render(tmp_root):
    paper, trial = _items()
    existing = {}
    merge(existing, [paper, trial], TODAY.isoformat())
    for it in existing.values():
        apply_fallback(it)
        store.save(it)
    loaded = store.load_all()
    assert set(loaded) == {paper.id, trial.id}
    state = {"sources": {"pubmed": {"ok": True, "count": 1, "at": "x"}}, "runs": [{"date": "2026-10-06", "new": 2, "updated": 0, "total": 2, "llm": None}]}
    render.render_all(loaded, state, TODAY)
    g = tmp_root / "docs" / "_generated"
    assert (g / "daily" / "2026" / "10" / "06.md").exists()
    assert (g / "trials" / "NCT06625320.md").exists()
    assert (g / "categories" / "drug.md").exists()
    assert (g / "topics" / "daraxonrasib.md").exists()
    assert (g / "feed.xml").exists() and (g / "latest.inc").exists() and (g / "status.md").exists()
    trial_md = (g / "trials" / "NCT06625320.md").read_text(encoding="utf-8")
    assert "Seoul National University Hospital" in trial_md and "Brain metastases" in trial_md
    trials_idx = (g / "trials" / "index.md").read_text(encoding="utf-8")
    assert "국내에서 모집 중 (1)" in trials_idx
    index = json.loads((tmp_root / "data" / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 2 and any(r["kr"] for r in index)


def test_slack_message(tmp_root, monkeypatch):
    import httpx
    from collector import notify

    paper, trial = _items()
    existing = {}
    merge(existing, [paper, trial], TODAY.isoformat())
    paper.summary_source = "llm"
    paper.title_ko = "다락소나십 3상 결과"
    state = {"sources": {"pubmed": {"ok": True}, "europepmc": {"ok": False, "error": "x"}},
             "runs": [{"date": TODAY.isoformat(), "new": 2, "updated": 0, "total": 2,
                       "llm": {"succeeded": 1, "failed": 1, "model": "gemini-3.5-flash-lite"}}]}
    payload = notify.build_message(existing, state, TODAY)
    text = json.dumps(payload, ensure_ascii=False)
    assert "신규 2건" in text and "다락소나십 3상 결과" in text and "🇰🇷국내 1곳" in text
    assert "소스 실패: europepmc" in text and "요약 대기" in text

    sent = {}
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: sent.update(url=url, body=json) or httpx.Response(200))
    assert notify.post(payload) is True and sent["url"].startswith("https://hooks.slack.com")
    monkeypatch.delenv("SLACK_WEBHOOK_URL")
    assert notify.post(payload) is False
