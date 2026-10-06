# PaperSearcher — 췌장암 정보 위키

췌장암 **신약·임상시험·수술·치료** 관련 논문, 임상시험 등록 정보, 프리프린트를 매일 자동 수집해 한국어로 요약하고 GitHub Pages 위키로 게시합니다. 모든 항목에 출처가 붙고, 임상시험 상태처럼 바뀌는 정보는 변경 이력과 함께 갱신됩니다.

- 사이트: https://hizorro88-rgb.github.io/papersearcher/ (Pages 설정 후 활성화)
- 설계: [docs/DESIGN.md](docs/DESIGN.md) · 운영자 설정: [docs/SETUP.md](docs/SETUP.md)
- 실행: GitHub Actions (매일 06:00 KST) → `data/` 커밋 → MkDocs 빌드 → GitHub Pages
- 비용: 호스팅 0원. 한국어 요약(Claude API)만 월 $5~15, [후원](docs/about/sponsor.md)으로 충당

## 구조

```
collector/        수집·병합·분류·요약·렌더 (Python)
config/           검색식, 분류 규칙, 약물 사전
data/items/       수집 레코드 (JSON, git이 DB)
docs/             사이트 원고 (가이드는 사람이, _generated/는 봇이 작성)
.github/workflows collect(매일) · deploy(문서 수정 시) · test(PR)
```

## 로컬 실행

```bash
pip install -r requirements.txt
pytest
ANTHROPIC_API_KEY=sk-ant-... python -m collector.run      # 수집 + 요약 + 렌더
python -m collector.run --no-llm                           # 요약 없이
mkdocs serve                                               # http://127.0.0.1:8000
```

> 이 사이트의 정보는 의료 조언이 아닙니다. 응급 상황에서는 119 또는 가까운 응급실로 연락하세요.
