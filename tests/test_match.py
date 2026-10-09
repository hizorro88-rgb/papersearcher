"""맞춤 임상시험 찾기: 규칙 추출·LLM 병합·match.json."""
import json

from collector.match import extract_rules, histology, lines_ko, match_from_llm, merge_match
from collector.models import Item, Source, TrialInfo


def trial(title, elig, conditions=("Pancreatic Ductal Adenocarcinoma",), interventions=("DrugX",)):
    return Item(id="nct:NCT00000001", type="trial", title=title, source=Source(name="clinicaltrials", url="https://x"),
                trial=TrialInfo(nct_id="NCT00000001", eligibility_text=elig, conditions=list(conditions),
                                interventions=list(interventions)))


def test_second_line_kras_g12d_trial():
    it = trial("Study of DrugX in KRAS G12D Mutated Pancreatic Cancer", """Inclusion Criteria:
* Histologically confirmed locally advanced unresectable or metastatic pancreatic adenocarcinoma.
* Documented KRAS G12D mutation.
* Must have received prior first-line systemic therapy. Prior adjuvant chemotherapy is allowed if recurrence > 6 months.
* ECOG performance status of 0 or 1.
* At least one measurable lesion per RECIST v1.1.
Exclusion Criteria:
* Prior treatment with a KRAS G12D inhibitor.
* Radiotherapy within 2 weeks.""")
    m = extract_rules(it)
    assert m.setting == ["metastatic", "locally_advanced"]
    assert m.min_prior_lines == 1 and m.max_prior_lines is None
    assert m.biomarkers_required == ["KRAS_G12D"]
    assert m.prior_excluded == ["KRAS_inhibitor"]       # 휴약기간(방사선 2주)은 제외 조건이 아님
    assert m.ecog_max == 1 and m.measurable_required is True
    assert "1가지 이상" in lines_ko(m)


def test_first_line_from_exclusion_and_adjuvant_setting():
    it = trial("DrugX Plus Gemcitabine as First-Line Treatment", """Inclusion Criteria:
* Metastatic pancreatic ductal adenocarcinoma.
* ECOG ≤ 1
Exclusion Criteria:
* Have prior systemic therapy in the metastatic setting.""")
    m = extract_rules(it)
    assert m.max_prior_lines == 0 and m.min_prior_lines is None

    adj = trial("Adjuvant DrugX After Resection", """Inclusion Criteria:
* Resected (R0/R1) pancreatic adenocarcinoma with no distant metastasis.
* No prior chemotherapy for pancreatic cancer.
Exclusion Criteria:
* Metastatic disease.""")
    m2 = extract_rules(adj)
    assert "adjuvant" in m2.setting and "metastatic" not in m2.setting


def test_llm_merge_and_histology():
    it = trial("Zanzalintinib in Neuroendocrine Tumors", "Inclusion Criteria:\n* ECOG 0-2", conditions=("Pancreatic Neuroendocrine Tumor",))
    rules = extract_rules(it)
    assert rules.ecog_max == 2 and histology(it) == "net"
    llm = match_from_llm({"setting": ["metastatic", "bogus"], "min_prior_lines": 1, "max_prior_lines": -1,
                          "prior_required": [], "prior_excluded": ["radiotherapy"], "biomarkers_required": [],
                          "biomarkers_excluded": [], "ecog_max": -1, "measurable_required": "yes",
                          "notes_ko": "이전 치료 1가지 이상 받은 전이성 환자", "key_exclusions_ko": ["뇌전이"]})
    merged = merge_match(rules, llm)
    assert merged.source == "llm" and merged.setting == ["metastatic"]
    assert merged.min_prior_lines == 1 and merged.max_prior_lines is None
    assert merged.ecog_max == 2                     # LLM이 비운 칸은 규칙 값으로
    assert merged.measurable_required is True and merged.key_exclusions_ko == ["뇌전이"]


def test_match_json_and_trial_page(tmp_root):
    from datetime import date
    from collector import config, render, store
    from collector.classify import classify
    it = trial("DrugX in KRAS G12C Pancreatic Cancer", "Inclusion Criteria:\n* KRAS G12C mutation\n* metastatic disease\n* ECOG 0-1")
    from collector.models import HistoryEvent
    it.history.append(HistoryEvent(date="2026-10-09", event="new"))
    classify(it, date(2026, 10, 9))
    assert it.trial.match and it.trial.match.biomarkers_required == ["KRAS_G12C"]
    store.save(it)
    render.render_all(store.load_all(), {"sources": {}, "runs": []}, date(2026, 10, 9))
    d = json.loads((config.GENERATED_DIR / "trials" / "match.json").read_text(encoding="utf-8"))
    assert d["n"] == 1 and d["trials"][0]["m"]["breq"] == ["KRAS_G12C"] and d["trials"][0]["h"] == "pdac"
    page = (config.GENERATED_DIR / "trials" / "NCT00000001.md").read_text(encoding="utf-8")
    assert "이 시험이 맞는 환자" in page and "KRAS G12C" in page and "맞춤 임상시험 찾기" in page
