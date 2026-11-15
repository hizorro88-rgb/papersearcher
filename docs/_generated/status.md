---
title: "수집 현황"
description: "소스별 상태와 실행 기록"
comments: false
search:
  boost: 0.4
---

# 수집 현황

## 소스 상태

| 소스 | 마지막 실행 | 결과 | 건수 |
|---|---|---|---|
| pubmed | 2026-11-15T00:31:54+00:00 | 정상 | 64 |
| clinicaltrials | 2026-11-15T00:31:55+00:00 | 정상 | 39 |
| europepmc | 2026-11-15T00:31:55+00:00 | 실패: HTTPStatusError: Server error '500 Internal Server Error' for url 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=%28%28TITLE%3A%22pancreatic+cancer%22+OR+TITLE%3A%22pancreatic+adenocarcinoma%22+OR+TITLE%3APDAC+OR+TITLE%3A%22pancreatic+ductal%22%29+AND+%28SRC%3APPR%29%29+AND+%28FIRST_PDATE%3A%5B2026-11-12+TO+2026-11-15%5D%29&format=json&resultType=core&pageSize=100&sort=P_PDATE_D+desc' For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 | 0 |

## 최근 실행

| 날짜 | 신규 | 갱신 | 누적 | LLM | 성공/실패 | 토큰(입력/출력) |
|---|---|---|---|---|---|---|
| 2026-11-15 | 22 | 0 | 1242 | gemini-3.5-flash-lite | 49/14 | 124184/36706 |
| 2026-11-14 | 23 | 0 | 1220 | gemini-3.5-flash-lite | 45/12 | 107322/32327 |
| 2026-11-13 | 31 | 2 | 1197 | gemini-3.5-flash-lite | 52/9 | 118566/38338 |
| 2026-11-12 | 14 | 0 | 1166 | gemini-3.5-flash-lite | 38/5 | 82203/26795 |
| 2026-11-11 | 29 | 2 | 1152 | gemini-3.5-flash-lite | 41/11 | 83336/27296 |
| 2026-11-10 | 16 | 1 | 1123 | gemini-3.6-flash | 12/14 | 26964/7597 |
| 2026-11-09 | 29 | 0 | 1107 | gemini-3.6-flash | 47/6 | 87892/29618 |
| 2026-11-08 | 3 | 0 | 1078 | gemini-3.6-flash | 31/9 | 76281/25144 |
| 2026-11-07 | 24 | 4 | 1075 | gemini-3.5-flash-lite | 56/10 | 127755/42441 |
| 2026-11-06 | 26 | 3 | 1051 | gemini-3.5-flash-lite | 62/2 | 138937/44298 |
| 2026-11-05 | 21 | 3 | 1025 | gemini-3.5-flash-lite | 51/1 | 118492/39409 |
| 2026-11-04 | 22 | 2 | 1004 | gemini-3.5-flash-lite | 38/0 | 82735/27537 |
| 2026-11-03 | 16 | 0 | 982 | gemini-3.6-flash | 20/3 | 43441/13308 |
| 2026-11-02 | 11 | 0 | 966 | gemini-3.6-flash | 23/3 | 46032/15761 |
| 2026-10-31 | 6 | 0 | 955 | gemini-3.8-flash | 37/5 | 87536/30915 |
| 2026-10-31 | 28 | 4 | 949 | gemini-3.5-flash-lite | 56/3 | 120600/38787 |
| 2026-10-30 | 22 | 1 | 921 | gemini-3.5-flash-lite | 48/5 | 105579/34462 |
| 2026-10-29 | 26 | 1 | 899 | gemini-3.5-flash-lite | 45/6 | 96997/33584 |
| 2026-10-28 | 63 | 0 | 873 | gemini-3.5-flash-lite | 79/0 | 149033/49531 |
| 2026-10-27 | 17 | 0 | 810 | gemini-3.6-flash | 12/10 | 27099/7248 |
| 2026-10-25 | 21 | 0 | 793 | gemini-3.5-flash-lite | 46/0 | 97590/32136 |
| 2026-10-24 | 25 | 0 | 772 | gemini-3.5-flash-lite | 57/0 | 118551/40681 |
| 2026-10-23 | 24 | 0 | 747 | gemini-3.5-flash-lite | 58/7 | 132578/43685 |
| 2026-10-22 | 10 | 0 | 723 | gemini-3.5-flash-lite | 45/2 | 109142/36570 |
| 2026-10-21 | 9 | 1 | 713 | gemini-3.5-flash-lite | 39/0 | 90475/31400 |
| 2026-10-20 | 31 | 1 | 704 | gemini-3.5-flash-lite | 46/0 | 99222/34248 |
| 2026-10-20 | 11 | 0 | 673 | gemini-3.8-flash | 14/0 | 29131/10921 |
| 2026-10-18 | 11 | 0 | 662 | gemini-3.8-flash | 38/0 | 86682/31463 |
| 2026-10-17 | 11 | 0 | 651 | gemini-3.5-flash-lite | 51/0 | 116352/41669 |
| 2026-10-16 | 39 | 1 | 640 | gemini-3.5-flash-lite | 99/0 | 213608/75347 |

요약 상태: AI 1228 · 발췌 14 · 수동 0 · 대기 0
