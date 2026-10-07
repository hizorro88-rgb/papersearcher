# 운영자 설정 안내 (개발 완료 후 직접 해야 할 일)

코드와 데이터는 모두 준비되어 있습니다. 아래 항목은 GitHub 계정 권한이 필요해 운영자가 직접 해야 합니다. 순서대로 진행하면 30분 안에 끝납니다.

## 1. 브랜치를 main으로 합치기 (필수)

개발 브랜치 `claude/focused-cannon-dzsc9u`의 내용을 기본 브랜치 `main`으로 옮깁니다. 워크플로가 `main`을 기준으로 돌기 때문입니다.

- GitHub 저장소 → **Pull requests** → **New pull request** → base: `main`, compare: `claude/focused-cannon-dzsc9u` → **Create pull request** → **Merge**.
- 저장소에 아직 `main`이 없다면: **Settings → General → Default branch**에서 `claude/focused-cannon-dzsc9u`를 기본으로 지정한 뒤 이름을 `main`으로 바꿔도 됩니다 (Branches 메뉴에서 연필 아이콘).

## 2. 저장소 공개 전환 (필수)

GitHub Actions 무제한 무료, GitHub Pages, Discussions는 **공개 저장소**에서만 무료입니다.

- **Settings → General → Danger Zone → Change repository visibility → Public**

## 3. GitHub Pages 켜기 (필수)

- **Settings → Pages → Build and deployment → Source: GitHub Actions** 선택 (branch 방식이 아님).
- 저장 후 사이트 주소는 `https://hizorro88-rgb.github.io/papersearcher/` 입니다.

## 4. 한국어 요약용 LLM API 키 등록 (필수, 무료 가능)

한국어 번역·요약은 LLM API가 필요합니다. **Google Gemini API 무료 등급**으로 비용 없이 운영할 수 있고, 품질을 더 높이고 싶을 때만 Claude API(유료)로 바꾸면 됩니다. 둘 다 등록하면 Gemini를 우선 사용합니다.

### 4-A. Google Gemini (무료, 권장)

1. https://aistudio.google.com/apikey 접속 → Google 계정 로그인 → **API 키 만들기** (신용카드 불필요).
2. GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `GEMINI_API_KEY`
   - Secret: 복사한 키
3. 끝. 다음 수집부터 `gemini-3.8-flash`로 요약합니다.

알아 둘 점:
- 무료 등급은 분당·일일 요청 한도가 있습니다(모델에 따라 분당 5~15회, 하루 수백~1,500회). 수집기는 요청 간 4초 간격으로 순차 호출하고 하루 최대 120건만 요약하므로 한도 안에서 동작합니다. 한도에 걸린 항목은 다음 날 자동 재시도됩니다.
- Google은 무료 등급의 입력 내용을 제품 개선에 사용할 수 있습니다. 이 프로젝트가 보내는 것은 공개 논문 초록과 임상시험 등록 정보뿐이므로 문제되지 않습니다.
- 무료 등급은 시간대에 따라 과부하(503)가 잦습니다. 수집기는 `gemini-3.8-flash` → 3.7 → 3.6 → 3.5-lite 순으로 자동 전환합니다. 모델 순서는 `config/sources.yaml`의 `llm.gemini_models`에서 바꿀 수 있습니다(무료 제공 모델 목록은 https://ai.google.dev/gemini-api/docs/pricing 에서 확인). 구형 모델(2.5 등)은 신규 계정에서 404가 납니다.

### 4-B. Anthropic Claude (유료, 선택)

품질이 더 중요해지면 전환합니다. Claude Code 구독(Pro/Max)은 API 호출을 포함하지 않으므로 별도 종량제 키가 필요합니다.

1. https://platform.claude.com 에서 로그인 → **API Keys → Create Key** → 키 복사 (`sk-ant-...`).
2. 크레딧 충전 및 **월 사용 한도(Spend limit)** 설정 권장: 처음에는 월 $20 정도.
3. GitHub Secrets에 `ANTHROPIC_API_KEY`로 등록하고, `config/sources.yaml`의 `llm.provider`를 `anthropic`으로 바꿉니다.

예상 비용: 하루 30~80건 요약 기준 월 $5~15. 사용량은 사이트의 **소개 → 수집 현황** 페이지에서 확인할 수 있습니다.

## 5. (선택) NCBI API 키

PubMed 조회 속도 제한을 초당 3회에서 10회로 올립니다. 없어도 동작합니다.

- https://www.ncbi.nlm.nih.gov/account/ 로그인 → **Settings → API Key Management → Create an API Key**
- GitHub Secrets에 `NCBI_API_KEY` 이름으로 등록

## 6. 첫 수집 실행과 확인 (필수)

1. 저장소 → **Actions** 탭 → 왼쪽에서 **collect** → **Run workflow** → `Run workflow` 클릭.
2. 5~15분 뒤 완료되면 `main`에 `chore(data): ... 수집` 커밋이 생기고 사이트가 배포됩니다.
3. 사이트에서 홈·임상시험 목록·날짜별 페이지가 보이는지 확인합니다.
4. 이후에는 매일 06:00 KST에 자동 실행됩니다 (GitHub 사정으로 최대 1시간가량 늦어질 수 있음).

문제가 있으면 Actions 실행 로그의 "Collect, summarize, render" 단계를 보면 원인이 나옵니다.

## 7. 댓글 기능 켜기 (giscus) (권장)

1. 저장소 → **Settings → General → Features → Discussions** 체크.
2. 저장소 **Discussions** 탭 → 카테고리 옆 연필 → **New category** → 이름 `Comments`, 형식 **Announcement** (아무나 댓글은 달 수 있지만 새 글은 봇/giscus만 만들도록) → 저장.
3. https://github.com/apps/giscus 에서 **Install** → 이 저장소 선택.
4. https://giscus.app/ko 접속 → 저장소 `hizorro88-rgb/papersearcher` 입력 → Discussion 카테고리 `Comments` 선택 → 아래 생성된 스크립트에서 `data-repo-id`와 `data-category-id` 값을 복사.
5. `mkdocs.yml`의 `extra.giscus.repo_id`, `extra.giscus.category_id`에 붙여 넣고 커밋 (GitHub 웹에서 파일을 열어 연필 아이콘으로 편집 가능).
6. 커밋하면 deploy 워크플로가 돌아 모든 페이지 하단에 댓글창이 생깁니다.

## 8. 후원 받기 (선택)

### GitHub Sponsors (수수료 0%)
1. https://github.com/sponsors 에서 **Join the waitlist / Get sponsored** → 계정 심사 (한국 거주자 가능, Stripe 연결 필요, 보통 며칠 소요).
2. 승인되면 티어(예: 월 $3, $5, $10)를 만들고 공개.
3. 저장소에 이미 `.github/FUNDING.yml`이 있어 승인 즉시 저장소 상단에 **Sponsor** 버튼이 나타납니다.

### 그 밖의 방법
- Buy Me a Coffee(https://buymeacoffee.com), 토스 익명 송금 링크, 카카오페이 송금 링크 등을 만든 뒤:
  - `.github/FUNDING.yml`의 `custom:` 줄에 주소 추가
  - `docs/about/sponsor.md`의 "후원 방법" 목록에 주소 추가
- 후원금 사용 내역은 `docs/about/sponsor.md`에 적어 투명하게 공개하는 것을 권장합니다.

## 9. 응급 가이드·병원 연락처 검수 (권장)

`docs/guides/emergency/` 아래 9개 페이지는 공식 기관 자료를 근거로 작성한 **초안**입니다. 가능하면 의료인에게 검토를 받고, `hospital-contacts.md`에 자주 가는 병원의 실제 연락처를 채워 주세요. GitHub 웹에서 파일을 열고 연필 아이콘으로 바로 편집할 수 있습니다.

## 10. 이후 운영에서 알아 둘 것

| 상황 | 방법 |
|---|---|
| 특정 날짜부터 다시 수집하고 싶다 | Actions → collect → Run workflow → `since`에 날짜 입력 |
| LLM 없이 테스트 실행 | Run workflow → `no_llm`에 `true` |
| 잘못 분류된 항목 고치기 | `data/overrides/<id>.json` 파일 생성. 예: `{"id": "pmid:41234567", "categories": ["surgery"], "review": {"status": "verified"}}` |
| 무관한 항목 숨기기 | 위 파일에 `"review": {"status": "hidden"}` |
| 새 약물 주제 페이지 추가 | `config/entities.yaml`에 항목 추가 후 커밋 |
| 검색식·키워드 조정 | `config/sources.yaml`, `config/taxonomy.yaml` 수정 후 커밋 → 다음 수집부터 반영. 기존 항목에도 적용하려면 로컬에서 `python -m collector.run --reclassify` 후 커밋 |
| 요약 건수·비용 줄이기 | `config/sources.yaml`의 `llm.max_items_per_run`을 낮추기 |
| Gemini 한도 초과(429)가 자주 보일 때 | `llm.gemini_min_interval_seconds`를 6~10으로 올리거나 `max_items_per_run`을 낮추기 |
| 60일 이상 수집이 멈춘 경우 | GitHub가 비활성 저장소의 예약 실행을 끕니다. Actions 탭에서 collect 워크플로를 **Enable** 하면 재개됩니다 (매일 봇 커밋이 생기므로 평소에는 발생하지 않음) |
