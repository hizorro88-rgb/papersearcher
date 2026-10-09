// 용어사전 페이지: 입력한 글자가 포함된 행만 남기고, 빈 섹션은 숨긴다.
document$.subscribe(function () {
  var box = document.getElementById("glossary-filter");
  if (!box) return;
  var content = box.closest(".md-content__inner") || document;
  var tables = Array.from(content.querySelectorAll("table"));
  var counter = document.getElementById("glossary-count");
  function norm(s) { return (s || "").toLowerCase().replace(/\s+/g, ""); }
  function apply() {
    var q = norm(box.value);
    var shown = 0;
    tables.forEach(function (t) {
      var rows = Array.from(t.querySelectorAll("tbody tr"));
      var visible = 0;
      rows.forEach(function (r) {
        var hit = !q || norm(r.textContent).indexOf(q) !== -1;
        r.style.display = hit ? "" : "none";
        if (hit) visible++;
      });
      shown += visible;
      // 표 앞의 가장 가까운 제목(h2/h3)과 표를 함께 숨김
      var wrap = t.closest(".md-typeset__table") || t;
      wrap.style.display = visible ? "" : "none";
      var h = wrap.previousElementSibling;
      while (h && !/^H[23]$/.test(h.tagName)) h = h.previousElementSibling;
      if (h) h.style.display = visible || !q ? "" : "none";
    });
    if (counter) counter.textContent = q ? shown + "개 항목" : "";
  }
  box.addEventListener("input", apply);
  var params = new URLSearchParams(location.search);
  if (params.get("q")) { box.value = params.get("q"); apply(); }
});
