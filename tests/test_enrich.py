import json
from datetime import date

import httpx
import pytest

from collector import enrich
from collector.classify import classify
from collector.enrich import Enricher, GeminiBackend, OUTPUT_SCHEMA, apply_result, gemini_schema, make_backend
from collector.sources.clinicaltrials import parse_study

from .test_sources import CT_STUDY

TODAY = date(2026, 10, 6)

GEMINI_JSON = {
    "title_ko": "RASolute 302: 췌장암에서 daraxonrasib 대 항암화학요법",
    "summary_ko": "전이성 췌장암 환자를 대상으로 daraxonrasib(다락소나십)과 표준 항암화학요법을 비교하는 3상 시험입니다.",
    "key_points_ko": ["목표 인원 460명입니다.", "국내 1개 기관이 참여합니다."],
    "categories": ["trial", "drug", "bogus"],
    "evidence": "phase3",
    "patient_relevance": 5,
    "eligibility_ko": "선정 기준:\n- 전이성 PDAC\n제외 기준:\n- 뇌 전이",
}


def test_gemini_schema_strips_unsupported_keys():
    s = gemini_schema(OUTPUT_SCHEMA)
    assert "additionalProperties" not in s
    assert "maxItems" not in s["properties"]["key_points_ko"]
    assert s["properties"]["evidence"]["enum"]  # enum은 유지
    assert "additionalProperties" in OUTPUT_SCHEMA  # 원본은 변경되지 않음


def test_backend_selection(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert make_backend({"provider": "auto"}) is None
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    b = make_backend({"provider": "auto", "gemini_model": "gemini-3.8-flash"})
    assert isinstance(b, GeminiBackend) and b.model == "gemini-3.8-flash"
    assert make_backend({"provider": "anthropic"}) is None  # 키 없으면 None


def test_gemini_backend_and_apply(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        body = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "test-key"
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert "additionalProperties" not in json.dumps(body["generationConfig"]["responseSchema"])
        if len(calls) == 1:
            return httpx.Response(429, text="quota", headers={"retry-after": "0"})
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(GEMINI_JSON)}]}}],
            "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 250},
        })

    backend = GeminiBackend("gemini-3.8-flash", min_interval=0)
    backend.client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(enrich, "make_backend", lambda cfg: backend)

    trial = classify(parse_study(CT_STUDY, TODAY), TODAY)
    stats = Enricher({"provider": "gemini"}).enrich([trial])
    assert len(calls) == 2  # 429 후 재시도
    assert stats.succeeded == 1 and stats.failed == 0 and stats.provider == "gemini"
    assert stats.input_tokens == 900 and stats.output_tokens == 250
    assert trial.summary_source == "llm"
    assert trial.title_ko.startswith("RASolute")
    assert trial.categories[0] == "trial" and "bogus" not in trial.categories
    assert trial.trial.eligibility_ko.startswith("선정 기준")
    assert trial.importance <= 1.0


def test_gemini_daily_quota_stops_fast(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    n = {"calls": 0}

    def handler(request):
        n["calls"] += 1
        return httpx.Response(429, text='{"error":{"status":"RESOURCE_EXHAUSTED","message":"Quota exceeded for GenerateRequestsPerDayPerProjectPerModel"}}')

    backend = GeminiBackend("gemini-3.8-flash", min_interval=0)
    backend.client = httpx.Client(transport=httpx.MockTransport(handler))
    for _ in range(3):
        with pytest.raises(RuntimeError, match="일일 한도"):
            backend.complete("s", "u", OUTPUT_SCHEMA)
    assert n["calls"] == 1  # 두 번째부터는 호출 없이 즉시 실패


def test_gemini_unknown_model_stops_fast(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    n = {"calls": 0}

    def handler(request):
        n["calls"] += 1
        return httpx.Response(404, text='{"error":{"code":404,"message":"This model models/x is no longer available"}}')

    backend = GeminiBackend("x", min_interval=0)
    backend.client = httpx.Client(transport=httpx.MockTransport(handler))
    for _ in range(2):
        with pytest.raises(RuntimeError, match="모델 사용 불가"):
            backend.complete("s", "u", OUTPUT_SCHEMA)
    assert n["calls"] == 1


def test_apply_result_tolerates_bad_values():
    trial = classify(parse_study(CT_STUDY, TODAY), TODAY)
    apply_result(trial, {"title_ko": "", "summary_ko": "", "key_points_ko": None, "categories": None,
                         "evidence": "nope", "patient_relevance": "x", "eligibility_ko": None})
    assert trial.summary_source == "llm" and trial.summary_ko  # 발췌로 채움
    assert trial.evidence == "phase3"


def test_enrich_without_key_falls_back(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    trial = classify(parse_study(CT_STUDY, TODAY), TODAY)
    stats = Enricher({"provider": "auto"}).enrich([trial])
    assert stats.failed == 1 and trial.summary_source == "excerpt"
