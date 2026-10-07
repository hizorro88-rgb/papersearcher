# 췌장암 정보 수집·정리 위키 (PaperSearcher) 설계 문서

작성일: 2026-10-06 · 상태: Phase 0·1 구현 완료 (운영자 설정은 [SETUP.md](SETUP.md) 참고)

---

## 1. 목표와 요구사항 정리

| # | 요구사항 (원문 요약) | 설계 결정 |
|---|---|---|
| R1 | 췌장암 신약·치료법 논문, 제약사 소식 등 광범위 수집 | PubMed, ClinicalTrials.gov, Europe PMC(프리프린트 포함), FDA/EMA/식약처, 제약사·바이오 전문지 RSS를 소스 어댑터로 수집 |
| R2 | 지속 업데이트 + 기존 정보도 갱신 | 레코드 ID 기반 병합. 임상시험 상태 변경, 프리프린트→정식 출판, 승인 상태 변화를 `history`에 기록 |
| R3 | 각 내용에 출처 | 모든 레코드는 최소 1개 원문 URL 필수. 출처 없는 항목은 저장하지 않음 |
| R4 | 매일 스케줄, GitHub에서 실행 (PC 자원 X) | GitHub Actions `schedule` cron. 공개 리포지토리는 Actions 무료·무제한 |
| R5 | 어디서나 열람 | GitHub Pages 정적 사이트 (모바일 대응), RSS 피드 제공 |
| R6 | 날짜별 보기 | `일일 다이제스트` 페이지 자동 생성 (`/daily/2026/10/06/`) |
| R7 | 카테고리별 보기 (신약 / 수술 / 치료 등) | 다중 라벨 분류. 카테고리별 페이지 + 클라이언트 측 필터 탐색기 |
| R7-1 | **임상** 카테고리: 어떤 임상시험이 있고, 조건은 무엇이며, 어떻게 신청하는지 | ClinicalTrials.gov 전용 어댑터로 선정·제외 기준, 국내 실시기관, 연락처를 수집. 시험별 페이지 + "국내 모집 중" 목록 + 참여 방법 가이드 |
| R8 | 응급상황 대처 가이드, 쉽게 찾기 | 사람이 작성·검수하는 정적 가이드. 상단 고정 "응급" 버튼, 검색 가중치 부여 |
| R9 | 여러 사람이 보고 댓글 | giscus (GitHub Discussions 기반, 무료, 서버 불필요) |
| R10 | 무료 · 공개 위키 형태 | 공개 리포지토리 + "이 페이지 편집" 링크로 PR 기여. 전 과정 비용 0원 (LLM 요약은 선택) |
| R11 | GitHub Pages 자동 게시 | 수집 워크플로 끝에서 사이트 빌드·배포까지 한 번에 수행 |

---

## 2. 전체 아키텍처

```
┌──────────────────────────── GitHub Actions (매일 06:00 KST) ────────────────────────────┐
│                                                                                         │
│  1. fetch        2. normalize     3. merge/update       4. classify      5. summarize   │
│  ┌──────────┐    ┌───────────┐    ┌───────────────┐     ┌───────────┐    ┌───────────┐  │
│  │ PubMed   │    │ 공통      │    │ data/items/   │     │ 규칙 기반 │    │ (선택)    │  │
│  │ CT.gov   │ →  │ 스키마로  │ →  │ 기존 레코드와 │  →  │ 키워드   │ →  │ Claude    │  │
│  │ EuropePMC│    │ 변환      │    │ 병합, 변경    │     │ 분류 +    │    │ 한국어    │  │
│  │ FDA/RSS  │    │           │    │ 이력 기록     │     │ 엔티티   │    │ 요약      │  │
│  └──────────┘    └───────────┘    └───────────────┘     └───────────┘    └───────────┘  │
│                                            │                                            │
│                                            ▼                                            │
│                    6. render (JSON → Markdown 페이지)  →  7. git commit (data/, docs/)  │
│                                            │                                            │
│                                            ▼                                            │
│                    8. mkdocs build  →  9. GitHub Pages 배포                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
        ┌───────────────────── 공개 사이트 (GitHub Pages) ─────────────────────┐
        │  오늘의 소식 │ 날짜별 │ 카테고리별 │ 주제(약물/시험)별 │ 응급 가이드 │
        │  검색 (클라이언트) │ 댓글 (giscus → GitHub Discussions) │ RSS       │
        └─────────────────────────────────────────────────────────────────────┘
```

핵심 원칙 세 가지:

1. **Git이 데이터베이스다.** 수집 결과는 `data/` 아래 JSON으로 커밋한다. 별도 DB·서버가 없고, 모든 변경 이력이 git 로그로 남으며, 누구나 fork해서 재현할 수 있다.
2. **자동 수집 결과와 사람이 쓰는 글을 분리한다.** 봇은 `data/`와 `docs/_generated/`만 쓴다. 가이드·위키 문서는 `docs/guides/` 등 사람이 관리하는 영역에 두어 봇이 덮어쓰지 않는다.
3. **출처 없는 내용은 존재하지 않는다.** LLM 요약은 원문 초록·본문만 입력으로 받고, 생성된 요약에는 항상 원문 링크가 따라붙는다.

---

## 3. 기술 스택과 선택 이유

| 영역 | 선택 | 대안 | 이유 |
|---|---|---|---|
| 실행 환경 | GitHub Actions (ubuntu-latest) | 로컬 cron, 클라우드 함수 | 공개 리포는 무료·무제한. PC 자원 불필요 |
| 수집 언어 | Python 3.12 (`httpx`, `feedparser`, `pydantic`) | Node.js | 생의학 API 클라이언트 생태계가 풍부, 테스트 쉬움 |
| 저장소 | 리포 내 JSON 파일 (`data/`) | SQLite, 외부 DB | 무료, 버전 관리, 리뷰 가능. 연간 1~2만 건 수준이면 충분 |
| 사이트 생성 | MkDocs + Material 테마 | Docusaurus, Hugo, Jekyll | 위키·문서형 사이트에 최적. 한국어 검색, 태그, 블로그(날짜별) 플러그인, giscus 공식 연동, 모바일 UI 우수 |
| 호스팅 | GitHub Pages | Cloudflare Pages, Netlify | 무료, 같은 리포에서 바로 배포 |
| 댓글 | giscus | utterances, Disqus | GitHub Discussions에 저장되므로 무료·데이터 소유. 댓글 작성에 GitHub 계정 필요 (제약) |
| 요약·번역 (필수) | 백엔드 교체형: **Gemini API 무료 등급**(`gemini-3.8-flash`, 기본) 또는 Claude API(`claude-opus-5-5`, 유료). 둘 다 JSON 스키마 강제 | GitHub Models(2026-07 종료), Groq/Mistral 무료 등급(한국어 품질 낮음) | 한국어 제공이 목표이므로 필수. Gemini면 0원, Claude면 월 $5~15. 키 미설정·실패 시 초록 발췌로 대체되고 다음 실행에서 재시도 |
| 운영비 | GitHub Sponsors + FUNDING.yml, 후원 페이지 | Buy Me a Coffee 등 | LLM 비용을 후원으로 충당. 사용량은 수집 현황 페이지에 공개 |

---

## 4. 데이터 소스

### 4.1 1차 소스 (Phase 1에 구현, 모두 무료 공개 API)

| 소스 | 종류 | 접근 방식 | 수집 내용 | 갱신 추적 가능 항목 |
|---|---|---|---|---|
| **PubMed** (NCBI E-utilities) | 논문 | `esearch` + `efetch` XML. 쿼리 예: `("pancreatic neoplasms"[MeSH] OR "pancreatic cancer"[tiab]) AND (last 3 days[dp])` | PMID, 제목, 초록, 저널, 저자, 출판일, DOI, 출판 유형(RCT/리뷰/메타분석) | 프리프린트 → 정식 게재 연결(DOI 매칭), 정정·철회 공지 |
| **ClinicalTrials.gov** (API v2) | 임상시험 | `/api/v2/studies?query.cond=pancreatic cancer&filter.advanced=AREA[LastUpdatePostDate]RANGE[...]` | NCT ID, 제목, 단계, 상태, 중재(약물), 스폰서, 결과 게시 여부 | **상태 변경**(모집 중→완료→결과 게시), 모집 인원, 1차 완료일 변경 |
| **Europe PMC** REST | 논문 + 프리프린트 | `search?query=...&src=PPR` 등 | bioRxiv/medRxiv 프리프린트, 전문 공개 여부, 인용 수 | 프리프린트의 정식 출판 연결, 인용 수 증가 |
| **openFDA / FDA 보도자료 RSS** | 규제 | Drugs@FDA API, 뉴스 RSS | 승인·신속심사 지정·안전성 서한 | 승인 상태 |

### 4.2 2차 소스 (Phase 2, RSS/키워드 필터)

| 소스 | 비고 |
|---|---|
| 제약사 보도자료 RSS | 췌장암 파이프라인 보유사 위주: Revolution Medicines, BMS, Amgen, AstraZeneca, Merck, Novartis, Roche, Ipsen, Eli Lilly, 한국 기업(유한양행, 삼성바이오에피스 등). `config/sources.yaml`에 목록 관리 |
| 바이오·제약 전문지 RSS | FierceBiotech, BioSpace, Endpoints News(일부 유료), Fierce Pharma. 키워드 `pancreatic` 필터 |
| 보도자료 와이어 | GlobeNewswire / PR Newswire / Business Wire 검색 RSS (`pancreatic cancer`) |
| 학회 | ASCO·ESMO·ASCO GI 초록 (공식 API 없음. 학회 기간에 PubMed/보도자료로 간접 수집) |
| 국내 | 식약처 보도자료, 국립암센터, 대한췌장담도학회 공지, 메디게이트뉴스·약업신문 RSS |
| EMA | EPAR·CHMP 회의 하이라이트 RSS |
| Semantic Scholar API | 기존 논문의 인용 수·영향력 갱신용 (무료 키) |

### 4.3 소스 설정 예시 (`config/sources.yaml`)

```yaml
pubmed:
  queries:
    - name: core
      term: '("Pancreatic Neoplasms"[MeSH] OR "pancreatic cancer"[tiab] OR "pancreatic ductal adenocarcinoma"[tiab] OR PDAC[tiab])'
  lookback_days: 3          # 지연 색인 대비 겹치게 조회, 중복은 병합 단계에서 제거
  api_key_env: NCBI_API_KEY # 선택. 없으면 3 req/s, 있으면 10 req/s
clinicaltrials:
  conditions: ["pancreatic cancer", "pancreatic adenocarcinoma"]
  lookback_days: 3
rss:
  - name: Revolution Medicines
    url: https://www.revmed.com/...
    kind: press
    trust: 0.8
    must_match: ["pancrea"]
```

---

## 5. 데이터 모델

### 5.1 레코드 (`data/items/YYYY/MM/<id>.json`)

```jsonc
{
  "id": "pmid:41234567",            // 우선순위: nct > pmid > doi > url 해시
  "type": "paper",                  // paper | preprint | trial | regulatory | press | news | guideline
  "title": "RMC-6236 in KRAS-mutant PDAC: phase 1/1b results",
  "title_ko": "KRAS 변이 췌장암에서 RMC-6236 1/1b상 결과",   // LLM 또는 비어 있음
  "summary_ko": "...3~5문장 요약, 핵심 수치 포함...",         // LLM 또는 초록 앞부분 발췌
  "abstract": "...",                                        // 원문 초록 (표시는 접힘)
  "published_at": "2026-10-04",
  "source": { "name": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/41234567/", "journal": "Lancet Oncology" },
  "links": { "doi": "10.1016/...", "pmid": "41234567", "nct": ["NCT05379985"], "pdf": null },
  "categories": ["drug", "treatment"],           // 다중 라벨 (7절 참조)
  "subcategories": ["targeted-kras"],
  "tags": ["KRAS", "G12D", "RAS(ON) inhibitor", "2nd-line"],
  "entities": ["daraxonrasib", "NCT05379985"],   // 주제 페이지와 연결
  "evidence": "phase1",                          // phase3 | phase2 | phase1 | preclinical | meta | review | guideline | press | case
  "importance": 0.82,                            // 근거 수준·출처 신뢰도·관련도 가중 합 (첫 화면 노출 기준)
  "first_seen": "2026-10-06",
  "last_updated": "2026-10-06",
  "history": [
    { "date": "2026-10-06", "event": "created", "by": "collector" }
  ],
  "review": { "status": "auto", "note": null }   // auto | verified | flagged | hidden (사람이 override)
}
```

### 5.2 엔티티 레지스트리 (`config/entities.yaml`, 사람이 관리 + 봇이 제안)

약물·시험·수술법처럼 "시간이 지나면서 상태가 바뀌는 대상"을 주제 페이지로 묶기 위한 사전.

```yaml
- id: daraxonrasib
  kind: drug
  names: ["daraxonrasib", "RMC-6236", "다락소나십"]
  target: "RAS(ON) multi-selective"
  developer: "Revolution Medicines"
  status: { phase: "3", fda: "Breakthrough Therapy (2024)", last_checked: "2026-10-06" }
  trials: ["NCT06625320"]
- id: whipple
  kind: procedure
  names: ["Whipple", "pancreaticoduodenectomy", "췌두십이지장절제술", "휘플"]
```

### 5.3 변경 이력 (`history[]`) 이벤트 종류

| 이벤트 | 발생 조건 | 사이트 표시 |
|---|---|---|
| `created` | 첫 수집 | 일일 다이제스트 "신규" |
| `trial_status_changed` | CT.gov `overallStatus` 변경 | "업데이트" 섹션 + 주제 페이지 타임라인 |
| `results_posted` | CT.gov 결과 게시 | 중요도 상향 |
| `preprint_published` | 프리프린트 DOI가 PubMed 논문과 연결됨 | 레코드 `type` 변경, 원 레코드에 링크 |
| `regulatory_update` | FDA/EMA 승인·거부·라벨 변경 | 엔티티 status 갱신 |
| `retracted` / `corrected` | PubMed 철회·정정 공지 | 경고 배지 |
| `citation_updated` | 인용 수 변화 (주 1회) | 주제 페이지 표 |

---

## 6. 수집 파이프라인 (단계별)

```
collector/
  run.py            # 전체 오케스트레이션: python -m collector.run --date 2026-10-06
  sources/          # 소스 어댑터 (각각 fetch(since) -> list[RawItem])
  normalize.py      # RawItem -> Item (공통 스키마, ID 부여)
  store.py          # data/ 읽기·쓰기, 샤딩, 인덱스 재생성
  merge.py          # 기존 레코드와 비교, history 이벤트 생성
  classify.py       # 규칙 기반 분류 + 엔티티 매칭
  enrich.py         # (선택) LLM 요약·번역·분류 보정
  render.py         # data/ -> docs/_generated/*.md, feed.xml, index.json
tests/
```

| 단계 | 입력 → 출력 | 핵심 규칙 |
|---|---|---|
| 1. fetch | 소스별 `since` 날짜 → RawItem[] | `lookback_days`만큼 겹쳐 조회. 실패한 소스는 건너뛰고 나머지 계속 (부분 실패 허용). `data/state.json`에 소스별 마지막 성공 시각 기록 |
| 2. normalize | RawItem → Item | ID 정규화(DOI 소문자, NCT 대문자), 날짜 ISO, URL canonical. 제목 유사도(≥0.92)로 같은 소식의 보도자료/뉴스 묶기 |
| 3. merge | Item + 기존 레코드 → 갱신된 레코드 + history | 필드별 diff. 사람이 수정한 필드(`review`, `summary_ko` 수동본)는 보존. 중요 변경은 history 이벤트로 |
| 4. classify | 레코드 → categories/tags/entities/evidence/importance | `config/taxonomy.yaml` 키워드·MeSH·정규식. 엔티티 별칭 매칭. 점수 산식은 7.3절 |
| 5. enrich (선택) | 레코드 → title_ko, summary_ko, 분류 보정 | API 키 없으면 skip. 구조화 출력(JSON 스키마)으로 받아 검증 |
| 6. render | data/ → Markdown + JSON + RSS | 생성 파일은 `docs/_generated/` 아래에만. 멱등(같은 입력 → 같은 출력)이어야 diff가 깨끗함 |
| 7. commit | 변경된 `data/`, `docs/_generated/` | 커밋 메시지 `chore(data): 2026-10-06 수집 (+23 신규, 5 갱신)`. 변경 없으면 커밋 안 함 |
| 8. build/deploy | `mkdocs build` → `site/` → Pages | 빌드 실패 시 배포하지 않고 이전 사이트 유지 |

---

## 7. 분류 체계

### 7.1 카테고리 (다중 라벨)

| 키 | 이름 | 포함 내용 |
|---|---|---|
| `drug` | 신약·치료제 | 표적치료(KRAS, PARP, NTRK…), 면역치료, 항암화학 신규 병용, ADC, 세포치료·백신 |
| `trial` | 임상시험 | 임상시험 등록·상태·결과. 임상시험 레코드는 항상 이 카테고리를 첫 번째로 가짐. 시험별 페이지에 참여 조건(AI 한국어 정리 + 원문), 국내 기관, 연락처 |
| `surgery` | 수술 | Whipple·원위췌장절제, 복강경·로봇, 신보조요법 후 절제, 수술 합병증·회복(ERAS) |
| `treatment` | 치료 전반 | 표준 항암요법(FOLFIRINOX, NALIRIFOX, GnP), 방사선(SBRT), 치료 가이드라인(NCCN/ESMO/대한암학회) 개정 |
| `diagnosis` | 진단·조기발견 | 바이오마커(CA19-9, KRAS ctDNA), 액체생검, 영상, 고위험군 선별, 낭종 관리 |
| `supportive` | 지지요법·삶의질 | 통증, 영양·췌장효소 보충, 당뇨 관리, 황달·스텐트, 혈전, 정신건강 |
| `industry` | 제약사·규제 소식 | 승인·지정(Breakthrough, Orphan), 라이선스·인수, 임상 결과 보도자료, 급여 |
| `basic` | 기초연구 | 기전·전임상 (기본 접힘, 중요도 낮게) |

### 7.2 근거 수준 (`evidence`) 와 배지

`guideline` > `meta` > `phase3` > `phase2` > `phase1` > `review` > `preclinical` > `press` > `case`. 사이트에서는 색 배지로 표시해 "보도자료"와 "3상 결과"를 한눈에 구분한다.

### 7.3 중요도 점수 (`importance`, 0~1)

```
importance = 0.45·evidence_weight + 0.25·source_trust + 0.20·relevance + 0.10·recency_bonus
```
- `evidence_weight`: guideline/phase3/meta 1.0 … press 0.4, preclinical 0.3
- `source_trust`: 소스 설정값 (NEJM/Lancet 1.0, PubMed 기본 0.8, 와이어 보도자료 0.5)
- `relevance`: 제목·초록에서 췌장암 핵심어 빈도, 1차 질환 여부
- 첫 화면 "오늘의 주요 소식"은 `importance ≥ 0.6`, 나머지는 "전체 목록"에 수록

### 7.4 분류 방식

1. **규칙 기반(기본)**: `config/taxonomy.yaml`에 카테고리별 키워드·MeSH 용어·정규식. 결정적이라 디버깅 쉬움.
2. **LLM 보정(선택)**: 규칙이 `basic`·미분류로 둔 항목만 LLM에 분류 요청. 구조화 출력 스키마로 카테고리·태그·근거수준을 받고, 허용 목록 밖 값은 거부.
3. **사람 override**: `data/overrides/<id>.json`에 수정값을 두면 병합 단계에서 항상 우선. 사이트의 "분류 수정 제안" 링크가 이 파일을 만드는 PR 템플릿으로 연결.

---

## 8. "기존 정보 업데이트" 메커니즘

요구사항 R2의 핵심. 세 층위로 구현한다.

| 층위 | 대상 | 방법 | 주기 |
|---|---|---|---|
| 레코드 갱신 | 임상시험 상태, 승인 상태, 철회 | CT.gov는 `LastUpdatePostDate` 기준으로 변경분을 매일 재조회. PubMed는 `[edat]`(entry date) 외에 기존 PMID 중 최근 90일 레코드를 주 1회 재조회해 정정·철회 확인 | 매일 / 주 1회 |
| 연결 갱신 | 프리프린트→논문, 보도자료→논문, 시험→결과 논문 | DOI/NCT/제목 유사도 매칭. 연결되면 양쪽 레코드에 `related[]` 추가 | 매일 |
| 주제 페이지 갱신 | 약물·시험·수술법의 "현재 상태" | 엔티티별로 관련 레코드를 시간순 정렬해 타임라인 생성. `status`는 가장 최근 `regulatory_update`/`trial_status_changed` 이벤트로 계산 | 매일 (렌더 시) |

주제 페이지 예 (`/topics/daraxonrasib/`):

```
# daraxonrasib (RMC-6236)
현재 상태: 3상 진행 중 (RASolute 302) · FDA Breakthrough Therapy · 최종 확인 2026-10-06
## 타임라인
2026-10-04  [논문·1상]  Lancet Oncol – 1/1b상 결과 ... (출처)
2026-09-20  [시험 갱신] NCT06625320 상태: Recruiting → Active, not recruiting (출처)
2026-08-02  [보도자료]  Revolution Medicines 2Q 실적 발표 중 PDAC 업데이트 (출처)
## 관련 임상시험  (표)
## 관련 논문      (표, 근거 수준·인용 수)
```

---

## 9. 사이트 구조 (MkDocs Material)

```
docs/
├── index.md                     # 오늘의 주요 소식 (자동) + 응급 버튼 + 카테고리 바로가기
├── _generated/                  # 봇 전용 (손대지 않음)
│   ├── daily/2026/10/06.md      # 날짜별 다이제스트: 신규 / 갱신 / 전체 목록
│   ├── categories/drug.md       # 카테고리별 최근 30일 + 월별 아카이브 링크
│   ├── categories/drug/2026-09.md
│   ├── topics/daraxonrasib.md   # 엔티티 주제 페이지
│   ├── explorer.md              # 전체 탐색기 (JS 테이블, data/index.json 로드, 필터·정렬·검색)
│   └── feed.xml                 # RSS (최근 50건)
├── guides/                      # 사람이 작성·검수 (위키 영역)
│   ├── emergency/               # 응급 가이드 (10절)
│   ├── treatment/               # 표준 치료 개요, 용어 설명, 질문 목록
│   ├── surgery/
│   └── glossary.md
├── about/
│   ├── sources.md               # 수집 소스·쿼리·주기 공개 (투명성)
│   ├── disclaimer.md            # 의료 면책
│   ├── contributing.md          # 기여·수정 요청 방법
│   └── changelog.md
└── assets/explorer.js, extra.css
```

탐색 뷰 4가지:

| 뷰 | 구현 | 비고 |
|---|---|---|
| 날짜별 | `_generated/daily/` + Material `blog` 플러그인의 아카이브 | 달력형 내비 |
| 카테고리별 | `_generated/categories/` + `tags` 플러그인 | 카테고리 페이지는 최근 30일만 본문에, 과거는 월별 페이지로 분할해 페이지 크기 제한 |
| 주제별 | `_generated/topics/` | 약물·시험·수술법 |
| 탐색기 | `explorer.md` + `data/index.json`(제목·날짜·카테고리·중요도만, 항목당 ~200B) | 수만 건도 클라이언트에서 필터 가능. 검색 인덱스에는 가이드 + 최근 12개월만 포함해 빌드 크기 관리 |

모바일: Material 테마 기본 반응형. 추가로 PWA 매니페스트를 넣어 홈 화면에 추가 가능하게 함.

---

## 10. 응급 가이드 설계

자동 수집 대상이 아니라 **사람이 쓰고 출처를 달아 검수하는 정적 문서**. 봇은 절대 수정하지 않는다.

구성 원칙:
- 첫 화면과 모든 페이지 상단 바에 빨간 **"응급"** 버튼. 검색어 `응급`, `열`, `황달`, `출혈` 등에 가이드 페이지가 최상단에 오도록 `search.boost` 설정.
- 각 항목은 **증상 → 즉시 할 일 → 119/응급실 가야 하는 기준 → 의료진에게 전달할 정보 → 출처** 순서의 동일한 템플릿.
- 출처는 NCCN 환자용 가이드라인, ASCO/ESMO 환자 정보, 국립암센터, 대한췌장담도학회, 병원 공개 안내문 등 **공식 기관 자료만** 허용.
- 페이지 상단에 "이 정보는 의료 조언이 아니며, 응급 시 119" 고정 면책.

초기 목차(안):

| 파일 | 주제 |
|---|---|
| `emergency/index.md` | 한눈에 보는 응급 판단표 (증상별 → 어디로) |
| `emergency/fever-neutropenia.md` | 항암 중 발열 (발열성 호중구감소증) |
| `emergency/jaundice-cholangitis.md` | 황달 악화·담관염·스텐트 막힘 |
| `emergency/bleeding.md` | 토혈·혈변·흑색변 |
| `emergency/bowel-obstruction.md` | 장폐색·십이지장 폐색 (구토, 복부 팽만) |
| `emergency/pain-crisis.md` | 조절되지 않는 통증, 마약성 진통제 부작용 |
| `emergency/thrombosis.md` | 혈전·폐색전 (다리 부종, 호흡곤란) |
| `emergency/glucose.md` | 혈당 급변 (췌장 절제·당뇨), 저혈당 |
| `emergency/dehydration-diarrhea.md` | 탈수·설사·췌장효소 부족 |
| `emergency/hospital-contacts.md` | 주요 병원 암 응급 콜센터 연락처 (사용자 지역 기준 보완) |

---

## 11. 커뮤니티·협업

| 기능 | 구현 |
|---|---|
| 댓글 | giscus. 리포지토리 Discussions 활성화 → 카테고리 `Comments` 생성 → `mkdocs.yml` overrides에 giscus 스크립트. 페이지 경로를 Discussion 제목으로 매핑 |
| 일일 토론 스레드 | 봇이 매일 다이제스트 페이지에 대응하는 Discussion을 자동 생성(giscus가 첫 댓글 시 만들어도 됨). Discussions를 "구독"하면 매일 알림을 받을 수 있음 |
| 위키 편집 | Material `edit_uri` 설정 → 모든 가이드 페이지에 "GitHub에서 편집" 링크 → PR. `CODEOWNERS`로 가이드 PR은 관리자 리뷰 필수 |
| 수정·누락 제보 | Issue 템플릿 3종: `분류 수정`, `소스 추가 요청`, `내용 오류 제보`. 레코드 페이지 하단에 ID가 채워진 링크 |
| 모더레이션 | Discussions 관리 권한은 리포 관리자. 부적절 댓글은 GitHub에서 삭제 |

---

## 12. 스케줄링·배포 워크플로

### 12.1 `collect.yml` (매일)

```yaml
name: collect
on:
  schedule:
    - cron: "0 21 * * *"      # UTC 21:00 = KST 06:00 (GitHub cron은 수십 분 지연될 수 있음)
  workflow_dispatch:
    inputs:
      since: { description: "재수집 시작일 (YYYY-MM-DD)", required: false }
permissions:
  contents: write
  pages: write
  id-token: write
concurrency: collect          # 중복 실행 방지
jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e .
      - run: python -m collector.run
        env:
          NCBI_API_KEY: ${{ secrets.NCBI_API_KEY }}          # 선택
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }} # 선택
      - run: python -m collector.render
      - name: commit data
        run: |
          git config user.name "papersearcher-bot"
          git config user.email "bot@users.noreply.github.com"
          git add data docs/_generated
          git diff --cached --quiet || git commit -m "chore(data): $(date -u +%F) 수집"
          git push
      - run: mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with: { path: site }
  deploy:
    needs: collect
    runs-on: ubuntu-latest
    environment: github-pages
    steps:
      - uses: actions/deploy-pages@v4
```

### 12.2 `deploy.yml` (사람이 `docs/guides/` 등을 수정해 push할 때)

`push` to `main` with paths `docs/**`, `mkdocs.yml` → 빌드·배포만 수행 (수집 안 함).

### 12.3 운영상 주의점

| 이슈 | 대응 |
|---|---|
| 공개 리포에서 60일간 활동이 없으면 예약 워크플로가 자동 비활성화 | 봇 커밋이 매일 발생해 실질적 위험은 낮으나, `keepalive` 단계(마지막 커밋이 50일 이상 지났으면 빈 변경 커밋)를 추가 |
| cron 지연·누락 | `lookback_days` 겹침 조회로 하루 누락돼도 다음 날 보충. `workflow_dispatch`로 수동 재실행 |
| 소스 API 장애 | 소스별 try/except, 실패 소스는 `state.json`에 기록하고 사이트 `about/status.md`에 표시 |
| 리포 용량 | 레코드 ~2KB × 연 1만 건 ≈ 20MB/년. 초록 전문은 저장하되 5년 이후 아카이브 샤딩 고려 |
| 비밀 키 | 모두 선택 사항. 없으면 기능 축소로 동작 (LLM 요약 skip, PubMed 느린 속도) |

---

## 13. LLM 요약·번역 (선택 기능)

목적: 영어 초록을 환자·보호자가 읽을 수 있는 한국어 3~5문장 요약으로. 분류 보정. **새로운 사실 생성 금지.**

| 항목 | 설계 |
|---|---|
| 백엔드 | `llm.provider: auto` → `GEMINI_API_KEY`가 있으면 Gemini(REST, 무료 등급, 순차 호출 4초 간격), 아니면 Anthropic SDK `claude-opus-5-5`. 두 백엔드 모두 같은 프롬프트·스키마를 사용 |
| 호출 방식 | 항목별 동기 호출, 스레드 4개 병렬. 1회 실행 상한 `llm.max_items_per_run`(기본 120)으로 비용 상한. 넘치는 항목은 다음 실행에서 이어서 처리. (Batches API는 완료까지 최대 24시간이 걸릴 수 있어 Actions 1회 실행 안에서 끝나지 않을 수 있으므로 채택하지 않음) |
| 출력 형식 | 구조화 출력(`output_config.format`)으로 `{title_ko, summary_ko, categories[], evidence, key_numbers[]}` JSON 스키마 강제. 허용 목록 밖 카테고리는 거부 후 규칙 결과 유지 |
| 프롬프트 원칙 | 입력은 제목+초록(+시험 요약)만. "초록에 없는 수치·결론을 쓰지 말 것", "불확실하면 '초록에 명시되지 않음'이라고 쓸 것", 의료 조언 금지 |
| 비용 추정 | 입력 ~1,500토큰 + 출력 ~400토큰/건 × 40건/일 ≈ 월 2.3M 입력·0.5M 출력 토큰. Opus 5.5 배치 단가 기준 월 약 $10 이하. 프롬프트 캐싱(시스템 프롬프트 고정)으로 추가 절감 |
| 안전장치 | `stop_reason == "refusal"` 처리, 응답 JSON 검증 실패 시 초록 발췌로 폴백. 요약 아래 항상 "AI 요약 · 원문 확인" 배지 |
| 미사용 시 | `summary_ko`는 초록 첫 2문장 발췌, `title_ko`는 비움. 사이트는 정상 동작 |

---

## 14. 리포지토리 구조 (최종)

```
papersearcher/
├── .github/
│   ├── workflows/collect.yml, deploy.yml, test.yml
│   ├── ISSUE_TEMPLATE/ (분류수정 / 소스추가 / 오류제보)
│   └── CODEOWNERS
├── collector/            # Python 패키지 (6절)
├── config/
│   ├── sources.yaml      # 소스·쿼리·신뢰도
│   ├── taxonomy.yaml     # 카테고리·키워드·근거수준 규칙
│   └── entities.yaml     # 약물·시험·수술법 사전
├── data/
│   ├── items/YYYY/MM/*.json
│   ├── index.json        # 탐색기용 경량 인덱스 (렌더 시 재생성)
│   ├── overrides/        # 사람 수정값
│   └── state.json        # 소스별 마지막 성공 시각, 실패 기록
├── docs/                 # 9절
├── overrides/            # MkDocs 테마 커스터마이징 (giscus, 응급 버튼)
├── mkdocs.yml
├── pyproject.toml
├── tests/                # 소스 어댑터 고정 응답(fixture) 기반 단위 테스트
└── README.md
```

---

## 15. 품질·법적·운영 리스크

| 리스크 | 대응 |
|---|---|
| 의료 정보 오해 | 모든 페이지 면책 고지. 요약에 "AI 생성" 배지. 응급 가이드는 공식 기관 출처만 |
| 저작권 | 초록은 PubMed 공개 메타데이터이나 전문 재게시는 피함. 보도자료·뉴스는 제목+2문장 발췌+링크만 저장. `about/sources.md`에 정책 명시 |
| 노이즈 (무관 논문) | `relevance` 점수 하한(0.3) 미만 제외. `basic` 카테고리는 기본 접힘. 사람 override |
| 중복 (같은 결과의 보도자료·뉴스·논문) | 제목 유사도 + NCT/DOI 공유로 `related[]` 묶음. 다이제스트에는 대표 1건만 노출 |
| 비용 | GitHub Actions·Pages·giscus 모두 무료. LLM만 선택적 유료 |
| 언어 | 1차: 수집 영어, 표시 한국어(요약) + 영어 원제. 영어 UI 토글은 Phase 3 |

---

## 16. 구현 로드맵

| 단계 | 내용 | 산출물 | 예상 작업량 |
|---|---|---|---|
| **Phase 0** 뼈대 ✅ | 리포 구조, MkDocs Material 사이트, Pages 워크플로, giscus 연동 코드, 면책·소스·후원 페이지, 응급 가이드 9종 초안, 임상시험 참여 안내·용어집 | 완료 | — |
| **Phase 1** 수집 MVP ✅ | PubMed + ClinicalTrials.gov + Europe PMC 어댑터, 공통 스키마, 규칙 분류, 병합·변경 이력, Claude 한국어 요약·참여 조건 정리, 일일·카테고리·임상시험·주제 페이지, RSS, `collect.yml` cron, 테스트 | 완료 (첫 수집 426건 포함) | — |
| **Phase 2** 갱신·주제 | merge/history, 엔티티 사전·주제 페이지, FDA·RSS 소스, 탐색기(JSON 테이블), RSS 피드, 중복 묶기 | "기존 정보 업데이트"가 보임 | 2~3일 |
| **Phase 3** 요약·품질 | Claude 배치 요약·번역, 중요도 점수 튜닝, override 워크플로, Issue 템플릿, 테스트·모니터링 페이지 | 한국어 요약이 달린 완성형 | 2일 |
| **Phase 4** 확장 | 국내 소스, 학회 시즌 대응, PWA, 영어 UI, 알림(Telegram/메일) | 선택 | 지속 |

---

## 17. 결정이 필요한 사항

구현 전에 확인하면 좋은 선택지. 답이 없으면 괄호 안 기본값으로 진행한다.

1. **LLM 한국어 요약 사용 여부** — Anthropic API 키를 Secrets에 넣을 것인지. (기본: 키 없이 Phase 1~2 먼저, Phase 3에서 추가)
2. **리포지토리 공개 여부** — 무료 Actions·Pages·Discussions를 위해 공개 필요. (기본: 공개)
3. **사이트 주소** — `hizorro88-rgb.github.io/papersearcher` 또는 보유 도메인. (기본: github.io)
4. **국내 소스 우선순위** — 식약처·국립암센터·국내 언론을 Phase 2에 포함할지. (기본: Phase 4)
5. **응급 가이드 초안 작성 주체** — 설계대로 사람이 공식 출처를 보고 작성할지, 초안을 AI가 출처 링크와 함께 작성하고 검수할지. (기본: 템플릿+목차만 만들고 내용은 검수 후 채움)
6. **댓글 방식** — giscus(GitHub 계정 필요) 유지 여부. (기본: giscus)
