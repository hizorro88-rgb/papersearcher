"""임상시험 선정/제외 기준 원문에서 '맞춤 찾기'용 구조화 조건을 규칙으로 뽑는다.

LLM이 없어도 동작해야 하므로 보수적으로 뽑는다. 애매하면 비워 둔다(= 알 수 없음).
LLM 결과가 있으면 그것이 우선이고, 여기서 뽑은 값은 빈칸을 채우는 용도로만 쓴다.
"""
from __future__ import annotations

import re

from .models import BIOMARKER_KEYS, PRIOR_KEYS, SETTING_KEYS, Item, TrialMatch

_SPLIT = re.compile(r"exclusion criteria\s*:?", re.I)

# --- 질병 상태
_SETTING = [
    ("metastatic", re.compile(r"\bmetasta|stage\s*IV\b|stage 4\b", re.I)),
    ("locally_advanced", re.compile(r"locally[- ]advanced|unresectable", re.I)),
    ("resectable", re.compile(r"\b(borderline[- ]resectable|resectable)\b", re.I)),
    ("neoadjuvant", re.compile(r"neo-?adjuvant|pre-?operative", re.I)),
    ("adjuvant", re.compile(r"(?<!neo)(?<!neo-)\badjuvant|after (curative|complete|R0|R1)?\s*(surgical )?resection|post-?operative|resected", re.I)),
]

# --- 이전 치료 줄 수
_FIRST_LINE = re.compile(
    r"first[- ]line|\b1L\b|treatment[- ]na[iï]ve|chemo(therapy)?[- ]na[iï]ve|previously untreated|\buntreated\b"
    r"|no (prior|previous) (systemic|chemo|anti-?cancer|anti-?neoplastic)"
    r"|(have|has|had) not (previously )?received (any )?(prior |previous )?(systemic|chemo)", re.I)
_AFTER_FIRST = re.compile(
    r"(after|following|post|progress\w* (on|after|during|following)|failure of|failed|refractory to|intoleran\w+ (to|of)|received|completed)"
    r"[^.\n]{0,40}?(first[- ]line|\b1L\b|one (prior )?line|standard (of care )?(therapy|treatment|chemotherapy))", re.I)
_PRETREATED = re.compile(
    r"second[- ]line|\b2L\b|previously treated|prior (systemic )?(therap|chemotherap|treatment|line)|progress\w* (on|after|during|following)"
    r"|refractory|relaps|intoleran|at least (one|1) (prior|previous)|≥\s*1 (prior|previous)|one or more (prior|previous)", re.I)
_SECOND_ONLY = re.compile(r"second[- ]line|\b2L\b|(only )?(one|1) (prior|previous) (line|regimen|systemic)|no more than (one|1) (prior|previous)", re.I)
_THIRD_PLUS = re.compile(r"third[- ]line|\b3L\b|at least (two|2) (prior|previous)|≥\s*2 (prior|previous)|two or more (prior|previous)|(two|2) (prior|previous) (lines|regimens)", re.I)

# --- 이전 치료 약제 (받았어야 함 / 받았으면 안 됨)
_PRIOR_DRUG = {
    "gemcitabine": re.compile(r"gemcitabine", re.I),
    "FOLFIRINOX": re.compile(r"FOLFIRINOX|FOLFOXIRI", re.I),
    "platinum": re.compile(r"platinum|oxaliplatin|cisplatin", re.I),
    "fluoropyrimidine": re.compile(r"fluoropyrimidine|5-?FU|fluorouracil|capecitabine|S-1\b", re.I),
    "irinotecan": re.compile(r"irinotecan|nal-?IRI|onivyde", re.I),
    "taxane": re.compile(r"nab-?paclitaxel|paclitaxel|taxane|abraxane", re.I),
    "immunotherapy": re.compile(r"immune checkpoint|anti-?PD-?(1|L1)|PD-?1\b|PD-?L1|CTLA-?4|immunotherap", re.I),
    "KRAS_inhibitor": re.compile(r"(K?RAS|G12[CDVR]|pan-?RAS)[- ]?(targeted |specific |directed )?inhibitor|RAS\(ON\)|sotorasib|adagrasib|daraxonrasib|elironrasib|zoldonrasib", re.I),
    "radiotherapy": re.compile(r"radiotherap|radiation therap", re.I),
}
_PRIOR_REQ_CTX = re.compile(
    r"(prior|previous(ly)?|received|treated with|after|following|progress\w* (on|after|during)|refractory to|failure of|intoleran\w+ (to|of)|containing|based)"
    r"[^.\n;]{0,60}?(%s)", re.I)
_PRIOR_EXC_CTX = re.compile(
    r"(no prior|no previous|not (have |had )?(previously )?received|never received|prior|previous(ly)?|any prior|exposure to|treated with)"
    r"[^.\n;]{0,60}?(%s)", re.I)

# --- 바이오마커
_BIOMARKER = {
    "KRAS_G12C": re.compile(r"KRAS\s*[- ]?\s*(p\.)?G12C|\bG12C\b", re.I),
    "KRAS_G12D": re.compile(r"KRAS\s*[- ]?\s*(p\.)?G12D|\bG12D\b", re.I),
    "KRAS_G12V": re.compile(r"KRAS\s*[- ]?\s*(p\.)?G12V|\bG12V\b", re.I),
    "KRAS_G12R": re.compile(r"KRAS\s*[- ]?\s*(p\.)?G12R|\bG12R\b", re.I),
    "KRAS_mutant": re.compile(r"KRAS[- ](mutat|mutant|altered|positive)|(mutat|alteration)\w* (in|of) (the )?KRAS|RAS[- ]mutant|RAS mutation", re.I),
    "KRAS_wild": re.compile(r"KRAS[- ]?(wild[- ]?type|WT\b)|wild[- ]?type KRAS", re.I),
    "BRCA_PALB2": re.compile(r"\bBRCA\s*[12]?|\bPALB2\b|germline BRCA|gBRCA", re.I),
    "HRD": re.compile(r"homologous recombination|\bHRD\b|\bHRR\b", re.I),
    "MSI_H": re.compile(r"MSI-?H|microsatellite instability|dMMR|mismatch repair[- ]deficien", re.I),
    "HER2": re.compile(r"\bHER2\b|\bERBB2\b", re.I),
    "CLDN18_2": re.compile(r"CLDN\s*18\.?2|claudin[- ]?18\.?2", re.I),
    "NTRK": re.compile(r"\bNTRK\b|TRK fusion", re.I),
    "NRG1": re.compile(r"\bNRG1\b", re.I),
    "TMB_high": re.compile(r"TMB-?H|tumou?r mutational burden", re.I),
}
_BIOMARKER_REQ_CTX = re.compile(
    r"(positive|expressi|amplif|mutat|mutant|alteration|fusion|rearrange|harbou?r|documented|confirmed|presence of|status|deficien|high|\bwith\b|\bhave\b|\bhas\b)", re.I)

_ECOG = re.compile(r"(ECOG|Eastern Cooperative Oncology Group|WHO performance|performance status|Karnofsky)[^.\n;]{0,60}?"
                   r"(?P<spec>(?:≤|<=|of|=|:)?\s*\b[0-3]\b(?:\s*(?:[-–~]|to|or|,|/|and)\s*\b[0-3]\b)*)", re.I)
_NEG = re.compile(r"\bno\b|without|absence|absent|non-?metastatic|not metastatic|\bM0\b|\bprior\b|previous|history of|received|completed|allowed|permitted|eligible for", re.I)
_SOFT = re.compile(r"adjuvant|allowed|permitted|acceptable|except|may have|optional|regardless|not required|if ", re.I)
_NET = re.compile(r"neuroendocrine|\bp?NETs?\b|carcinoid|\bNEC\b", re.I)
_PDAC = re.compile(r"adenocarcinoma|\bPDAC\b|ductal|\bPDA\b", re.I)
_MEASURABLE = re.compile(r"measurable (disease|lesion|tumou?r)", re.I)


def _inclusion_exclusion(text: str) -> tuple[str, str]:
    parts = _SPLIT.split(text, maxsplit=1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+|\n+", text) if s.strip()]


def extract_rules(item: Item) -> TrialMatch | None:
    t = item.trial
    if not t:
        return None
    m = TrialMatch(source="rules")
    text = t.eligibility_text or ""
    inc, exc = _inclusion_exclusion(text)
    head = " ".join([item.title or "", " ".join(t.conditions), item.abstract or ""])

    # 질병 상태: 선정 기준 문장(부정·과거력 문장 제외) + 제목·대상 질환에서
    ctx_sents = [s for s in _sentences(inc) if not _NEG.search(s)] + [item.title or ""] + list(t.conditions)
    for key, rx in _SETTING:
        if any(rx.search(s) for s in ctx_sents):
            m.setting.append(key)
    if not m.setting:
        for key, rx in _SETTING:
            if rx.search(head):
                m.setting.append(key)
    # 보조요법 시험은 보통 제외 기준에 'metastatic'이 들어 있다 → 전이성 삭제
    if "adjuvant" in m.setting and "metastatic" in m.setting and re.search(r"metasta", exc, re.I) \
            and not any(re.search(r"metasta", s, re.I) for s in ctx_sents):
        m.setting.remove("metastatic")
    m.setting = [k for k in SETTING_KEYS if k in m.setting]

    # 이전 치료 줄 수: 선정 기준 문장에서. "보조항암은 허용" 같은 문장은 치료 경험 요구로 보지 않는다
    inc_s = _sentences(inc)
    pre_s = [x for x in inc_s if _PRETREATED.search(x) and not _SOFT.search(x)]
    first_s = [x for x in inc_s if _FIRST_LINE.search(x) and not re.search(r"adjuvant|except", x, re.I)]
    if any(_THIRD_PLUS.search(x) for x in inc_s):
        m.min_prior_lines = 2
    elif any(_AFTER_FIRST.search(x) for x in inc_s) or (pre_s and not first_s):
        m.min_prior_lines = 1
        if any(_SECOND_ONLY.search(x) for x in pre_s + first_s):
            m.max_prior_lines = 1
    elif first_s and not pre_s:
        m.max_prior_lines = 0
    if m.min_prior_lines is None and m.max_prior_lines is None and not pre_s:
        # 제외 기준에 "진행성 상태에서 이전 전신치료 받음"이 있거나 제목이 1차 치료이면 → 1차 전용
        exc_prior = any(re.search(r"(prior|previous|any)\s+(systemic|chemo|anti-?cancer|anti-?neoplastic)", x, re.I)
                        and not re.search(r"within|weeks|days|months|neo-?adjuvant|adjuvant|peri-?operative", x, re.I)
                        for x in _sentences(exc))
        if exc_prior or re.search(r"first[- ]line|\b1L\b|treatment[- ]na[iï]ve|previously untreated", item.title or "", re.I):
            m.max_prior_lines = 0

    # 이전 치료 약제
    for key, rx in _PRIOR_DRUG.items():
        pat_req = re.compile(_PRIOR_REQ_CTX.pattern % rx.pattern, re.I)
        pat_exc = re.compile(_PRIOR_EXC_CTX.pattern % rx.pattern, re.I)
        req = any(pat_req.search(s) and not re.search(r"\bno (prior|previous)|not (have )?received|never", s, re.I)
                  for s in _sentences(inc))
        excl = any(pat_exc.search(s) for s in _sentences(exc)) or \
            any(re.search(r"\bno (prior|previous)[^.\n;]{0,60}?(%s)" % rx.pattern, s, re.I) for s in _sentences(inc))
        if key == "radiotherapy":
            # 방사선은 대개 '최근 N주 이내 금지'(휴약 기간)라서 규칙으로는 판단하지 않는다 (LLM만)
            req = excl = False
        if req:
            m.prior_required.append(key)
        if excl:
            m.prior_excluded.append(key)
    # 1차 치료 전용이면 '이전 치료 필요'는 모순 → 비움
    if m.max_prior_lines == 0:
        m.prior_required = []
    m.prior_required = [k for k in PRIOR_KEYS if k in m.prior_required]
    m.prior_excluded = [k for k in PRIOR_KEYS if k in m.prior_excluded and k not in m.prior_required]

    # 바이오마커: 선정 기준 문장 중 '양성/변이/보유' 맥락이 있는 것만
    inc_sents = _sentences(inc)
    for key, rx in _BIOMARKER.items():
        hit = any(rx.search(s) and _BIOMARKER_REQ_CTX.search(s) and not re.search(r"\bno\b|without|negative|absence|regardless|irrespective|not required", s, re.I)
                  for s in inc_sents)
        if hit:
            m.biomarkers_required.append(key)
        if any(rx.search(s) for s in _sentences(exc)) and key in ("MSI_H", "KRAS_G12C", "BRCA_PALB2", "HER2", "NTRK", "NRG1"):
            if key not in m.biomarkers_required:
                m.biomarkers_excluded.append(key)
    # 특정 KRAS 아형이 있으면 일반 'KRAS 변이'는 중복
    if any(k.startswith("KRAS_G12") for k in m.biomarkers_required):
        m.biomarkers_required = [k for k in m.biomarkers_required if k != "KRAS_mutant"]
    if "KRAS_wild" in m.biomarkers_required and "KRAS_mutant" in m.biomarkers_required:
        m.biomarkers_required = [k for k in m.biomarkers_required if k not in ("KRAS_wild", "KRAS_mutant")]
    # 제목·중재에 특정 표적이 없고 다른 암종(대장암 등) 코호트 설명에서만 나온 바이오마커는 신뢰도가 낮다 → 제목/질환/중재에도 없으면 버린다
    title_ctx = " ".join([item.title or "", " ".join(t.interventions), " ".join(t.conditions)])
    strong = {k for k in m.biomarkers_required if _BIOMARKER[k].search(title_ctx) or _BIOMARKER[k].search(item.abstract or "")}
    weak_only = [k for k in m.biomarkers_required if k not in strong]
    if weak_only and len(t.conditions) > 1 and not any(re.search(r"pancrea", c, re.I) for c in t.conditions[:1]):
        m.biomarkers_required = [k for k in m.biomarkers_required if k in strong]
    m.biomarkers_required = [k for k in BIOMARKER_KEYS if k in m.biomarkers_required]
    m.biomarkers_excluded = [k for k in BIOMARKER_KEYS if k in m.biomarkers_excluded]

    # ECOG
    e = _ECOG.search(inc)
    if e:
        digits = [int(d) for d in re.findall(r"[0-3]", e.group("spec"))]
        if digits:
            m.ecog_max = max(digits)
    if _MEASURABLE.search(inc):
        m.measurable_required = True
    return m


def merge_match(rules: TrialMatch | None, llm: TrialMatch | None) -> TrialMatch | None:
    """LLM 결과를 우선하되 비어 있는 칸은 규칙 값으로 채운다."""
    if llm is None:
        return rules
    if rules is None:
        return llm
    out = llm.model_copy()
    if not out.setting:
        out.setting = rules.setting
    if out.min_prior_lines is None:
        out.min_prior_lines = rules.min_prior_lines
    if out.max_prior_lines is None:
        out.max_prior_lines = rules.max_prior_lines
    if out.ecog_max is None:
        out.ecog_max = rules.ecog_max
    if out.measurable_required is None:
        out.measurable_required = rules.measurable_required
    out.source = "llm"
    return out


def match_from_llm(data: dict | None) -> TrialMatch | None:
    """LLM JSON → TrialMatch. 허용된 키만 남기고 -1/빈값은 None으로."""
    if not data:
        return None
    def ints(v):
        return None if v is None or int(v) < 0 else int(v)
    def keys(v, allowed):
        return [k for k in allowed if k in (v or [])]
    meas = data.get("measurable_required")
    return TrialMatch(
        setting=keys(data.get("setting"), SETTING_KEYS),
        min_prior_lines=ints(data.get("min_prior_lines")),
        max_prior_lines=ints(data.get("max_prior_lines")),
        prior_required=keys(data.get("prior_required"), PRIOR_KEYS),
        prior_excluded=keys(data.get("prior_excluded"), PRIOR_KEYS),
        biomarkers_required=keys(data.get("biomarkers_required"), BIOMARKER_KEYS),
        biomarkers_excluded=keys(data.get("biomarkers_excluded"), BIOMARKER_KEYS),
        ecog_max=ints(data.get("ecog_max")),
        measurable_required=None if meas in (None, "unknown") else (meas in (True, "yes", "true")),
        notes_ko=(data.get("notes_ko") or "").strip(),
        key_exclusions_ko=[s.strip() for s in (data.get("key_exclusions_ko") or []) if s and s.strip()][:6],
        source="llm",
    )


SETTING_KO = {"metastatic": "전이성(4기)", "locally_advanced": "국소진행(수술 불가)", "resectable": "수술 가능·경계성",
              "adjuvant": "수술 후 보조치료", "neoadjuvant": "수술 전 선행치료"}
PRIOR_KO = {"gemcitabine": "젬시타빈", "FOLFIRINOX": "FOLFIRINOX", "platinum": "백금계(옥살리플라틴 등)",
            "fluoropyrimidine": "5-FU 계열", "irinotecan": "이리노테칸", "taxane": "탁산(아브락산 등)",
            "immunotherapy": "면역항암제", "KRAS_inhibitor": "KRAS 억제제", "radiotherapy": "방사선치료"}
BIOMARKER_KO = {"KRAS_G12C": "KRAS G12C", "KRAS_G12D": "KRAS G12D", "KRAS_G12V": "KRAS G12V", "KRAS_G12R": "KRAS G12R",
                "KRAS_mutant": "KRAS 변이(아형 무관)", "KRAS_wild": "KRAS 정상(wild-type)", "BRCA_PALB2": "BRCA1/2·PALB2",
                "HRD": "상동재조합결핍(HRD)", "MSI_H": "MSI-H/dMMR", "HER2": "HER2", "CLDN18_2": "CLDN18.2",
                "NTRK": "NTRK 융합", "NRG1": "NRG1 융합", "TMB_high": "TMB 높음", "other": "기타 표적"}


def lines_ko(m: TrialMatch) -> str:
    lo, hi = m.min_prior_lines, m.max_prior_lines
    if hi == 0:
        return "1차 치료(아직 항암 안 받은 분)"
    if lo is not None and hi is not None:
        return f"이전 항암 {lo}~{hi}가지 받은 분"
    if lo is not None:
        return f"이전 항암 {lo}가지 이상 받은 분"
    if hi is not None:
        return f"이전 항암 {hi}가지 이하"
    return "제한 없음 또는 미확인"


def histology(item: Item) -> str:
    """시험이 어떤 조직형을 대상으로 하는지: pdac / net / both / any(고형암 바스켓 등)."""
    t = item.trial
    text = " ".join([item.title or "", " ".join(t.conditions if t else []), (item.abstract or "")[:600]])
    net, pdac = bool(_NET.search(text)), bool(_PDAC.search(text))
    if net and pdac:
        return "both"
    if net:
        return "net"
    if pdac:
        return "pdac"
    return "any"
