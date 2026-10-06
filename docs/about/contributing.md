---
title: 기여·수정 요청
comments: true
---

# 기여하고 수정 요청하는 방법

모든 기여는 GitHub 계정이 필요합니다 (무료).

| 하고 싶은 것 | 방법 |
|---|---|
| 특정 항목의 분류·요약이 틀렸다 | 항목 아래 **[수정 제안]** 링크 → 이슈 작성 |
| 가이드 페이지 내용을 고치고 싶다 | 페이지 상단 연필 아이콘 → GitHub에서 편집 → Pull Request. 관리자가 검토 후 반영 |
| 새 수집 소스(저널, 제약사 RSS 등)를 추가하고 싶다 | [소스 추가 요청 이슈](https://github.com/hizorro88-rgb/papersearcher/issues/new?template=source-request.yml) |
| 새 약물·요법을 주제 페이지로 만들고 싶다 | `config/entities.yaml`에 항목 추가 PR |
| 의견·질문 | 각 페이지 하단 댓글 또는 [Discussions](https://github.com/hizorro88-rgb/papersearcher/discussions) |

## 개발자용

```bash
git clone https://github.com/hizorro88-rgb/papersearcher
cd papersearcher
pip install -r requirements.txt
pytest                               # 단위 테스트
python -m collector.run --no-llm     # 수집 (LLM 없이)
mkdocs serve                         # http://127.0.0.1:8000
```

구조와 설계는 [DESIGN.md](https://github.com/hizorro88-rgb/papersearcher/blob/main/docs/DESIGN.md)를 참고하세요.
