/* 맞춤 임상시험 찾기: 모든 처리는 브라우저 안에서만 이루어진다. 입력은 어디에도 전송·저장하지 않는다. */
(function () {
  var SETTING_KO = { metastatic: "전이성(4기)·재발", locally_advanced: "국소진행(수술 불가)", resectable: "수술 가능·경계성", adjuvant: "수술 후 보조치료", neoadjuvant: "수술 전 선행치료" };
  var PRIOR_KO = { gemcitabine: "젬시타빈", FOLFIRINOX: "FOLFIRINOX", platinum: "백금계(옥살리플라틴)", fluoropyrimidine: "5-FU 계열", irinotecan: "이리노테칸", taxane: "탁산(아브락산)", immunotherapy: "면역항암제", KRAS_inhibitor: "KRAS 억제제", radiotherapy: "방사선치료" };
  var BM_KO = { KRAS_G12C: "KRAS G12C", KRAS_G12D: "KRAS G12D", KRAS_G12V: "KRAS G12V", KRAS_G12R: "KRAS G12R", KRAS_mutant: "KRAS 변이", KRAS_wild: "KRAS 정상", BRCA_PALB2: "BRCA1/2·PALB2", HRD: "HRD", MSI_H: "MSI-H/dMMR", HER2: "HER2", CLDN18_2: "CLDN18.2", NTRK: "NTRK", NRG1: "NRG1", TMB_high: "TMB 높음", other: "기타 표적" };
  // 체크박스 값 → 약제 분류
  var REGIMEN = {
    folfirinox: ["FOLFIRINOX", "platinum", "fluoropyrimidine", "irinotecan"],
    gem_abx: ["gemcitabine", "taxane"],
    gem: ["gemcitabine"],
    naliri: ["irinotecan", "fluoropyrimidine"],
    folfox: ["platinum", "fluoropyrimidine"],
    capecitabine: ["fluoropyrimidine"],
    io: ["immunotherapy"],
    kras: ["KRAS_inhibitor"],
    rt: ["radiotherapy"],
  };
  var KRAS_SUB = ["KRAS_G12C", "KRAS_G12D", "KRAS_G12V", "KRAS_G12R", "KRAS_other"];

  function $(id) { return document.getElementById(id); }
  function val(name) { var el = document.querySelector('input[name="' + name + '"]:checked'); return el ? el.value : null; }
  function vals(name) { return Array.prototype.map.call(document.querySelectorAll('input[name="' + name + '"]:checked'), function (e) { return e.value; }); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function readForm() {
    var regimens = vals("regimen");
    var drugs = {};
    regimens.forEach(function (r) { (REGIMEN[r] || []).forEach(function (d) { drugs[d] = true; }); });
    var bm = vals("biomarker");
    var lines = val("lines");
    return {
      histology: val("histology") || "pdac",
      setting: val("setting"),
      lines: lines === null || lines === "unknown" ? null : parseInt(lines, 10),
      regimens: regimens, drugs: drugs,
      biomarkers: bm, krasKnown: bm.some(function (b) { return b.indexOf("KRAS") === 0; }),
      ecog: val("ecog") === null || val("ecog") === "unknown" ? null : parseInt(val("ecog"), 10),
      krOnly: $("f-kr").checked, recOnly: $("f-rec").checked,
    };
  }

  // 한 시험을 환자 정보와 대조한다. 결과: {level: "match"|"check"|"no", why: [..], ok: [..]}
  function evaluate(tr, p) {
    var m = tr.m, why = [], ok = [], check = [];
    var hard = m && m.src === "llm";
    // 조직형: 췌관선암 환자에게 신경내분비종양 전용 시험은 해당 없음 (반대도 마찬가지)
    if (p.histology === "pdac" && tr.h === "net") why.push("신경내분비종양(NET) 대상 시험");
    else if (p.histology === "net" && tr.h === "pdac") why.push("췌관선암(PDAC) 대상 시험");
    else if (p.histology === "net" && tr.h === "any") check.push("신경내분비종양 포함 여부 확인");
    if (!m) return { level: why.length ? "no" : "check", why: why.length ? why : ["조건 정보 없음"], ok: ok, check: check };

    // 질병 상태
    if (p.setting && m.set && m.set.length) {
      var wantSet = p.setting === "recurrent" ? "metastatic" : p.setting;
      if (m.set.indexOf(wantSet) >= 0) ok.push("질병 상태 " + SETTING_KO[wantSet]);
      else why.push("대상이 " + m.set.map(function (k) { return SETTING_KO[k] || k; }).join("·") + " 환자");
    } else if (!m.set || !m.set.length) check.push("대상 질병 상태 미확인");

    // 이전 치료 줄 수 (진행성 상태에서만 의미)
    var advanced = p.setting === "metastatic" || p.setting === "recurrent" || p.setting === "locally_advanced";
    if (advanced && p.lines !== null) {
      if (m.hi !== null && m.hi !== undefined && p.lines > m.hi) why.push(m.hi === 0 ? "1차 치료(항암 경험 없는 분) 전용" : "이전 항암 " + m.hi + "가지 이하만 가능");
      else if (m.lo !== null && m.lo !== undefined && p.lines < m.lo) why.push("이전 항암 " + m.lo + "가지 이상 받은 분 대상");
      else if (m.lo !== null || m.hi !== null) ok.push("치료 단계 조건 충족");
    } else if (advanced && (m.lo !== null || m.hi !== null)) check.push("받은 항암 요법 수를 고르면 더 정확합니다");

    // 받았어야 하는 치료
    (m.preq || []).forEach(function (d) {
      if (p.drugs[d]) ok.push(PRIOR_KO[d] + " 치료 경험 조건 충족");
      else if (p.regimens.length) (hard ? why : check).push(PRIOR_KO[d] + " 치료를 받았어야 함");
      else check.push(PRIOR_KO[d] + " 치료 경험 필요");
    });
    // 받았으면 안 되는 치료
    (m.pexc || []).forEach(function (d) {
      if (p.drugs[d]) (hard ? why : check).push(PRIOR_KO[d] + " 받은 환자는 제외" + (hard ? "" : " (원문 확인)"));
    });

    // 바이오마커
    (m.breq || []).forEach(function (b) {
      var has = p.biomarkers.indexOf(b) >= 0;
      if (b === "KRAS_mutant") has = p.biomarkers.some(function (x) { return KRAS_SUB.indexOf(x) >= 0; });
      if (has) { ok.push(BM_KO[b] + " 조건 충족"); return; }
      var hasAnyKrasMut = p.biomarkers.some(function (x) { return KRAS_SUB.indexOf(x) >= 0; });
      var explicitNo = false;
      if (b === "KRAS_mutant") explicitNo = p.biomarkers.indexOf("KRAS_wild") >= 0;       // KRAS 정상이면 제외
      else if (b === "KRAS_wild") explicitNo = hasAnyKrasMut;                               // KRAS 변이가 있으면 제외
      else if (b.indexOf("KRAS_G12") === 0) explicitNo = p.krasKnown;                       // 결과를 아는데 그 아형이 아님
      else explicitNo = p.biomarkers.indexOf("tested_neg") >= 0;                            // 검사했지만 해당 표적 없음
      if (explicitNo) why.push(BM_KO[b] + " 필요");
      else check.push(BM_KO[b] + " 검사 결과 필요");
    });
    (m.bexc || []).forEach(function (b) {
      var has = p.biomarkers.indexOf(b) >= 0 || (b === "KRAS_mutant" && p.biomarkers.some(function (x) { return KRAS_SUB.indexOf(x) >= 0; }));
      if (has) why.push(BM_KO[b] + " 있으면 제외");
    });

    // ECOG
    if (p.ecog !== null && m.ecog !== null && m.ecog !== undefined) {
      if (p.ecog > m.ecog) why.push("ECOG " + m.ecog + " 이하만 가능");
      else ok.push("ECOG 조건 충족");
    }

    var level = why.length ? "no" : (check.length ? "check" : "match");
    if (level !== "no" && m.src !== "llm") check.push("자동 추출 조건이라 원문 확인 필요");
    return { level: level, why: why, ok: ok, check: check };
  }

  function card(tr, ev) {
    var kr = tr.kr && tr.kr.length ? tr.kr.join(", ") : "";
    var pageUrl = root + "_generated/trials/" + tr.nct + "/";
    var h = '<div class="tf-card tf-' + ev.level + '">';
    h += '<div class="tf-head"><a href="' + pageUrl + '">' + esc(tr.t) + '</a></div>';
    h += '<div class="tf-meta">' + esc(tr.nct) + ' · ' + esc(tr.p) + ' · ' + esc(tr.s) + (kr ? ' · <b>국내: ' + esc(kr) + '</b>' : ' · 국내 기관 없음') + (tr.drug ? ' · ' + esc(tr.drug) : '') + '</div>';
    if (tr.m && tr.m.note) h += '<div class="tf-note">' + esc(tr.m.note) + '</div>';
    if (ev.why.length) h += '<div class="tf-why">✕ ' + ev.why.map(esc).join(" · ") + '</div>';
    if (ev.ok.length) h += '<div class="tf-ok">✓ ' + ev.ok.map(esc).join(" · ") + '</div>';
    if (ev.check && ev.check.length) h += '<div class="tf-check">? ' + ev.check.map(esc).join(" · ") + '</div>';
    if (tr.m && tr.m.excl && tr.m.excl.length) h += '<div class="tf-excl">주요 제외 기준: ' + tr.m.excl.map(esc).join(" · ") + '</div>';
    h += '<div class="tf-links"><a href="' + pageUrl + '">상세·참여 조건</a> · <a href="https://clinicaltrials.gov/study/' + esc(tr.nct) + '" target="_blank" rel="noopener">ClinicalTrials.gov</a></div>';
    return h + '</div>';
  }

  var root = "./", DATA = null, lastResult = null;

  function run() {
    if (!DATA) return;
    var p = readForm();
    var groups = { match: [], check: [], no: [] };
    DATA.trials.forEach(function (tr) {
      if (p.recOnly && !tr.rec) return;
      if (p.krOnly && !(tr.kr && tr.kr.length)) return;
      var ev = evaluate(tr, p);
      groups[ev.level].push({ tr: tr, ev: ev });
    });
    var score = function (x) { return (x.ev.ok.length * 2) + (x.tr.kr.length ? 3 : 0) + (x.tr.rec ? 2 : 0) + x.tr.imp; };
    ["match", "check"].forEach(function (k) { groups[k].sort(function (a, b) { return score(b) - score(a); }); });
    lastResult = { p: p, groups: groups };

    var out = $("tf-results");
    var total = groups.match.length + groups.check.length + groups.no.length;
    var h = '<p class="tf-summary">검토한 시험 ' + total + '건 (전체 ' + DATA.n + '건 중 필터 통과) · 기준일 ' + esc(DATA.generated) + '</p>';
    if (!p.setting) h += '<p class="tf-hint">위에서 <b>현재 상태</b>를 고르면 결과가 훨씬 정확해집니다.</p>';
    h += '<h3>조건에 맞을 가능성이 있는 시험 (' + groups.match.length + ')</h3>';
    h += groups.match.length ? groups.match.map(function (x) { return card(x.tr, x.ev); }).join("") : '<p>입력한 조건을 모두 만족하는 것으로 확인된 시험이 없습니다. 아래 "확인 필요"를 보세요.</p>';
    h += '<h3>조건 일부를 확인해야 하는 시험 (' + groups.check.length + ')</h3>';
    h += '<p class="tf-hint">조건 정보가 부족하거나 자동 추출이라 확실하지 않은 시험입니다. 유전자 검사 결과나 받은 항암제를 더 고르면 줄어듭니다.</p>';
    h += groups.check.map(function (x) { return card(x.tr, x.ev); }).join("");
    h += '<details class="tf-no"><summary>조건에 맞지 않는 것으로 보이는 시험 (' + groups.no.length + ')</summary>';
    h += groups.no.map(function (x) { return card(x.tr, x.ev); }).join("") + '</details>';
    out.innerHTML = h;
    $("tf-copy").disabled = !(groups.match.length || groups.check.length);
  }

  // ---- 치료 요약 붙여넣기 → 자동 체크
  function parseSummary(text) {
    var t = text || "", lower = t.toLowerCase();
    var set = function (name, v) { var el = document.querySelector('input[name="' + name + '"][value="' + v + '"]'); if (el) el.checked = true; };
    var regs = [];
    if (/folfirinox|폴피리녹스|폴피/.test(lower)) regs.push("folfirinox");
    if (/abraxane|nab[- ]?paclitaxel|아브락산|젬아|젬브/.test(lower)) regs.push("gem_abx");
    else if (/gemcitabine|젬시타빈|젬자/.test(lower)) regs.push("gem");
    if (/onivyde|nal-?iri|liposomal irinotecan|오니바이드|나리리/.test(lower)) regs.push("naliri");
    if (/folfox|폴폭스/.test(lower) && !/folfirinox/.test(lower)) regs.push("folfox");
    if (/capecitabine|xeloda|젤로다|카페시타빈|s-1|티에스원/.test(lower)) regs.push("capecitabine");
    if (/pembrolizumab|keytruda|nivolumab|opdivo|키트루다|옵디보|면역항암|checkpoint/.test(lower)) regs.push("io");
    if (/daraxonrasib|rmc-6236|sotorasib|adagrasib|kras 억제|ras 억제|kras inhibitor/.test(lower)) regs.push("kras");
    if (/radiotherap|radiation|\brt\b|gy\b|방사선/.test(lower)) regs.push("rt");
    regs.forEach(function (r) { set("regimen", r); });

    var bms = [];
    var kras = t.match(/KRAS[^A-Za-z0-9]{0,6}(p\.)?G12([CDVR])/i);
    if (kras) bms.push("KRAS_G12" + kras[2].toUpperCase());
    else if (/KRAS[^.\n]{0,20}(G13|Q61|mut|변이)/i.test(t)) bms.push("KRAS_other");
    else if (/KRAS[^.\n]{0,15}(wild|WT|정상|음성)/i.test(t)) bms.push("KRAS_wild");
    if (/BRCA|PALB2/i.test(t)) bms.push("BRCA_PALB2");
    if (/MSI-?H|dMMR|microsatellite instab/i.test(t)) bms.push("MSI_H");
    if (/HER2[^.\n]{0,15}(positive|양성|amplif|\+)/i.test(t)) bms.push("HER2");
    if (/CLDN ?18|claudin/i.test(t)) bms.push("CLDN18_2");
    if (/NTRK/i.test(t)) bms.push("NTRK");
    if (/NRG1/i.test(t)) bms.push("NRG1");
    bms.forEach(function (b) { set("biomarker", b); });

    if (/neuroendocrine|신경내분비|pnet|\bnet\b/i.test(t)) set("histology", "net"); else set("histology", "pdac");

    var setting = null;
    if (/metasta|전이|stage ?(iv|4)|4기/i.test(t)) setting = "metastatic";
    if (/recurren|재발/i.test(t)) setting = "recurrent";
    if (!setting && /locally advanced|unresectable|국소진행|절제 불가/i.test(t)) setting = "locally_advanced";
    if (!setting && /resectable|borderline|경계성|수술 가능/i.test(t)) setting = "resectable";
    if (!setting && /adjuvant|보조/i.test(t)) setting = "adjuvant";
    if (setting) set("setting", setting);

    var e = t.match(/ECOG[^0-9]{0,15}([0-4])/i);
    if (e) set("ecog", e[1]);

    // 진행성 상태에서 받은 요법 수 (대략): 서로 다른 항암 요법 개수
    var n = regs.filter(function (r) { return ["folfirinox", "gem_abx", "gem", "naliri", "folfox", "capecitabine", "io", "kras"].indexOf(r) >= 0; }).length;
    if (setting === "metastatic" || setting === "recurrent" || setting === "locally_advanced") set("lines", n >= 3 ? "3" : String(n));
    return { regs: regs, bms: bms, setting: setting, ecog: e ? e[1] : null, lines: n };
  }

  function copySummary() {
    if (!lastResult) return;
    var p = lastResult.p, g = lastResult.groups;
    var lines = ["[임상시험 후보 정리 - pancreas.dopamine.me.kr 맞춤 찾기]", ""];
    lines.push("암 종류: " + ({ pdac: "췌장선암(췌관선암)", net: "췌장 신경내분비종양", unknown: "모름" })[p.histology]);
    lines.push("현재 상태: " + (p.setting ? ({ metastatic: "전이성(4기)", recurrent: "수술 후 재발(전이)", locally_advanced: "국소진행(수술 불가)", resectable: "수술 가능·경계성", adjuvant: "수술 후 보조치료 단계" })[p.setting] : "미입력"));
    lines.push("진행성 상태에서 받은 항암 요법 수: " + (p.lines === null ? "미입력" : p.lines + (p.lines >= 3 ? "개 이상" : "개")));
    lines.push("받은 치료: " + (p.regimens.length ? p.regimens.map(function (r) { var el = document.querySelector('input[name="regimen"][value="' + r + '"]'); return el ? el.parentNode.textContent.trim() : r; }).join(", ") : "미입력"));
    lines.push("유전자·표지자: " + (p.biomarkers.length ? p.biomarkers.map(function (b) { return BM_KO[b] || b.replace("tested_neg", "검사했으나 표적 변이 없음").replace("KRAS_other", "기타 KRAS 변이"); }).join(", ") : "미입력"));
    lines.push("ECOG: " + (p.ecog === null ? "미입력" : p.ecog));
    lines.push("");
    var add = function (title, arr) {
      lines.push(title + " (" + arr.length + ")");
      arr.slice(0, 15).forEach(function (x) {
        lines.push("- " + x.tr.nct + " · " + x.tr.t + (x.tr.kr.length ? " · 국내: " + x.tr.kr.join(", ") : "") + " · https://clinicaltrials.gov/study/" + x.tr.nct);
      });
      lines.push("");
    };
    add("가능성 있는 시험", g.match);
    add("확인 필요한 시험", g.check);
    lines.push("※ ClinicalTrials.gov 등록 정보를 자동 정리한 것으로, 실제 참여 가능 여부는 담당 의료진과 해당 기관 임상시험센터에서 확인해야 합니다.");
    var text = lines.join("\n");
    var done = function () { $("tf-copy").textContent = "복사됨 ✓"; setTimeout(function () { $("tf-copy").textContent = "주치의용 요약 복사"; }, 2000); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); });
    else { fallback(text); done(); }
    function fallback(s) { var ta = document.createElement("textarea"); ta.value = s; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); } catch (e) {} document.body.removeChild(ta); }
  }

  function init() {
    var form = $("trial-finder");
    if (!form) return;
    var logo = document.querySelector("a.md-header__button.md-logo");
    root = logo ? logo.getAttribute("href") : "../../../";
    if (root.charAt(root.length - 1) !== "/") root += "/";
    $("tf-results").innerHTML = '<p class="tf-hint">시험 목록을 불러오는 중…</p>';
    fetch(root + "_generated/trials/match.json", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (d) {
      DATA = d; run();
    }).catch(function () { $("tf-results").innerHTML = '<p class="tf-hint">시험 목록을 불러오지 못했습니다. 새로고침해 주세요.</p>'; });
    form.addEventListener("change", run);
    $("tf-parse").addEventListener("click", function () {
      var r = parseSummary($("tf-paste").value);
      $("tf-parse-msg").textContent = "자동으로 체크했습니다: 치료 " + r.regs.length + "건, 변이 " + r.bms.length + "건" + (r.setting ? ", 상태 1건" : "") + (r.ecog ? ", ECOG" : "") + ". 아래에서 맞는지 확인하고 고쳐 주세요.";
      run();
    });
    $("tf-reset").addEventListener("click", function () { form.reset(); $("tf-paste").value = ""; $("tf-parse-msg").textContent = ""; run(); });
    $("tf-copy").addEventListener("click", copySummary);
  }

  if (window.document$) document$.subscribe(init); else document.addEventListener("DOMContentLoaded", init);
})();
