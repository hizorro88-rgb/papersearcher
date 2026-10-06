"""Claude로 한국어 제목·요약·핵심 포인트·임상시험 참여 조건을 만든다.

원칙: 입력(제목·초록·선정기준)에 없는 사실을 만들지 않는다. 출력은 JSON 스키마로 강제한다.
API 키가 없거나 호출이 실패하면 초록 발췌로 대체하고 summary_source="excerpt"로 표시한다.
"""
from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

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
class EnrichStats:
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


class Enricher:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.model = cfg.get("model", "claude-opus-5-5")
        self.client = None
        if cfg.get("enabled", True) and os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            self.client = anthropic.Anthropic(max_retries=3, timeout=180)

    @property
    def available(self) -> bool:
        return self.client is not None

    def _call(self, item: Item, stats: EnrichStats) -> dict:
        import anthropic

        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": build_user_prompt(item)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        )
        u = response.usage
        stats.input_tokens += u.input_tokens or 0
        stats.output_tokens += u.output_tokens or 0
        stats.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        if response.stop_reason == "refusal":
            raise RuntimeError("모델이 요청을 거절함 (refusal)")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("출력이 잘림 (max_tokens)")
        text = next(b.text for b in response.content if b.type == "text")
        import json
        return json.loads(text)

    def enrich_one(self, item: Item, stats: EnrichStats) -> Item:
        stats.attempted += 1
        try:
            data = self._call(item, stats)
        except Exception as e:  # 실패는 개별 항목에 국한
            stats.failed += 1
            stats.errors.append(f"{item.id}: {type(e).__name__}: {str(e)[:200]}")
            log.warning("LLM 실패 %s: %s", item.id, e)
            return apply_fallback(item)
        item.title_ko = data["title_ko"].strip() or None
        item.summary_ko = data["summary_ko"].strip()
        item.key_points_ko = [k.strip() for k in data["key_points_ko"] if k.strip()][:4]
        item.summary_source = "llm"
        # 규칙 분류와 합집합. LLM이 준 카테고리를 앞에 둔다.
        llm_cats = [c for c in data["categories"] if c in CATEGORY_KEYS]
        item.categories = (llm_cats + [c for c in item.categories if c not in llm_cats])[:4]
        if item.evidence in ("other", "review") and data["evidence"] in EVIDENCE_KEYS:
            item.evidence = data["evidence"]
        if item.trial and data.get("eligibility_ko", "").strip():
            item.trial.eligibility_ko = data["eligibility_ko"].strip()
        rel = int(data.get("patient_relevance", 3))
        item.importance = round(min(1.0, item.importance * 0.8 + 0.2 * (rel / 5)), 2)
        stats.succeeded += 1
        return item

    def enrich(self, items: list[Item]) -> EnrichStats:
        stats = EnrichStats()
        if not items:
            return stats
        if not self.available:
            log.warning("ANTHROPIC_API_KEY 없음: %d건을 초록 발췌로 대체", len(items))
            for it in items:
                apply_fallback(it)
            stats.failed = len(items)
            stats.errors.append("ANTHROPIC_API_KEY 미설정")
            return stats
        workers = int(self.cfg.get("concurrency", 4))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(self.enrich_one, it, stats) for it in items]
            for f in as_completed(futs):
                f.result()
        log.info("LLM 요약: 성공 %d / 실패 %d, 입력 %d 출력 %d (캐시 %d)",
                 stats.succeeded, stats.failed, stats.input_tokens, stats.output_tokens, stats.cache_read_tokens)
        return stats
