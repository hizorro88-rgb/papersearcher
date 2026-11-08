/* 관심 주제로 필터: 모든 처리는 브라우저 안에서. 저장은 이 브라우저의 localStorage에만. */
(function () {
  var KEY = "ps-research-filter", PAGE = 40;
  var DATA = null, root = "./", shown = PAGE, topicById = {};

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null"); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }

  function state() {
    var topics = Array.prototype.map.call(document.querySelectorAll(".rf-topic.on"), function (b) { return b.getAttribute("data-id"); });
    return { t: topics, q: $("rf-q").value.trim(), p: $("rf-paper").checked, tr: $("rf-trial").checked, kr: $("rf-kr").checked, d: $("rf-days").value, s: $("rf-sort").value };
  }
  function apply(st) {
    if (!st) return;
    document.querySelectorAll(".rf-topic").forEach(function (b) { b.classList.toggle("on", (st.t || []).indexOf(b.getAttribute("data-id")) >= 0); });
    $("rf-q").value = st.q || ""; $("rf-paper").checked = st.p !== false; $("rf-trial").checked = st.tr !== false;
    $("rf-kr").checked = !!st.kr; $("rf-days").value = st.d || "0"; $("rf-sort").value = st.s || "date";
  }
  function toUrl(st) {
    var p = new URLSearchParams();
    if (st.t.length) p.set("t", st.t.join(","));
    if (st.q) p.set("q", st.q);
    if (!st.p) p.set("paper", "0"); if (!st.tr) p.set("trial", "0"); if (st.kr) p.set("kr", "1");
    if (st.d !== "0") p.set("d", st.d); if (st.s !== "date") p.set("s", st.s);
    var qs = p.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
  }
  function fromUrl() {
    var p = new URLSearchParams(location.search);
    if (!p.toString()) return null;
    return { t: (p.get("t") || "").split(",").filter(Boolean), q: p.get("q") || "", p: p.get("paper") !== "0", tr: p.get("trial") !== "0", kr: p.get("kr") === "1", d: p.get("d") || "0", s: p.get("s") || "date" };
  }

  // 한 항목의 검색 대상 텍스트 (소문자)
  function haystack(it) {
    if (!it._h) it._h = [it.t, it.te, it.s, it.x, (it.c || []).join(" "), it.e, it.nct || ""].join(" \n ").toLowerCase();
    return it._h;
  }
  function matchTerms(it, terms) {
    var h = haystack(it);
    for (var i = 0; i < terms.length; i++) if (h.indexOf(terms[i]) >= 0) return true;
    return false;
  }
  // 검색창 단어: 주제 별칭이면 그 주제의 terms로 확장, 아니면 글자 그대로
  function expand(word) {
    var w = word.toLowerCase();
    for (var i = 0; i < DATA.topics.length; i++) {
      var tp = DATA.topics[i];
      if (tp.id === w || tp.aliases.indexOf(w) >= 0 || tp.label.toLowerCase() === w) return tp.terms;
    }
    return [w];
  }

  function run(keepShown) {
    if (!DATA) return;
    if (!keepShown) shown = PAGE;
    var st = state(); toUrl(st);
    var groups = st.t.map(function (id) { return topicById[id] ? topicById[id].terms : []; });
    st.q.split(/[\s,]+/).filter(Boolean).forEach(function (w) { groups.push(expand(w)); });
    var cut = st.d !== "0" ? new Date(Date.now() - parseInt(st.d, 10) * 86400000).toISOString().slice(0, 10) : null;
    var saved = store(KEY), lastSeen = saved && saved.seen ? saved.seen : null;
    var out = DATA.items.filter(function (it) {
      var isTrial = !!it.nct;
      if (isTrial && !st.tr) return false;
      if (!isTrial && !st.p) return false;
      if (st.kr && isTrial && !it.kr) return false;
      if (cut && (it.d || it.f) < cut) return false;
      for (var g = 0; g < groups.length; g++) if (!matchTerms(it, groups[g])) return false;
      return true;
    });
    if (st.s === "imp") out.sort(function (a, b) { return b.imp - a.imp; });
    var fresh = lastSeen ? out.filter(function (it) { return it.f > lastSeen || it.u > lastSeen; }).length : 0;
    $("rf-count").innerHTML = (groups.length ? "조건에 맞는 항목 <b>" + out.length + "</b>건 (전체 " + DATA.n + "건 중)" : "전체 <b>" + out.length + "</b>건 · 위에서 주제를 고르거나 검색어를 입력하세요")
      + (lastSeen ? ' · 마지막 확인(' + esc(lastSeen) + ') 이후 새로 들어오거나 바뀐 항목 <b class="rf-fresh">' + fresh + '</b>건' : "")
      + ' · 기준일 ' + esc(DATA.generated);
    var html = out.slice(0, shown).map(function (it) { return card(it, lastSeen); }).join("");
    $("rf-results").innerHTML = html || '<p class="rf-hint">조건에 맞는 항목이 없습니다. 주제를 하나 빼거나 기간을 넓혀 보세요.</p>';
    $("rf-more").hidden = out.length <= shown;
    $("rf-more").textContent = "더 보기 (" + Math.max(out.length - shown, 0) + "건 남음)";
  }

  function card(it, lastSeen) {
    var isNew = lastSeen && (it.f > lastSeen || it.u > lastSeen);
    var badges = ['<span class="rf-b">' + esc(it.ty) + '</span>', '<span class="rf-b">' + esc(it.e) + '</span>'];
    (it.c || []).forEach(function (c) { if (c !== it.ty) badges.push('<span class="rf-b">' + esc(c) + '</span>'); });
    if (it.nct) badges.push('<span class="rf-b ' + (it.kr ? "rf-kr" : "") + '">' + (it.kr ? "국내 기관" : "해외") + (it.rec ? " · 모집 중" : "") + '</span>');
    var h = '<div class="rf-card' + (isNew ? " rf-new" : "") + '">';
    h += '<div class="rf-title">' + (isNew ? '<span class="rf-newtag">NEW</span> ' : "") + '<a href="' + esc(it.url) + '" target="_blank" rel="noopener">' + esc(it.t) + '</a></div>';
    if (it.te) h += '<div class="rf-en">' + esc(it.te) + '</div>';
    h += '<div class="rf-meta">' + badges.join(" ") + ' · ' + esc(it.d || "날짜 미상") + ' · ' + esc(it.src) + '</div>';
    if (it.s) h += '<div class="rf-sum">' + esc(it.s) + '</div>';
    h += '<div class="rf-links"><a href="' + root + esc(it.page) + '">' + (it.nct ? "참여 조건·국내 기관" : "사이트에서 보기") + '</a> · <a href="' + esc(it.url) + '" target="_blank" rel="noopener">원문</a></div>';
    return h + "</div>";
  }

  function renderTopics() {
    var byGroup = {}, order = [];
    DATA.topics.forEach(function (t) { topicById[t.id] = t; if (!byGroup[t.group]) { byGroup[t.group] = []; order.push(t.group); } byGroup[t.group].push(t); });
    $("rf-topics").innerHTML = order.map(function (g) {
      return '<div class="rf-group"><span class="rf-gname">' + esc(g) + '</span>' + byGroup[g].map(function (t) {
        return '<button type="button" class="rf-topic" data-id="' + esc(t.id) + '">' + esc(t.label) + '</button>';
      }).join("") + "</div>";
    }).join("");
    $("rf-topics").addEventListener("click", function (e) {
      var b = e.target.closest(".rf-topic"); if (!b) return;
      b.classList.toggle("on"); run();
    });
  }

  function init() {
    var box = $("rf"); if (!box) return;
    var logo = document.querySelector("a.md-header__button.md-logo");
    root = logo ? logo.getAttribute("href") : "../../";
    if (root.charAt(root.length - 1) !== "/") root += "/";
    $("rf-results").innerHTML = '<p class="rf-hint">목록을 불러오는 중…</p>';
    fetch(root + "_generated/items.json", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (d) {
      DATA = d; renderTopics();
      var saved = store(KEY);
      apply(fromUrl() || (saved && saved.st) || null);
      if (saved && saved.st && !fromUrl()) $("rf-saved-msg").textContent = "저장된 관심 주제를 적용했습니다.";
      run();
    }).catch(function () { $("rf-results").innerHTML = '<p class="rf-hint">목록을 불러오지 못했습니다. 새로고침해 주세요.</p>'; });

    var timer = null;
    $("rf-q").addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 250); });
    ["rf-paper", "rf-trial", "rf-kr", "rf-days", "rf-sort"].forEach(function (id) { $(id).addEventListener("change", function () { run(); }); });
    $("rf-more").addEventListener("click", function () { shown += PAGE; run(true); });
    $("rf-save").addEventListener("click", function () {
      store(KEY, { st: state(), seen: new Date().toISOString().slice(0, 10) });
      $("rf-saved-msg").textContent = "저장했습니다. 다음에 열면 이 조건이 적용되고, 오늘 이후 새 항목에 NEW가 붙습니다.";
      run(true);
    });
    $("rf-clear").addEventListener("click", function () {
      document.querySelectorAll(".rf-topic.on").forEach(function (b) { b.classList.remove("on"); });
      $("rf-q").value = ""; $("rf-paper").checked = true; $("rf-trial").checked = true; $("rf-kr").checked = false; $("rf-days").value = "0"; $("rf-sort").value = "date";
      try { localStorage.removeItem(KEY); } catch (e) {}
      $("rf-saved-msg").textContent = "저장된 관심 주제를 지웠습니다."; run();
    });
  }

  if (window.document$) document$.subscribe(init); else document.addEventListener("DOMContentLoaded", init);
})();
