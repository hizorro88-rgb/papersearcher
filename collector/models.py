"""공통 데이터 모델."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

ItemType = Literal["paper", "preprint", "trial", "regulatory", "press", "news", "guideline"]
CATEGORY_KEYS = ["drug", "trial", "surgery", "treatment", "diagnosis", "supportive", "industry", "basic"]
EVIDENCE_KEYS = [
    "guideline", "meta", "phase3", "phase2", "phase1", "rct",
    "observational", "review", "case", "preclinical", "press", "other",
]


class Source(BaseModel):
    name: str
    url: str
    journal: Optional[str] = None


class Links(BaseModel):
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    nct: list[str] = Field(default_factory=list)


class TrialLocation(BaseModel):
    facility: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None


class TrialContact(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


SETTING_KEYS = ["metastatic", "locally_advanced", "resectable", "adjuvant", "neoadjuvant"]
PRIOR_KEYS = ["gemcitabine", "FOLFIRINOX", "platinum", "fluoropyrimidine", "irinotecan", "taxane",
              "immunotherapy", "KRAS_inhibitor", "radiotherapy"]
BIOMARKER_KEYS = ["KRAS_G12C", "KRAS_G12D", "KRAS_G12V", "KRAS_G12R", "KRAS_mutant", "KRAS_wild",
                  "BRCA_PALB2", "HRD", "MSI_H", "HER2", "CLDN18_2", "NTRK", "NRG1", "TMB_high", "other"]


class TrialMatch(BaseModel):
    """맞춤 임상시험 찾기용 구조화 조건. 규칙(rules)으로 먼저 뽑고 LLM(llm)이 보정한다.

    - min_prior_lines / max_prior_lines: 진행성(전이·국소진행) 상태에서 받은 전신 항암 요법 수의 하한/상한.
      max 0 = 1차 치료 전용, min 1 = 이전 치료 경험 필요. None = 제한 없음/알 수 없음.
    """
    setting: list[str] = Field(default_factory=list)          # SETTING_KEYS
    min_prior_lines: Optional[int] = None
    max_prior_lines: Optional[int] = None
    prior_required: list[str] = Field(default_factory=list)   # PRIOR_KEYS
    prior_excluded: list[str] = Field(default_factory=list)   # PRIOR_KEYS
    biomarkers_required: list[str] = Field(default_factory=list)  # BIOMARKER_KEYS
    biomarkers_excluded: list[str] = Field(default_factory=list)
    ecog_max: Optional[int] = None
    measurable_required: Optional[bool] = None
    notes_ko: str = ""                                        # 한 줄: 어떤 환자를 위한 시험인지
    key_exclusions_ko: list[str] = Field(default_factory=list)
    source: Literal["rules", "llm"] = "rules"


class TrialInfo(BaseModel):
    """ClinicalTrials.gov에서 오는 임상시험 전용 정보."""
    nct_id: str
    phase: Optional[str] = None            # "PHASE1", "PHASE2", "PHASE1/PHASE2", "PHASE3", "NA"
    status: Optional[str] = None           # RECRUITING, ACTIVE_NOT_RECRUITING, COMPLETED ...
    study_type: Optional[str] = None
    sponsor: Optional[str] = None
    interventions: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    eligibility_text: Optional[str] = None  # 원문 선정/제외 기준
    eligibility_ko: Optional[str] = None    # LLM이 정리한 한국어 핵심 조건
    min_age: Optional[str] = None
    max_age: Optional[str] = None
    sex: Optional[str] = None
    enrollment: Optional[int] = None
    start_date: Optional[str] = None
    primary_completion_date: Optional[str] = None
    has_results: bool = False
    locations_kr: list[TrialLocation] = Field(default_factory=list)
    location_countries: list[str] = Field(default_factory=list)
    n_locations: int = 0
    contacts: list[TrialContact] = Field(default_factory=list)
    last_update_posted: Optional[str] = None
    match: Optional[TrialMatch] = None       # 맞춤 찾기용 구조화 조건


class HistoryEvent(BaseModel):
    date: str
    event: str
    detail: Optional[str] = None


class Review(BaseModel):
    status: Literal["auto", "verified", "flagged", "hidden"] = "auto"
    note: Optional[str] = None


class Item(BaseModel):
    id: str
    type: ItemType
    title: str
    title_ko: Optional[str] = None
    summary_ko: Optional[str] = None
    summary_source: Literal["pending", "llm", "excerpt", "manual"] = "pending"
    key_points_ko: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    published_at: Optional[str] = None     # ISO date
    authors: list[str] = Field(default_factory=list)
    source: Source
    links: Links = Field(default_factory=Links)
    pub_types: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    evidence: str = "other"
    relevance: float = 0.0
    importance: float = 0.0
    trial: Optional[TrialInfo] = None
    first_seen: str = Field(default_factory=lambda: date.today().isoformat())
    last_updated: str = Field(default_factory=lambda: date.today().isoformat())
    history: list[HistoryEvent] = Field(default_factory=list)
    review: Review = Field(default_factory=Review)

    @property
    def display_title(self) -> str:
        return self.title_ko or self.title

    @property
    def safe_id(self) -> str:
        return self.id.replace(":", "_").replace("/", "_")


def make_id(*, nct: str | None = None, pmid: str | None = None, doi: str | None = None,
            url: str | None = None) -> str:
    """ID 우선순위: nct > pmid > doi > url 해시."""
    import hashlib

    if nct:
        return f"nct:{nct.upper()}"
    if pmid:
        return f"pmid:{pmid}"
    if doi:
        return f"doi:{doi.lower()}"
    if url:
        return "url:" + hashlib.sha1(url.encode()).hexdigest()[:16]
    raise ValueError("ID를 만들 식별자가 없습니다")
