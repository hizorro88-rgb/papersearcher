---
search:
  boost: 3
title: 관심 주제로 필터
description: 젬아, 폐 전이 수술, KRAS 억제제처럼 보고 싶은 주제만 골라 수집된 연구·임상시험을 봅니다
comments: true
---

# 관심 주제로 필터

수집된 모든 논문·소식·임상시험을 **내가 관심 있는 주제만** 골라서 봅니다. 주제를 여러 개 고르면 **모두 해당하는** 항목만 남습니다 (예: "젬아" + "폐 전이" = 젬아를 쓴 폐 전이 연구). 검색창에 직접 쳐도 됩니다 ("젬아", "폐전이 수술"처럼 띄어 쓰면 두 조건을 모두 만족하는 것만).

!!! tip "저장해 두면 다음에 바로"
    "내 관심 주제로 저장"을 누르면 이 브라우저에 저장되어 다음에 이 페이지를 열 때 자동으로 적용되고, **마지막으로 본 뒤 새로 들어온 항목**이 표시됩니다. 주소창의 링크를 즐겨찾기에 넣어도 같은 필터가 열립니다. 저장 내용은 브라우저 밖으로 나가지 않습니다.

<div id="rf" class="rf">
  <div class="rf-row">
    <input id="rf-q" type="search" placeholder="직접 검색: 예) 젬아, 폐전이 수술, daraxonrasib, 신경병증" autocomplete="off">
  </div>
  <div id="rf-topics" class="rf-topics"></div>
  <div class="rf-row rf-opts">
    <label><input type="checkbox" id="rf-paper" checked> 논문·소식</label>
    <label><input type="checkbox" id="rf-trial" checked> 임상시험</label>
    <label><input type="checkbox" id="rf-kr"> 국내 기관 있는 임상만</label>
    <label>기간
      <select id="rf-days">
        <option value="0">전체</option>
        <option value="30">최근 30일</option>
        <option value="90">최근 90일</option>
        <option value="365">최근 1년</option>
      </select>
    </label>
    <label>정렬
      <select id="rf-sort">
        <option value="date">최신순</option>
        <option value="imp">중요도순</option>
      </select>
    </label>
  </div>
  <div class="rf-row rf-actions">
    <button type="button" id="rf-save" class="md-button md-button--primary">내 관심 주제로 저장</button>
    <button type="button" id="rf-clear" class="md-button">모두 지우기</button>
    <span id="rf-saved-msg" class="rf-hint"></span>
  </div>
  <p id="rf-count" class="rf-count"></p>
  <div id="rf-results"></div>
  <p class="rf-row"><button type="button" id="rf-more" class="md-button" hidden>더 보기</button></p>
</div>

## 이렇게 써 보세요

- **젬아 치료 중이라면**: "젬아 (젬시타빈+아브락산)"과 "부작용"을 함께 고르면 젬아의 부작용 관리 연구만 남습니다. "생존 기간 보고"를 더하면 효과를 숫자로 보고한 것만.
- **폐 전이가 있다면**: "폐 전이" + "전이 절제술·소수전이"로 폐 전이 수술 관련 연구를, "폐 전이" + "임상시험"만 켜서 참여할 만한 시험을 봅니다.
- **유전자 결과가 KRAS 변이라면**: "KRAS 억제제" 하나만 골라 저장해 두고 매일 새 소식을 확인합니다.
- 주제 사전에 없는 말(약 이름, 병원 이름 등)은 검색창에 그대로 치면 제목·요약·중재명에서 찾습니다.

## 한계

- 주제 분류는 제목·요약·중재명에 나온 단어로 자동 판별하므로 빠지거나 잘못 들어가는 항목이 있을 수 있습니다. 요약이 아직 없는 항목은 영어 제목으로만 걸립니다.
- 이 사이트가 수집한 범위 안에서만 찾습니다. [모든 연구를 포함하지 않습니다](../_generated/daily/index.md).
- 주제를 추가하고 싶으면 [수정 요청](../about/contributing.md)으로 알려 주세요. 사전은 `config/topics.yaml` 한 파일입니다.
