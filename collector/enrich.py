"""LLM으로 한국어 제목·요약·핵심 포인트·임상시험 참여 조건을 만든다.

백엔드 두 가지:
- gemini    : Google Gemini API (무료 등급 가능, GEMINI_API_KEY)
- anthropic : Claude API (유료, ANTHROPIC_API_KEY)
`llm.provider` 가 auto면 GEMINI_API_KEY → ANTHROPIC_API_KEY 순으로 있는 것을 쓴다.

원칙: 입력(제목·초록·선정기준)에 없는 사실을 만들지 않는다. 출력은 JSON 스키마로 강제한다.
키가 없거나 호출이 실패하면 초록 발췌로 대체하고 summary_source="excerpt"로 표시한다 (다음 실행에서 재시도).
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import httpx

from .models import CATEGORY_KEYS, EVIDENCE_KEYS, Item

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 췌장암 환자와 보호자를 위한 의학 정보 정리 도우미입니다. 영어 논문 초록, 임상시험 등록 정보를 한국어로 정확하게 옮깁니다.

규칙:
- 제공된 텍스트에 있는 내용만 사용합니다. 없는 수치, 결론, 효과를 추측해서 쓰지 않습니다.
- 초록에 명시되지 않은 것은 "초록에 명시되지 않음"이라고 씁니다.
- 의료 조언(특정 치료를 권하거나 말리는 말)을 하지 않습니다. 사실만 전달합니다.
- 전문 용어는 처음 나올 때 괄호로 영어 원어를 병기합니다. 예: 무진행 생존기간(PFS)
- 약물명은 영어 원어를 유지하고 필요하면 한글 음차를 병기합니다. 예: daraxonrasib(다락소나십)
- 핵심 수치(생존기간, 반응률, 환자 수, 위험비)는 반드시 포함합니다.
- 문체는 "~입니다/~했습니다"의 정중한 평서문, 한 문장은 짧게.

출력 필드:
- title_ko: 제목의 자연스러운 한국어 번역 (한 줄).
- summary_ko: 3~5문장. 무엇을/누구에게/어떤 결과가 나왔는지. 임상시험이면 어떤 치료를 누구에게 시험하는지.
- key_points_ko: 핵심 포인트 2~4개, 각 한 문장. 수치 중심.
- categories: 가장 알맞은 카테고리 1~3개. drug(신약·치료제), trial(임상시험), surgery(수술), treatment(치료 전반), diagnosis(진단·조기발견), supportive(지지요법·삶의질), industry(제약사·규제), basic(기초연구).
- evidence: guideline, meta, phase3, phase2, phase1, rct, observational, review, case, preclinical, press, other 중 하나.
- patient_relevance: 1~5. 지금 치료 중인 환자·보호자에게 얼마나 직접 관련되는지 (5=표준치료를 바꿀 수 있는 3상 결과, 1=전임상 기전 연구).
- eligibility_ko: 임상시험일 때만. 선정 기준과 제외 기준의 핵심을 각각 불릿 3~6개로 정리한 한국어 텍스트 ("선정 기준:" / "제외 기준:" 소제목 사용). 임상시험이 아니면 빈 문자열.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title_ko": {"type": "string"},
        "summary_ko": {"type": "string"},
        "key_points_ko": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "categories": {"type": "array", "items": {"type": "string", "enum": CATEGORY_KEYS}, "maxItems": 3},
        "evidence": {"type": "string", "enum": EVIDENCE_KEYS},
        "patient_relevance": {"type": "integer", "minimum": 1, "maximum": 5},
        "eligibility_ko": {"type": "string"},
    },
    "required": ["title_ko", "summary_ko", "key_points_ko", "categories", "evidence",
                 "patient_relevance", "eligibility_ko"],
    "additionalProperties": False,
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class EnrichStats:
    provider: str = "none"
    model: str = ""
    models_used: dict = field(default_factory=dict)
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    errors: list[str] = field(default_factory=list)


def excerpt(text: str | None, n_sentences: int = 2, limit: int = 500) -> str:
    if not text:
        return ""
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    out = " ".join(sents[:n_sentences])
    return out[:limit] + ("…" if len(out) > limit else "")


def build_user_prompt(item: Item) -> str:
    parts = [f"[유형] {item.type}", f"[제목] {item.title}"]
    if item.source.journal:
        parts.append(f"[저널/스폰서] {item.source.journal}")
    if item.pub_types:
        parts.append(f"[출판 유형] {', '.join(item.pub_types)}")
    if item.trial:
        t = item.trial
        parts.append(f"[임상시험] {t.nct_id} · 단계: {t.phase} · 상태: {t.status} · 중재: {', '.join(t.interventions) or '-'}"
                     f" · 대상 질환: {', '.join(t.conditions[:5])} · 연령: {t.min_age}~{t.max_age} · 성별: {t.sex}"
                     f" · 목표 인원: {t.enrollment} · 국내 기관: {len(t.locations_kr)}곳")
    if item.abstract:
        parts.append(f"[초록/설명]\n{item.abstract[:6000]}")
    if item.trial and item.trial.eligibility_text:
        parts.append(f"[선정/제외 기준 원문]\n{item.trial.eligibility_text[:6000]}")
    return "\n\n".join(parts)


def apply_fallback(item: Item) -> Item:
    item.summary_ko = excerpt(item.abstract) or "원문을 확인하세요."
    item.summary_source = "excerpt"
    return item


# ------------------------------------------------------------------ 백엔드

class Backend:
    name = "none"
    model = ""

    def complete(self, system: str, user: str, schema: dict) -> tuple[dict, Usage]:
        raise NotImplementedError


class AnthropicBackend(Backend):
    name = "anthropic"

    def __init__(self, model: str):
        import anthropic
        self.model = model
        self.client = anthropic.Anthropic(max_retries=3, timeout=180)

    def complete(self, system, user, schema):
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        )
        u = response.usage
        usage = Usage(u.input_tokens or 0, u.output_tokens or 0, getattr(u, "cache_read_input_tokens", 0) or 0)
        if response.stop_reason == "refusal":
            raise RuntimeError("모델이 요청을 거절함 (refusal)")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("출력이 잘림 (max_tokens)")
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text), usage


def gemini_schema(schema: dict) -> dict:
    """Gemini responseSchema(OpenAPI 서브셋)용으로 지원하지 않는 키를 제거한다."""
    s = copy.deepcopy(schema)

    def strip(node):
        if isinstance(node, dict):
            for k in ("additionalProperties", "maxItems", "minItems", "minimum", "maximum"):
                node.pop(k, None)
            for v in node.values():
                strip(v)
        elif isinstance(node, list):
            for v in node:
                strip(v)
    strip(s)
    return s


class GeminiBackend(Backend):
    """Gemini REST 백엔드. 모델 체인을 순서대로 시도한다.

    - 503(과부하)·429(분당 한도)는 같은 모델에서 짧게 재시도 후 다음 모델로 넘어간다.
    - 404(모델 없음)·일일 한도 소진은 그 모델을 이번 실행에서 제외한다.
    - 한 모델이 연속 3개 항목에서 과부하로 실패하면 이번 실행에서 제외한다 (실행 시간 상한).
    """
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, models: list[str], min_interval: float = 4.0):
        self.models = list(models)
        self.model = models[0]
        self.key = os.environ["GEMINI_API_KEY"]
        self.min_interval = min_interval          # 무료 등급 RPM 제한 대응 (기본 15/min)
        self._lock = threading.Lock()
        self._last = 0.0
        self.disabled: dict[str, str] = {}        # model -> 이유
        self.overload_streak: dict[str, int] = {}
        self.models_used: dict[str, int] = {}
        self.client = httpx.Client(timeout=120)

    def _throttle(self):
        with self._lock:
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def _try_model(self, model: str, body: dict) -> tuple[dict, Usage]:
        url = self.URL.format(model=model)
        last_err: Exception | None = None
        for attempt in range(3):
            self._throttle()
            r = self.client.post(url, headers={"x-goog-api-key": self.key}, json=body)
            if r.status_code == 429 and re.search(r"PerDay|per day|daily", r.text, re.I):
                self.disabled[model] = f"일일 한도 소진: {r.text[:120]}"
                raise RuntimeError(self.disabled[model])
            if r.status_code == 404 or (r.status_code == 400 and "model" in r.text.lower()):
                self.disabled[model] = f"모델 사용 불가: {r.text[:120]}"
                raise RuntimeError(self.disabled[model])
            if r.status_code in (429, 500, 503):
                last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:160]}")
                retry_after = r.headers.get("retry-after")
                time.sleep(min(30.0, float(retry_after) if retry_after else 5 * (attempt + 1)))
                continue
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
            cand = (data.get("candidates") or [None])[0]
            if not cand or cand.get("finishReason") not in (None, "STOP"):
                raise RuntimeError(f"응답 없음/중단: {json.dumps(data)[:300]}")
            text = "".join(p.get("text", "") for p in cand["content"]["parts"])
            um = data.get("usageMetadata", {})
            usage = Usage(um.get("promptTokenCount", 0), um.get("candidatesTokenCount", 0),
                          um.get("cachedContentTokenCount", 0))
            self.overload_streak[model] = 0
            self.models_used[model] = self.models_used.get(model, 0) + 1
            return json.loads(text), usage
        # 과부하/분당 한도로 3회 모두 실패
        self.overload_streak[model] = self.overload_streak.get(model, 0) + 1
        if self.overload_streak[model] >= 3:
            self.disabled[model] = f"연속 과부하 {self.overload_streak[model]}회: {last_err}"
        raise last_err or RuntimeError("재시도 초과")

    def complete(self, system, user, schema):
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4000,
                "responseMimeType": "application/json",
                "responseSchema": gemini_schema(schema),
            },
        }
        errors = []
        for model in self.models:
            if model in self.disabled:
                continue
            try:
                return self._try_model(model, body)
            except RuntimeError as e:
                errors.append(f"{model}: {e}")
        if all(m in self.disabled for m in self.models):
            raise RuntimeError("사용 가능한 Gemini 모델 없음: " + " | ".join(f"{m}={r[:60]}" for m, r in self.disabled.items()))
        raise RuntimeError(" / ".join(errors)[:400])


def make_backend(cfg: dict) -> Backend | None:
    provider = (cfg.get("provider") or "auto").lower()
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "auto":
        provider = "gemini" if has_gemini else "anthropic" if has_anthropic else "none"
    if provider == "gemini" and has_gemini:
        models = cfg.get("gemini_models") or [cfg.get("gemini_model", "gemini-3.8-flash")]
        return GeminiBackend(list(models), float(cfg.get("gemini_min_interval_seconds", 4.0)))
    if provider == "anthropic" and has_anthropic:
        return AnthropicBackend(cfg.get("anthropic_model", cfg.get("model", "claude-opus-5-5")))
    return None


# ------------------------------------------------------------------ 적용

class Enricher:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.backend = make_backend(cfg) if cfg.get("enabled", True) else None

    @property
    def available(self) -> bool:
        return self.backend is not None

    def enrich_one(self, item: Item, stats: EnrichStats) -> Item:
        stats.attempted += 1
        try:
            data, usage = self.backend.complete(SYSTEM_PROMPT, build_user_prompt(item), OUTPUT_SCHEMA)
            stats.input_tokens += usage.input_tokens
            stats.output_tokens += usage.output_tokens
            stats.cache_read_tokens += usage.cache_read_tokens
            apply_result(item, data)
        except Exception as e:  # 실패는 개별 항목에 국한
            stats.failed += 1
            stats.errors.append(f"{item.id}: {type(e).__name__}: {str(e)[:200]}")
            log.warning("LLM 실패 %s: %s", item.id, e)
            return apply_fallback(item)
        stats.succeeded += 1
        return item

    def enrich(self, items: list[Item]) -> EnrichStats:
        stats = EnrichStats()
        if not items:
            return stats
        if not self.available:
            log.warning("LLM 키 없음(GEMINI_API_KEY 또는 ANTHROPIC_API_KEY): %d건을 초록 발췌로 대체", len(items))
            for it in items:
                apply_fallback(it)
            stats.failed = len(items)
            stats.errors.append("LLM API 키 미설정")
            return stats
        stats.provider, stats.model = self.backend.name, self.backend.model
        workers = int(self.cfg.get("concurrency", 4)) if self.backend.name != "gemini" else 1
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(self.enrich_one, it, stats) for it in items]
            for f in as_completed(futs):
                f.result()
        if getattr(self.backend, "models_used", None):
            stats.models_used = dict(self.backend.models_used)
            stats.model = max(stats.models_used, key=stats.models_used.get)
        log.info("LLM 요약(%s/%s): 성공 %d / 실패 %d, 입력 %d 출력 %d (캐시 %d) 모델별 %s", stats.provider, stats.model,
                 stats.succeeded, stats.failed, stats.input_tokens, stats.output_tokens, stats.cache_read_tokens,
                 stats.models_used)
        return stats


def apply_result(item: Item, data: dict) -> Item:
    """검증된 JSON을 레코드에 반영한다. 허용 목록 밖 값은 무시."""
    item.title_ko = (data.get("title_ko") or "").strip() or None
    item.summary_ko = (data.get("summary_ko") or "").strip() or excerpt(item.abstract)
    item.key_points_ko = [k.strip() for k in data.get("key_points_ko") or [] if isinstance(k, str) and k.strip()][:4]
    item.summary_source = "llm"
    llm_cats = [c for c in data.get("categories") or [] if c in CATEGORY_KEYS]
    item.categories = (llm_cats + [c for c in item.categories if c not in llm_cats])[:4]
    if item.trial and "trial" in item.categories:
        item.categories = ["trial"] + [c for c in item.categories if c != "trial"]
    if item.evidence in ("other", "review") and data.get("evidence") in EVIDENCE_KEYS:
        item.evidence = data["evidence"]
    if item.trial and (data.get("eligibility_ko") or "").strip():
        item.trial.eligibility_ko = data["eligibility_ko"].strip()
    try:
        rel = max(1, min(5, int(data.get("patient_relevance", 3))))
    except (TypeError, ValueError):
        rel = 3
    item.importance = round(min(1.0, item.importance * 0.8 + 0.2 * (rel / 5)), 2)
    return item
