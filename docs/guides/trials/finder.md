---
search:
  boost: 4
title: 맞춤 임상시험 찾기
description: 진단 상태, 받은 항암제, 유전자 검사 결과를 고르면 조건에 맞는 췌장암 임상시험을 골라 줍니다
comments: true
---

# 맞춤 임상시험 찾기

!!! info "입력 내용은 이 브라우저 안에서만 처리됩니다"
    고른 내용은 어디에도 전송되거나 저장되지 않습니다. 페이지를 닫으면 사라집니다.

!!! warning "결과는 '후보'입니다"
    ClinicalTrials.gov에 등록된 선정·제외 기준을 규칙과 AI로 자동 정리해 대조한 것입니다. 혈액 수치, 장기 기능, 동반 질환 등 여기서 묻지 않는 조건이 많고, 실제 참여 가능 여부는 **담당 의료진과 해당 병원 임상시험센터**가 판단합니다. 결과를 가지고 주치의와 상의하세요. [참여 방법 안내](how-to-apply.md)

<form id="trial-finder" class="tf-form" onsubmit="return false;">

<details class="tf-paste">
<summary>진료 의뢰서·치료 요약을 붙여넣어 자동으로 채우기 (선택)</summary>
<p>병원에서 받은 소견서나 치료 요약(영어·한국어 혼용 가능)을 붙여넣고 버튼을 누르면 아래 항목을 자동으로 체크합니다. 붙여넣은 글도 브라우저 밖으로 나가지 않습니다.</p>
<textarea id="tf-paste" rows="6" placeholder="예: pancreatic tail cancer with liver metastasis 진단, FOLFIRINOX 후 distal pancreatectomy, 재발 후 gemcitabine/abraxane … KRAS G12R, TP53"></textarea>
<p><button type="button" id="tf-parse" class="md-button md-button--primary">자동으로 채우기</button> <span id="tf-parse-msg" class="tf-hint"></span></p>
</details>

<fieldset>
<legend>0. 암 종류</legend>
<label><input type="radio" name="histology" value="pdac" checked> 췌장선암(췌관선암, PDAC): 췌장암의 대부분</label>
<label><input type="radio" name="histology" value="net"> 췌장 신경내분비종양(pNET)</label>
<label><input type="radio" name="histology" value="unknown"> 모름</label>
</fieldset>

<fieldset>
<legend>1. 현재 상태</legend>
<label><input type="radio" name="setting" value="metastatic"> 전이성(4기): 다른 장기에 전이가 있음</label>
<label><input type="radio" name="setting" value="recurrent"> 수술 후 재발·전이</label>
<label><input type="radio" name="setting" value="locally_advanced"> 국소진행: 전이는 없지만 수술이 어려움</label>
<label><input type="radio" name="setting" value="resectable"> 수술 가능·경계성: 수술 전 단계</label>
<label><input type="radio" name="setting" value="adjuvant"> 수술 후 보조치료 단계 (재발 없음)</label>
</fieldset>

<fieldset>
<legend>2. 전이·재발·국소진행 상태에서 받은 항암 요법 수</legend>
<p class="tf-hint">수술 전후 보조항암은 보통 세지 않습니다(수술 후 6개월 이내 재발이면 1가지로 봅니다). 약을 바꿔서 받은 횟수를 세세요.</p>
<label><input type="radio" name="lines" value="0"> 0 (아직 항암을 안 받음)</label>
<label><input type="radio" name="lines" value="1"> 1가지</label>
<label><input type="radio" name="lines" value="2"> 2가지</label>
<label><input type="radio" name="lines" value="3"> 3가지 이상</label>
<label><input type="radio" name="lines" value="unknown"> 모름</label>
</fieldset>

<fieldset>
<legend>3. 지금까지 받은 치료 (모두 체크)</legend>
<label><input type="checkbox" name="regimen" value="folfirinox"> FOLFIRINOX (폴피리녹스)</label>
<label><input type="checkbox" name="regimen" value="gem_abx"> 젬시타빈 + 아브락산 (젬아)</label>
<label><input type="checkbox" name="regimen" value="gem"> 젬시타빈 단독</label>
<label><input type="checkbox" name="regimen" value="naliri"> 오니바이드(nal-IRI) + 5-FU</label>
<label><input type="checkbox" name="regimen" value="folfox"> FOLFOX / 옥살리플라틴 + 5-FU</label>
<label><input type="checkbox" name="regimen" value="capecitabine"> 카페시타빈(젤로다) 또는 S-1</label>
<label><input type="checkbox" name="regimen" value="io"> 면역항암제 (키트루다, 옵디보 등)</label>
<label><input type="checkbox" name="regimen" value="kras"> KRAS 억제제 (임상시험 약 포함)</label>
<label><input type="checkbox" name="regimen" value="rt"> 방사선치료</label>
</fieldset>

<fieldset>
<legend>4. 유전자·표지자 검사 결과 (아는 것만 체크)</legend>
<p class="tf-hint">조직 NGS 검사 결과지, 또는 주치의에게 물어보세요. 모르면 비워 두어도 됩니다.</p>
<label><input type="checkbox" name="biomarker" value="KRAS_G12C"> KRAS G12C</label>
<label><input type="checkbox" name="biomarker" value="KRAS_G12D"> KRAS G12D</label>
<label><input type="checkbox" name="biomarker" value="KRAS_G12V"> KRAS G12V</label>
<label><input type="checkbox" name="biomarker" value="KRAS_G12R"> KRAS G12R</label>
<label><input type="checkbox" name="biomarker" value="KRAS_other"> 기타 KRAS 변이 (G13, Q61 등)</label>
<label><input type="checkbox" name="biomarker" value="KRAS_wild"> KRAS 정상 (wild-type)</label>
<label><input type="checkbox" name="biomarker" value="BRCA_PALB2"> BRCA1/2 또는 PALB2 변이</label>
<label><input type="checkbox" name="biomarker" value="MSI_H"> MSI-H / dMMR</label>
<label><input type="checkbox" name="biomarker" value="HER2"> HER2 양성</label>
<label><input type="checkbox" name="biomarker" value="CLDN18_2"> CLDN18.2 양성</label>
<label><input type="checkbox" name="biomarker" value="NTRK"> NTRK 융합</label>
<label><input type="checkbox" name="biomarker" value="NRG1"> NRG1 융합</label>
<label><input type="checkbox" name="biomarker" value="tested_neg"> 유전자 검사를 했고, 위 표적(BRCA·MSI·HER2 등)은 없었음</label>
</fieldset>

<fieldset>
<legend>5. 활동 상태 (ECOG)</legend>
<label><input type="radio" name="ecog" value="0"> 0: 아프기 전과 같이 활동</label>
<label><input type="radio" name="ecog" value="1"> 1: 힘든 일은 못 하지만 가벼운 집안일·사무는 가능</label>
<label><input type="radio" name="ecog" value="2"> 2: 자기 돌봄은 되지만 일은 못 함, 낮의 절반 이상은 활동</label>
<label><input type="radio" name="ecog" value="3"> 3: 낮의 절반 이상 누워 지냄</label>
<label><input type="radio" name="ecog" value="unknown"> 모름</label>
</fieldset>

<fieldset>
<legend>6. 보기 조건</legend>
<label><input type="checkbox" id="f-kr" checked> 국내 실시기관이 있는 시험만</label>
<label><input type="checkbox" id="f-rec" checked> 모집 중인 시험만</label>
</fieldset>

<p><button type="button" id="tf-copy" class="md-button md-button--primary" disabled>주치의용 요약 복사</button> <button type="button" id="tf-reset" class="md-button">모두 지우기</button></p>

</form>

<div id="tf-results" class="tf-results"></div>

## 결과를 읽는 법

- **가능성 있는 시험**: 입력한 조건(질병 상태, 치료 단계, 받은 치료, 유전자, ECOG)과 어긋나는 것이 없는 시험입니다. 여기 있어도 혈액 수치 등 다른 기준으로 참여가 안 될 수 있습니다.
- **확인 필요**: 시험 쪽 조건이 자동 추출이라 확실하지 않거나, 환자 쪽 정보(유전자 검사 등)가 비어 있어 판단할 수 없는 시험입니다. 항목을 더 채우면 줄어듭니다.
- **맞지 않는 시험**: 1차 치료 전용인데 이미 항암을 받았거나, 다른 KRAS 아형이 필요한 경우처럼 분명히 어긋나는 시험입니다. 접혀 있지만 펼쳐 볼 수 있습니다.
- "주치의용 요약 복사"를 누르면 입력 내용과 후보 시험 목록이 글로 복사됩니다. 진료 때 보여 주거나 임상시험센터에 문의할 때 쓰세요.

국내 기관이 없는 시험까지 보려면 6번에서 체크를 풀면 됩니다. 해외 시험은 참여가 현실적으로 어렵지만, 같은 약의 국내 시험이 뒤따라 열리는 경우가 있어 참고가 됩니다.

## 이 도구의 한계

- ClinicalTrials.gov에 등록된 시험만 다룹니다. 국내 식약처·CRIS에만 등록된 시험은 빠질 수 있습니다. [참여 방법 안내](how-to-apply.md)의 다른 경로도 함께 보세요.
- 조건은 매일 자동으로 다시 뽑지만, 등록 정보 자체가 늦게 갱신되기도 합니다. 각 시험의 "최근 갱신" 날짜를 확인하세요.
- 여러 암종을 함께 모집하는 시험은 췌장암 코호트 조건만 뽑으려 했지만 섞일 수 있습니다.
- 용어가 낯설면 [용어사전](../glossary.md)에서 찾아보세요.
